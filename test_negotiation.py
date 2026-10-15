import io
import json
import unittest
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
from datetime import date
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from consultation_frames import NegotiationFrame, TradeInFrame
from negotiation import advise_negotiation
from trade_in import compare_trade_in
from seller_profile import SellerVehicleFrame
from valuation import estimate_vehicle_value
from vehicle_frame import load_vehicles

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def fixture(name, frame):
    return frame.model_validate_json((ROOT/'examples'/name).read_text(encoding='utf-8'))


def change(frame, **updates):
    return type(frame).model_validate(frame.model_dump() | updates)


class NegotiationTests(unittest.TestCase):
    def setUp(self):
        self.buyer = fixture('negotiation_buyer.json', NegotiationFrame)
        self.seller = fixture('negotiation_seller.json', NegotiationFrame)
        vehicle = fixture('seller_alza.json', SellerVehicleFrame)
        cars = load_vehicles(ROOT/'data/vehicles_real.json')
        self.reference = estimate_vehicle_value(vehicle, cars, as_of=AS_OF)
        self.insufficient = estimate_vehicle_value(vehicle, cars[:1], as_of=AS_OF)
        self.illustrative = estimate_vehicle_value(vehicle, cars, as_of=AS_OF, illustrative_adjustments=True)
        self.damage = estimate_vehicle_value(change(vehicle, flood_damage_reported=True), cars, as_of=AS_OF)

    def advice(self, profile=None, reference='default'):
        return advise_negotiation(profile or self.buyer, as_of=AS_OF, valuation_result=self.reference if reference == 'default' else reference)

    def test_buyer_total_budget_includes_fees(self):
        result = self.advice()
        self.assertEqual(result['status'], 'advice_ready')
        self.assertEqual(result['suggested_counter_price_myr'], 44500)
        self.assertEqual(result['calculations']['offered_total_cost_myr'], 47500)
        self.assertEqual(result['suggested_counter_price_myr'] + self.buyer.fees_myr, self.buyer.buyer_total_budget_myr)
        self.assertEqual(result['fired_rules'][-1]['rule_id'], 'NEG_BUY_BUDGET')

    def test_buyer_budget_and_reference_boundaries_inclusive(self):
        for offer, budget in [(44500, 46000), (45000, 46500), (35888, 50000)]:
            result = self.advice(change(self.buyer, current_offer_myr=offer, buyer_total_budget_myr=budget))
            self.assertEqual(result['action'], 'review_offer')
            self.assertIsNone(result['suggested_counter_price_myr'])

    def test_buyer_reference_anchor_is_not_declared_fair_value(self):
        result = self.advice(change(self.buyer, buyer_total_budget_myr=50000))
        self.assertEqual(result['suggested_counter_price_myr'], 44800)
        self.assertEqual(result['fired_rules'][-1]['rule_id'], 'NEG_BUY_REFERENCE')
        self.assertTrue(any('does not establish' in note for note in result['limitations']))

    def test_low_quote_requests_details(self):
        result = self.advice(change(self.buyer, current_offer_myr=30000))
        self.assertEqual(result['action'], 'verify_listing_details')
        self.assertIsNone(result['suggested_counter_price_myr'])

    def test_fees_exhaust_budget_no_negative_counter(self):
        for fees in [46000, 50000]:
            result = self.advice(change(self.buyer, fees_myr=fees))
            self.assertEqual(result['action'], 'review_budget_or_fees')
            self.assertIsNone(result['suggested_counter_price_myr'])

    def test_seller_net_floor_includes_fees_and_settlement(self):
        result = self.advice(self.seller)
        self.assertEqual(result['calculations']['offered_net_proceeds_myr'], 34000)
        self.assertEqual(result['calculations']['minimum_vehicle_price_myr'], 44000)
        self.assertEqual(result['suggested_counter_price_myr'], 44800)
        self.assertGreaterEqual(result['suggested_counter_price_myr'] - 1000 - 5000, 38000)

    def test_seller_exact_net_floor_and_strong_bid(self):
        for offer in [44000, 50000]:
            result = self.advice(change(self.seller, current_offer_myr=offer))
            self.assertEqual(result['action'], 'review_offer')
            self.assertIsNone(result['suggested_counter_price_myr'])

    def test_seller_meets_reserve_but_below_asking_evidence(self):
        result = self.advice(change(self.seller, current_offer_myr=30000, seller_minimum_net_myr=20000))
        self.assertEqual(result['fired_rules'][-1]['rule_id'], 'NEG_SELL_REFERENCE')
        self.assertEqual(result['suggested_counter_price_myr'], 44800)

    def test_seller_asking_price_conflicts_with_net_floor(self):
        result = self.advice(change(self.seller, asking_price_myr=43000))
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertIsNone(result['suggested_counter_price_myr'])

    def test_unknown_and_partial_fees_never_assumed_zero(self):
        for profile in [self.buyer, self.seller]:
            for updates in [{'fees_myr': None}, {'fees_confirmed_complete': None}, {'fees_confirmed_complete': False}]:
                result = self.advice(change(profile, **updates))
                self.assertEqual(result['status'], 'needs_clarification')
                self.assertIsNone(result['suggested_counter_price_myr'])
        self.assertEqual(self.advice(change(self.seller, loan_settlement_myr=None))['status'], 'needs_clarification')

    def test_no_valuation_only_limit_advice(self):
        for reference in [None, self.insufficient]:
            result = self.advice(reference=reference)
            self.assertEqual(result['status'], 'limited_advice')
            self.assertEqual(result['price_position'], 'not_assessed')
            self.assertEqual(result['suggested_counter_price_myr'], 44500)
        result = self.advice(change(self.buyer, current_offer_myr=44000), reference=None)
        self.assertEqual(result['action'], 'review_offer')

    def test_wrong_identity_date_damage_and_bad_arithmetic_block(self):
        wrong_identity = deepcopy(self.reference)
        wrong_identity['seller_profile']['model'] = 'Bezza'
        old_date = deepcopy(self.reference)
        old_date['as_of'] = '2026-10-14'
        bad_math = deepcopy(self.reference)
        bad_math['reference']['median_asking_price_myr'] = 1
        for reference in [wrong_identity, old_date, bad_math]:
            result = self.advice(reference=reference)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertIsNone(result['suggested_counter_price_myr'])
        self.assertEqual(self.advice(reference=self.damage)['status'], 'inspection_required')

    def test_illustrative_adjustment_never_used_as_market_anchor(self):
        result = self.advice(change(self.buyer, buyer_total_budget_myr=50000), reference=self.illustrative)
        self.assertEqual(result['suggested_counter_price_myr'], 44800)
        self.assertNotEqual(result['suggested_counter_price_myr'], 43092)

    def test_counter_invariants_across_limits(self):
        for budget in [20000, 40000, 50000, 60000]:
            for offer in [10000, 40000, 46000, 70000]:
                result = self.advice(change(self.buyer, buyer_total_budget_myr=budget, current_offer_myr=offer))
                counter = result['suggested_counter_price_myr']
                if counter is not None:
                    self.assertLessEqual(counter + self.buyer.fees_myr, budget)
                    self.assertLessEqual(counter, offer)
        for reserve in [20000, 38000, 60000]:
            result = self.advice(change(self.seller, asking_price_myr=None, seller_minimum_net_myr=reserve))
            counter = result['suggested_counter_price_myr']
            if counter is not None:
                self.assertGreaterEqual(counter - self.seller.fees_myr - self.seller.loan_settlement_myr, reserve)


class TradeInTests(unittest.TestCase):
    def setUp(self):
        self.profile = fixture('trade_in.json', TradeInFrame)

    def test_cash_differences_reconcile_by_hand(self):
        result = compare_trade_in(self.profile)
        self.assertEqual(result['paths']['trade_in']['net_proceeds_myr'], 24500)
        self.assertEqual(result['paths']['trade_in']['cash_difference_myr'], 41500)
        self.assertEqual(result['paths']['private_sale']['net_proceeds_myr'], 29000)
        self.assertEqual(result['paths']['private_sale']['cash_difference_myr'], 37000)
        self.assertEqual(result['comparison']['private_sale_cash_advantage_myr'], 4500)
        self.assertEqual(result['suggested_path'], 'private_sale')

    def test_path_specific_replacement_discount_can_reverse_result(self):
        profile = change(self.profile, trade_in_replacement=change(self.profile.trade_in_replacement, price_myr=60000))
        result = compare_trade_in(profile)
        self.assertEqual(result['paths']['trade_in']['cash_difference_myr'], 36500)
        self.assertEqual(result['suggested_path'], 'trade_in')
        self.assertEqual(result['comparison']['private_sale_cash_advantage_myr'], -500)

    def test_unknown_fees_partial_fees_and_settlement_withheld(self):
        for updates in [{'fees_myr': None}, {'fees_confirmed_complete': False}, {'fees_confirmed_complete': None}]:
            p = change(self.profile, private_sale_quote=change(self.profile.private_sale_quote, **updates))
            result = compare_trade_in(p)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertIsNone(result['paths']['private_sale']['cash_difference_myr'])
            self.assertIsNone(result['comparison'])
            self.assertIsNone(result['suggested_path'])
            self.assertEqual(result['paths']['trade_in']['cash_difference_myr'], 41500)
        result = compare_trade_in(change(self.profile, loan_settlement_myr=None))
        self.assertTrue(all(row['cash_difference_myr'] is None for row in result['paths'].values()))

    def test_negative_equity_and_cash_surplus_not_clamped_away(self):
        result = compare_trade_in(change(self.profile, loan_settlement_myr=50000))
        self.assertEqual(result['paths']['trade_in']['net_proceeds_myr'], -15500)
        self.assertEqual(result['paths']['trade_in']['cash_difference_myr'], 81500)
        cheap = change(self.profile.trade_in_replacement, price_myr=10000, fees_myr=0)
        result = compare_trade_in(change(self.profile, loan_settlement_myr=0, trade_in_replacement=cheap))
        row = result['paths']['trade_in']
        self.assertEqual((row['cash_difference_myr'], row['cash_required_myr'], row['cash_surplus_myr']), (-24500, 0, 24500))

    def test_cash_limit_overrides_speed_preference(self):
        result = compare_trade_in(change(self.profile, priority='speed', available_cash_myr=40000))
        self.assertEqual(result['suggested_path'], 'private_sale')
        self.assertFalse(result['paths']['trade_in']['within_available_cash'])
        result = compare_trade_in(change(self.profile, available_cash_myr=30000))
        self.assertIsNone(result['suggested_path'])
        self.assertEqual(result['fired_rules'][-1]['rule_id'], 'TRADE_CASH_LIMIT')

    def test_speed_effort_use_user_estimates_not_path_assumptions(self):
        for priority in ['speed', 'effort']:
            self.assertEqual(compare_trade_in(change(self.profile, priority=priority))['suggested_path'], 'trade_in')
            faster = change(self.profile.private_sale_quote, estimated_completion_days=1, estimated_effort_hours=1)
            result = compare_trade_in(change(self.profile, priority=priority, private_sale_quote=faster))
            self.assertEqual(result['suggested_path'], 'private_sale')

    def test_unknown_time_no_priority_and_ties_not_invented(self):
        quote = change(self.profile.private_sale_quote, estimated_completion_days=None)
        result = compare_trade_in(change(self.profile, priority='speed', private_sale_quote=quote))
        self.assertIsNone(result['suggested_path'])
        self.assertIsNone(result['time_comparison']['faster_path'])
        self.assertIsNone(compare_trade_in(change(self.profile, priority=None))['suggested_path'])
        tied = change(self.profile.private_sale_quote, price_myr=35500)
        result = compare_trade_in(change(self.profile, private_sale_quote=tied))
        self.assertEqual(result['comparison']['lower_cash_difference_path'], 'tie')
        self.assertIsNone(result['suggested_path'])

    def test_explicit_zero_and_cents_are_preserved(self):
        replacement = change(self.profile.trade_in_replacement, price_myr=65000.01, fees_myr=0)
        disposal = change(self.profile.trade_in_quote, price_myr=35000, fees_myr=0)
        result = compare_trade_in(change(self.profile, trade_in_replacement=replacement, trade_in_quote=disposal, loan_settlement_myr=0))
        self.assertEqual(result['paths']['trade_in']['cash_difference_myr'], 30000.01)

    def test_unknown_cash_does_not_claim_affordability(self):
        result = compare_trade_in(change(self.profile, available_cash_myr=None))
        self.assertEqual(result['status'], 'comparison_ready')
        self.assertTrue(all(row['within_available_cash'] is None for row in result['paths'].values()))
        self.assertTrue(any('does not establish affordability' in text for text in result['limitations']))

    def test_additional_fees_and_loan_have_monotonic_effect(self):
        baseline = compare_trade_in(self.profile)['paths']['trade_in']['cash_difference_myr']
        for extra in [0, 0.01, 100, 5000]:
            quote = change(self.profile.trade_in_quote, fees_myr=500 + extra)
            result = compare_trade_in(change(self.profile, trade_in_quote=quote, loan_settlement_myr=10000 + extra))
            self.assertAlmostEqual(result['paths']['trade_in']['cash_difference_myr'], baseline + 2 * extra)


class ConsultationValidationAndCLITests(unittest.TestCase):
    def test_invalid_money_currency_and_boolean_types_rejected(self):
        for updates in [{'fees_myr': -1}, {'current_offer_myr': 'RM40000'}, {'current_offer_myr': True}, {'fees_myr': 0.001},
                        {'fees_myr': float('nan')}, {'fees_myr': float('inf')}, {'fees_myr': 1e40}, {'fees_confirmed_complete': 'true'}, {'currency': 'USD'}]:
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                NegotiationFrame.model_validate(updates)

    def invoke(self, *arguments):
        import main
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['main.py', *arguments]), redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = main.main()
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_manual_cli_tools_and_linked_valuation(self):
        code, output, _ = self.invoke('--fixture', str(ROOT/'examples/negotiation_seller.json'), '--negotiate', '--valuation-seller', str(ROOT/'examples/seller_alza.json'), '--as-of', '2026-10-15')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['suggested_counter_price_myr'], 44800)
        code, output, _ = self.invoke('--fixture', str(ROOT/'examples/trade_in_unknown_fees.json'), '--trade-in')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)['status'], 'needs_clarification')

    def test_cli_rejects_unsupported_text_and_conflicting_actions(self):
        for arguments in [('--text', 'Negotiate a car', '--negotiate'),
                          ('--fixture', 'unused.json', '--value', '--trade-in'),
                          ('--fixture', 'unused.json', '--trade-in', '--as-of', '2026-10-15'),
                          ('--fixture', 'unused.json', '--trade-in', '--valuation-seller', 'unused.json'),
                          ('--fixture', 'unused.json', '--negotiate', '--illustrative-adjustments')]:
            self.assertEqual(self.invoke(*arguments)[0], 2)


if __name__ == '__main__':
    unittest.main()
