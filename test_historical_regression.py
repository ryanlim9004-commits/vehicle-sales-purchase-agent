"""Historical development/engineering checks; not independent market accuracy."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest
from agent_controller import AgentController
from agent_grounding import apply_patch
from agent_state import SessionState, TurnPatch, switch_goal
from agent_tools import ToolRuntime, verify_observation
from consultation_frames import NegotiationFrame, TradeInFrame
from form_inputs import prepare_form
from historical_price_regression import (ARTIFACT, POLICY, prepare_rows, fit, predict_rows,
                                         load_artifact, estimate, verify_prediction)
from negotiation import advise_negotiation
from seller_profile import SellerVehicleFrame
from test_agent import ScriptedBackend, sensed, planned
from trade_in import compare_trade_in
from valuation import estimate_vehicle_value
from vehicle_frame import load_agent_vehicles

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def seller(**updates):
    values = dict(brand='Toyota', model='Alphard', variant='2.5 G S C Package', year=2018,
                  transmission='Automatic', mileage_km=65000., condition='good',
                  major_accident_reported=False, flood_damage_reported=False)
    return SellerVehicleFrame.model_validate(values | updates)


def identity(profile):
    return {k: getattr(profile, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}


class HistoricalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cars = load_agent_vehicles()

    def test_combined_training_preserves_unknowns_and_conservative_groups(self):
        rows, excluded = prepare_rows(self.cars)
        self.assertEqual(len(rows), 111)
        self.assertEqual(len({r['group_id'] for r in rows}), 111)
        self.assertEqual(sum(r['provenance'] == 'historical_simulation' for r in rows), 95)
        self.assertEqual(len(excluded), 3)
        self.assertTrue(all(r['observed_on'] is None for r in rows if r['provenance'] == 'historical_simulation'))
        self.assertTrue(any(r['mileage_min_km'] != r['mileage_proxy_km'] for r in rows))
        self.assertTrue(all(c.mileage_km is None for c in self.cars if c.simulation and c.mileage_min_km != c.mileage_max_km))

    def test_holdout_has_no_fitted_target_or_transform_leakage(self):
        artifact = load_artifact(self.cars)
        held = next(r for r in artifact['training_rows'] if r['row_id'] == 'SIM-MRC-V1-0033')
        training = [r for r in artifact['training_rows'] if r['group_id'] != held['group_id']]
        spec, coef = fit(training)
        observation = next(r for r in artifact['model_evaluation']['toyota|alphard|automatic']['predictions'] if r['row_id'] == held['row_id'])
        self.assertAlmostEqual(float(predict_rows([held], spec, coef)[0]), observation['prediction_myr'])
        before = json.dumps(spec)
        changed = held | {'price_myr': 999999., 'mileage_proxy_km': 999999.}
        predict_rows([changed], spec, coef)
        self.assertEqual(json.dumps(spec), before)
        self.assertNotIn(held['group_id'], {r['group_id'] for r in training})

    def test_per_model_failures_remain_disabled(self):
        result = load_artifact(self.cars)
        eligible = {k for k, v in result['model_evaluation'].items() if v['eligible_for_historical_demo']}
        self.assertEqual(eligible, {'toyota|alphard|automatic', 'toyota|harrier|automatic'})
        self.assertFalse(result['model_evaluation']['perodua|alza|automatic']['eligible_for_historical_demo'])
        self.assertIsNone(estimate(seller(brand='Perodua', model='Alza', variant='1.5 AV', year=2023), self.cars)['estimated_asking_price_myr'])

    def test_no_unseen_model_variant_or_out_of_range_extrapolation(self):
        for changes in ({'model': 'Never seen'}, {'variant': 'Never seen'}, {'year': 2024},
                        {'year': 2014}, {'mileage_km': 1000000.}, {'transmission': 'Manual'}):
            with self.subTest(changes=changes):
                outcome = estimate(seller(**changes), self.cars)
                self.assertEqual(outcome['status'], 'unavailable')
                self.assertIsNone(outcome['estimated_asking_price_myr'])
        outcome = estimate(seller(mileage_km=None), self.cars)
        self.assertTrue(outcome['needs_mileage'])

    def test_catalogue_change_or_model_edit_requires_retraining(self):
        cars = deepcopy(self.cars)
        cars[0].price_myr += 1
        self.assertIsNone(load_artifact(cars))
        data = json.loads(ARTIFACT.read_text())
        data['coefficients'][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'edited.json'
            path.write_text(json.dumps(data))
            self.assertIsNone(load_artifact(self.cars, path))

    def test_prediction_can_interpolate_absent_year_and_reject_tampering(self):
        self.assertFalse(any(c.model == 'Alphard' and c.variant == seller().variant and c.year == 2018 for c in self.cars))
        prediction = estimate(seller(), self.cars)
        self.assertEqual(prediction['status'], 'historical_prediction')
        self.assertFalse(prediction['market_validated'])
        self.assertTrue(verify_prediction(prediction, self.cars))
        changed = deepcopy(prediction)
        changed['estimated_asking_price_myr'] += 1
        self.assertFalse(verify_prediction(changed, self.cars))

    def test_exact_reference_keeps_priority_and_damage_still_stops(self):
        profile = SellerVehicleFrame.model_validate_json((ROOT/'examples/seller_alza.json').read_text())
        exact = estimate_vehicle_value(profile, self.cars, as_of=AS_OF)
        self.assertEqual(exact['status'], 'reference_only')
        self.assertNotIn('historical_regression', exact)
        damaged = estimate_vehicle_value(seller(flood_damage_reported=True), self.cars, as_of=AS_OF)
        self.assertEqual(damaged['status'], 'inspection_required')
        self.assertNotIn('historical_regression', damaged)

    def test_sell_controller_executes_real_fallback_and_checks(self):
        backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'estimate_vehicle_value', 'check_result', 'finish'))
        state = SessionState(goal='sell', seller=seller())
        result = AgentController(state=state, backend=backend, as_of=AS_OF).handle('Please estimate my vehicle.')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['result']['status'], 'historical_reference')
        self.assertIn('Historical regression reference', result['message'])
        self.assertTrue(all(c['passed'] for c in result['checks']))
        bad = deepcopy(result['result'])
        bad['historical_regression']['estimated_asking_price_myr'] += 1
        self.assertFalse(all(c['passed'] for c in verify_observation('estimate_vehicle_value', bad, state, self.cars, AS_OF)))

    def negotiation(self, **updates):
        return NegotiationFrame.model_validate(dict(vehicle=identity(seller()), mileage_km=65000., role='buyer',
                                                    current_offer_myr=230000., fees_myr=1000., fees_confirmed_complete=True,
                                                    buyer_total_budget_myr=300000.) | updates)

    def test_buyer_model_anchor_respects_budget_and_never_becomes_market_range(self):
        valuation = estimate_vehicle_value(seller(), self.cars, as_of=AS_OF)
        for budget in (300000., 180000.):
            profile = self.negotiation(buyer_total_budget_myr=budget)
            result = advise_negotiation(profile, as_of=AS_OF, valuation_result=valuation)
            self.assertEqual(result['status'], 'historical_advice')
            self.assertEqual(result['price_position'], 'not_assessed')
            self.assertIsNone(result['valuation_evidence']['reference'])
            self.assertLessEqual(result['suggested_counter_price_myr'] + profile.fees_myr, budget)
            state = SessionState(goal='negotiate', negotiation=profile)
            self.assertTrue(all(c['passed'] for c in verify_observation('advise_negotiation', result, state, self.cars, AS_OF)))
            result['suggested_counter_price_myr'] -= 100
            self.assertFalse(all(c['passed'] for c in verify_observation('advise_negotiation', result, state, self.cars, AS_OF)))

    def test_seller_counter_covers_loan_fees_and_net_reserve(self):
        profile = self.negotiation(role='seller', current_offer_myr=150000., seller_minimum_net_myr=160000., loan_settlement_myr=10000.)
        valuation = estimate_vehicle_value(seller(), self.cars, as_of=AS_OF)
        result = advise_negotiation(profile, as_of=AS_OF, valuation_result=valuation)
        self.assertGreaterEqual(result['suggested_counter_price_myr'] - 1000 - 10000, 160000)
        self.assertEqual(result['status'], 'historical_advice')

    def test_link_rejects_valid_prediction_for_wrong_input(self):
        valuation = estimate_vehicle_value(seller(), self.cars, as_of=AS_OF)
        changed = deepcopy(valuation)
        changed['historical_regression'] = estimate(seller(mileage_km=70000.), self.cars)
        result = advise_negotiation(self.negotiation(), as_of=AS_OF, valuation_result=changed)
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertIsNone(result['suggested_counter_price_myr'])

    def test_trade_model_context_never_replaces_actual_quotes(self):
        data = json.loads((ROOT/'examples/trade_in.json').read_text())
        profile = TradeInFrame.model_validate(data | {'current_vehicle': identity(seller()), 'mileage_km': 65000.})
        valuation = estimate_vehicle_value(seller(), self.cars, as_of=AS_OF)
        plain = compare_trade_in(profile)
        result = compare_trade_in(profile, valuation_result=valuation, as_of=AS_OF)
        self.assertEqual(result['paths'], plain['paths'])
        self.assertEqual(result['comparison'], plain['comparison'])
        self.assertIsNotNone(result['historical_quote_context'])
        state = SessionState(goal='trade_in', trade_in=profile)
        self.assertTrue(all(c['passed'] for c in verify_observation('compare_trade_in', result, state, self.cars, AS_OF)))
        profile.private_sale_quote.price_myr = None
        self.assertEqual(compare_trade_in(profile, valuation_result=valuation, as_of=AS_OF)['status'], 'needs_clarification')

    def test_reference_asks_mileage_once_and_unknown_allows_limited_advice(self):
        state = SessionState(goal='negotiate', negotiation=self.negotiation(mileage_km=None))
        runtime = ToolRuntime(state, self.cars, AS_OF)
        runtime.call('inspect_requirements', {})
        runtime.call('get_price_reference', {})
        self.assertEqual(runtime.available_tools('Continue.'), ['ask_user'])
        runtime.call('ask_user', {})
        text, patch = prepare_form('negotiate', {'negotiation.mileage_km': 'Unknown'}, state)
        apply_patch(state, patch, text)
        runtime = ToolRuntime(state, self.cars, AS_OF)
        runtime.call('inspect_requirements', {})
        runtime.call('get_price_reference', {})
        self.assertFalse(runtime.pending)
        self.assertEqual(runtime.call('advise_negotiation', {})['status'], 'limited_advice')

    def test_odometer_units_handoff_and_changed_identity(self):
        for goal, slot in [('negotiate', 'negotiation.mileage_km'), ('trade_in', 'trade_in.mileage_km')]:
            state = SessionState(goal=goal)
            text, patch = prepare_form(goal, {slot: '900'}, state, mileage_unit='m')
            apply_patch(state, patch, text)
            self.assertEqual(getattr(state, slot.split('.')[0]).mileage_km, .9)
        state = SessionState(goal='sell', seller=seller())
        switch_goal(state, 'negotiate')
        self.assertEqual(state.negotiation.mileage_km, 65000.)
        state.turn += 1
        text, patch = prepare_form('negotiate', {'negotiation.vehicle.model': 'Harrier'}, state)
        apply_patch(state, patch, text)
        self.assertIsNone(state.negotiation.mileage_km)

    def test_direct_odometer_reply_survives_model_omission_without_using_replacement(self):
        state = SessionState(goal='negotiate', negotiation=self.negotiation(mileage_km=None),
                             pending_slots=['negotiation.mileage_km'])
        apply_patch(state, TurnPatch(), '65000 km')
        self.assertEqual(state.negotiation.mileage_km, 65000.)
        state = SessionState(goal='negotiate', pending_slots=['negotiation.mileage_km'])
        apply_patch(state, TurnPatch(), 'Unknown')
        self.assertIn('negotiation.mileage_km', state.provenance)
        state = SessionState(goal='trade_in', pending_slots=['trade_in.mileage_km'])
        apply_patch(state, TurnPatch(), 'The replacement car odometer is 20000 km.')
        self.assertIsNone(state.trade_in.mileage_km)
        patch = TurnPatch.model_validate({'updates': [{'slot': 'trade_in.mileage_km', 'value': 20000.,
                                                      'evidence': 'The replacement car odometer is 20000 km.'}]})
        apply_patch(state, patch, 'The replacement car odometer is 20000 km.')
        self.assertIsNone(state.trade_in.mileage_km)
        self.assertIn('trade_in.mileage_km', state.issues)

    def test_actual_streamlit_render_labels_all_three_historical_outputs(self):
        valuation = estimate_vehicle_value(seller(), self.cars, as_of=AS_OF)
        profile = self.negotiation()
        negotiation = advise_negotiation(profile, as_of=AS_OF, valuation_result=valuation)
        trade = TradeInFrame.model_validate(json.loads((ROOT/'examples/trade_in.json').read_text()) |
                                            {'current_vehicle': identity(seller()), 'mileage_km': 65000.})
        outputs = [('render_value', valuation), ('render_negotiation', negotiation),
                   ('render_trade', compare_trade_in(trade, valuation_result=valuation, as_of=AS_OF))]
        for function, value in outputs:
            with self.subTest(function=function):
                app = AppTest.from_string(f'from streamlit_app import {function}\nimport streamlit as st\n{function}(st.session_state.result)')
                app.session_state.result = value
                app.run()
                self.assertFalse(app.exception)
                self.assertIn('Historical regression reference', '\n'.join(m.value for m in app.markdown))
                self.assertTrue(any('Not current market value' in c.value for c in app.caption))


if __name__ == '__main__':
    unittest.main()
