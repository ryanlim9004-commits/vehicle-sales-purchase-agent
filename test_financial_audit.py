"""Financial meaning and multi-turn contracts, not market accuracy tests."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import unittest

from agent_grounding import apply_patch
from agent_state import SessionState, TurnPatch
from agent_tools import requirements, verify_observation, ToolRuntime
from consultation_frames import NegotiationFrame, TradeInFrame
from negotiation import advise_negotiation
from trade_in import compare_trade_in
from seller_profile import SellerVehicleFrame
from valuation import estimate_vehicle_value
from vehicle_frame import load_agent_vehicles

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def fixture(name, cls):
    return cls.model_validate_json((ROOT/'examples'/name).read_text())


def patch(state, message, *changes):
    state.turn += 1
    apply_patch(state, TurnPatch.model_validate({'updates': [
        {'slot': slot, 'value': value, 'evidence': evidence} for slot, value, evidence in changes]}), message)


class FinancialAuditTests(unittest.TestCase):
    def buyer(self):
        return SessionState(goal='negotiate', negotiation=fixture('negotiation_buyer.json', NegotiationFrame))

    def trade(self):
        return SessionState(goal='trade_in', trade_in=fixture('trade_in.json', TradeInFrame))

    def test_updated_fee_or_other_party_offer_requires_new_fee_confirmation(self):
        for field, value, text in [('fees_myr', 2500., 'The applicable fee total is RM2500.'),
                                   ('current_offer_myr', 48000., 'The seller current offer is RM48000 excluding fees.')]:
            state = self.buyer()
            patch(state, text, ('negotiation.' + field, value, text))
            self.assertIsNone(state.negotiation.fees_confirmed_complete)
            self.assertIn('negotiation.fees_confirmed_complete', requirements(state, AS_OF))

    def test_explicit_same_turn_complete_fees_allow_updated_quote(self):
        state = self.buyer()
        message = 'The seller current offer is RM48000 excluding fees. Fees are RM2500. All fees are complete.'
        patch(state, message,
              ('negotiation.current_offer_myr', 48000., 'seller current offer is RM48000 excluding fees'),
              ('negotiation.fees_myr', 2500., 'Fees are RM2500'))
        self.assertTrue(state.negotiation.fees_confirmed_complete)
        self.assertEqual(state.negotiation.current_offer_myr, 48000.)

    def test_trade_quote_refresh_invalidates_only_its_own_fee_confirmation(self):
        state = self.trade()
        message = 'The trade-in disposal gross offer is RM37000.'
        patch(state, message)
        self.assertEqual(state.trade_in.trade_in_quote.price_myr, 37000.)
        self.assertIsNone(state.trade_in.trade_in_quote.fees_confirmed_complete)
        self.assertTrue(state.trade_in.private_sale_quote.fees_confirmed_complete)
        self.assertTrue(state.trade_in.trade_in_replacement.fees_confirmed_complete)

    def test_changing_buyer_seller_role_cannot_reuse_opponent_offer_or_fee_scope(self):
        state = self.buyer()
        patch(state, 'I am now the seller.', ('negotiation.role', 'seller', 'seller'))
        self.assertEqual(state.negotiation.role, 'seller')
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertIsNone(state.negotiation.fees_myr)
        self.assertIsNone(state.negotiation.asking_price_myr)
        self.assertEqual(state.negotiation.vehicle.model, 'Alza')

    def test_inclusive_negotiation_offer_is_not_treated_as_bare_vehicle_price(self):
        state = self.buyer()
        text = 'The seller current offer is RM45000 including all fees.'
        patch(state, text, ('negotiation.current_offer_myr', 45000., text))
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertIn('negotiation.current_offer_myr', state.issues)

    def test_all_in_trade_replacement_price_does_not_get_fees_added_twice(self):
        state = self.trade()
        patch(state, 'The trade-in replacement price is RM66000 including all fees.')
        self.assertIsNone(state.trade_in.trade_in_replacement.price_myr)
        self.assertIn('trade_in.trade_in_replacement.price_myr', state.issues)

    def test_net_disposal_proceeds_do_not_get_loan_subtracted_twice(self):
        state = self.trade()
        patch(state, 'The trade-in disposal net proceeds are RM24500 after fees and loan settlement.')
        self.assertIsNone(state.trade_in.trade_in_quote.price_myr)
        self.assertIn('trade_in.trade_in_quote.price_myr', state.issues)

    def test_withdrawn_fee_completeness_is_honoured_even_if_model_omits_it(self):
        for goal, state in [('negotiate', self.buyer()), ('trade_in', self.trade())]:
            patch(state, 'All fees are unknown.')
            if goal == 'negotiate':
                self.assertIsNot(state.negotiation.fees_confirmed_complete, True)
            else:
                self.assertTrue(all(getattr(state.trade_in, name).fees_confirmed_complete is not True for name in
                                    ('trade_in_quote', 'private_sale_quote', 'trade_in_replacement', 'private_sale_replacement')))
            self.assertTrue(requirements(state, AS_OF))

    def test_unknown_or_excluded_insurance_revokes_prior_complete_total(self):
        for text in ('All fees are complete, except insurance which is unknown.',
                     'The applicable fees are RM1500 excluding insurance.'):
            state = self.buyer()
            patch(state, text)
            self.assertIsNot(state.negotiation.fees_confirmed_complete, True)
            self.assertIn('negotiation.fees_confirmed_complete', requirements(state, AS_OF))

    def test_direct_current_vehicle_flood_report_cannot_produce_ordinary_advice(self):
        for goal, state in [('negotiate', self.buyer()), ('trade_in', self.trade())]:
            with self.subTest(goal=goal):
                patch(state, 'The current vehicle has flood damage.')
                profile = state.negotiation if goal == 'negotiate' else state.trade_in
                self.assertIs(getattr(profile, 'flood_damage_reported', None), True)
                result = advise_negotiation(profile, as_of=AS_OF) if goal == 'negotiate' else compare_trade_in(profile)
                self.assertEqual(result['status'], 'inspection_required')
                if goal == 'negotiate':
                    self.assertIsNone(result['suggested_counter_price_myr'])
                else:
                    self.assertEqual(result['paths'], {})

    def test_requested_speed_or_effort_asks_for_missing_estimates(self):
        for priority, field in [('speed', 'estimated_completion_days'), ('effort', 'estimated_effort_hours')]:
            p = self.trade().trade_in
            p.priority = priority
            setattr(p.trade_in_quote, field, None)
            setattr(p.private_sale_quote, field, None)
            result = compare_trade_in(p)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertIsNone(result['suggested_path'])
            self.assertIn('trade_in.trade_in_quote.' + field, result['missing_slots'])
            self.assertIn('trade_in.private_sale_quote.' + field, result['missing_slots'])
            self.assertIsNotNone(result['comparison'])  # Known money is still visible.

    def test_in_budget_counter_tampering_and_suboptimal_trade_selection_fail_checks(self):
        cars = load_agent_vehicles()
        state = self.buyer()
        seller = fixture('seller_alza.json', SellerVehicleFrame)
        reference = estimate_vehicle_value(seller, cars, as_of=AS_OF)
        result = advise_negotiation(state.negotiation, as_of=AS_OF, valuation_result=reference)
        self.assertTrue(all(c['passed'] for c in verify_observation('advise_negotiation', result, state, cars, AS_OF)))
        bad = deepcopy(result)
        bad['suggested_counter_price_myr'] -= 100
        self.assertFalse(all(c['passed'] for c in verify_observation('advise_negotiation', bad, state, cars, AS_OF)))
        state = self.trade()
        result = compare_trade_in(state.trade_in)
        self.assertEqual(result['suggested_path'], 'private_sale')
        result['suggested_path'] = 'trade_in'  # Affordable, but not the stated lowest-cost choice.
        self.assertFalse(all(c['passed'] for c in verify_observation('compare_trade_in', result, state, cars, AS_OF)))

    def test_inclusive_basis_is_checked_against_original_clause_not_only_short_evidence(self):
        state = self.buyer()
        text = 'The seller current offer is RM45000 including all fees.'
        patch(state, text, ('negotiation.current_offer_myr', 45000., 'RM45000'))
        self.assertIsNone(state.negotiation.current_offer_myr)

    def test_one_named_fee_package_does_not_confirm_all_four(self):
        state = self.trade()
        for name in ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote'):
            getattr(state.trade_in, name).fees_confirmed_complete = None
        patch(state, 'The private-sale replacement all fees are complete.')
        self.assertTrue(state.trade_in.private_sale_replacement.fees_confirmed_complete)
        self.assertIsNone(state.trade_in.trade_in_replacement.fees_confirmed_complete)
        self.assertIsNone(state.trade_in.trade_in_quote.fees_confirmed_complete)
        self.assertIsNone(state.trade_in.private_sale_quote.fees_confirmed_complete)

    def test_model_cannot_apply_a_private_sale_fee_confirmation_to_trade_in(self):
        state = self.trade()
        state.trade_in.trade_in_quote.fees_confirmed_complete = None
        text = 'The private-sale disposal fees are confirmed complete.'
        patch(state, text, ('trade_in.trade_in_quote.fees_confirmed_complete', True, text))
        self.assertIsNone(state.trade_in.trade_in_quote.fees_confirmed_complete)
        self.assertIn('trade_in.trade_in_quote.fees_confirmed_complete', state.issues)

    def test_timing_path_and_units_cannot_be_swapped_by_model(self):
        cases = [('trade_in.trade_in_quote.estimated_completion_days', 21., 'Private-sale completion is 21 days.'),
                 ('trade_in.trade_in_quote.estimated_completion_days', 2., 'Trade-in completion is 2 hours.'),
                 ('trade_in.private_sale_quote.estimated_effort_hours', 3., 'Private-sale effort is 3 days.')]
        for slot, value, text in cases:
            with self.subTest(slot=slot, text=text):
                state = self.trade()
                patch(state, text, (slot, value, text))
                self.assertIn(slot, state.issues)
                self.assertIsNone(getattr(getattr(state.trade_in, slot.split('.')[1]), slot.split('.')[2]))

    def test_missing_speed_estimates_are_named_pending_slots_in_agent_runtime(self):
        state = self.trade()
        state.trade_in.priority = 'speed'
        state.trade_in.trade_in_quote.estimated_completion_days = None
        state.trade_in.private_sale_quote.estimated_completion_days = None
        runtime = ToolRuntime(state, load_agent_vehicles(), AS_OF)
        runtime.call('inspect_requirements', {})
        runtime.call('compare_trade_in', {})
        self.assertEqual(runtime.available_tools('Continue'), ['ask_user'])
        questions = runtime.call('ask_user', {})['questions']
        self.assertEqual(set(state.pending_slots), {'trade_in.trade_in_quote.estimated_completion_days', 'trade_in.private_sale_quote.estimated_completion_days'})
        self.assertTrue(all('days' in q and 'e.g.' in q for q in questions))

    def test_direct_damage_completes_inspection_path_without_made_up_fees_or_identity(self):
        for goal in ('negotiate', 'trade_in'):
            state = SessionState(goal=goal)
            patch(state, 'The current vehicle has flood damage.')
            self.assertEqual(requirements(state, AS_OF), {})
            runtime = ToolRuntime(state, load_agent_vehicles(), AS_OF)
            runtime.call('inspect_requirements', {})
            tool = 'advise_negotiation' if goal == 'negotiate' else 'compare_trade_in'
            self.assertEqual(runtime.call(tool, {})['status'], 'inspection_required')
            self.assertTrue(runtime.call('check_result', {})['passed'])
            self.assertEqual(runtime.call('finish', {})['status'], 'complete')

    def test_conflicting_or_hypothetical_history_never_silently_becomes_clean(self):
        state = self.buyer()
        patch(state, 'The vehicle had flood damage. No flood damage.')
        self.assertIn('negotiation.flood_damage_reported', state.issues)
        self.assertIsNone(state.negotiation.flood_damage_reported)
        state = self.buyer()
        patch(state, 'What if the vehicle had flood damage?')
        self.assertIsNone(state.negotiation.flood_damage_reported)

    def test_minor_or_unspecified_accident_requires_severity_clarification(self):
        state = self.buyer()
        patch(state, 'The current vehicle had a minor accident.')
        self.assertIsNone(state.negotiation.major_accident_reported)
        self.assertIn('negotiation.major_accident_reported', state.issues)
        patch(state, 'No major accident.')
        self.assertFalse(state.negotiation.major_accident_reported)
        self.assertNotIn('negotiation.major_accident_reported', state.issues)

    def test_legacy_saved_seller_damage_handoff_cannot_deadlock_on_price_lookup(self):
        state = self.buyer()
        state.seller = fixture('seller_alza.json', SellerVehicleFrame)
        state.seller.flood_damage_reported = True
        state.negotiation_from_seller = True
        self.assertIsNone(state.negotiation.flood_damage_reported)
        runtime = ToolRuntime(state, load_agent_vehicles(), AS_OF)
        self.assertTrue(state.negotiation.flood_damage_reported)
        runtime.call('inspect_requirements', {})
        self.assertEqual(runtime.call('advise_negotiation', {})['status'], 'inspection_required')
        self.assertTrue(runtime.call('check_result', {})['passed'])


if __name__ == '__main__':
    unittest.main()
