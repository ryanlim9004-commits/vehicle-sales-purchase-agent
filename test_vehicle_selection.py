"""Test checked recommendation memory across Buy/Negotiation, using real tools."""
from datetime import date
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

from agent_controller import AgentController, context_for
from agent_state import SessionState, switch_goal
from agent_tools import ToolRuntime, ToolError
from buyer_profile import BuyerProfileFrame
from test_agent import ScriptedBackend, planned, sensed, update
from ui_session import UISession
from vehicle_frame import load_agent_vehicles
from vehicle_selection import resolve_selection

AS_OF = date(2026, 10, 15)
ROOT = Path(__file__).resolve().parent


def checked_buyer():
    state = SessionState(goal='buy', turn=1, buyer=BuyerProfileFrame(
        budget_myr=65000, required_seats=7, usage=['family_travel'], comfort_priority='high'))
    cars = load_agent_vehicles()
    runtime = ToolRuntime(state, cars, AS_OF)
    runtime.call('inspect_requirements', {})
    result = runtime.call('rank_vehicles', {})
    runtime.call('check_result', {})
    return state, cars, result


def quote_patch(offer=29800, budget=28800):
    return sensed(updates=[update('negotiation.role', 'buyer', 'buyer'),
                           update('negotiation.current_offer_myr', offer, f'RM{offer} excluding fees'),
                           update('negotiation.fees_myr', 1500, 'Total applicable fees are RM1500'),
                           update('negotiation.fees_confirmed_complete', True, 'All fees are complete'),
                           update('negotiation.buyer_total_budget_myr', budget, f'RM{budget}')])


def quote_message(option='option 1', offer=29800, budget=28800):
    return (f'I want to negotiate as the buyer for {option}. The seller current vehicle offer is RM{offer} excluding fees. '
            f'Total applicable fees are RM1500. All fees are complete. My maximum total purchase budget including fees is RM{budget}.')


class VehicleSelectionTests(unittest.TestCase):
    def test_numeric_and_ordinal_references_resolve_the_same_checked_order(self):
        state, cars, result = checked_buyer()
        for text, index in [('option 1', 0), ('option #2', 1), ('vehicle number 3', 2),
                            ('the first one', 0), ('the second car', 1), ('choose third', 2), ('option one', 0)]:
            with self.subTest(text=text):
                self.assertEqual(resolve_selection(state, cars, text).vehicle_id, result['matches'][index]['vehicle']['vehicle_id'])
        self.assertFalse(resolve_selection(state, cars, 'My maximum budget is RM65000; fees RM1500.').requested)

    def test_cross_goal_option_1_keeps_user_money_and_links_correct_vehicle(self):
        for area in ('buy', 'negotiate'):
            with self.subTest(area=area):
                state, cars, result = checked_buyer()
                selected = result['matches'][0]['vehicle']
                backend = ScriptedBackend(quote_patch(), planned('inspect_requirements',
                    ('select_vehicle', {'vehicle_id': selected['vehicle_id']}), 'get_price_reference',
                    'advise_negotiation', 'check_result', 'finish'))
                ui = UISession(AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF))
                answer = ui.submit(quote_message(), goal=area)
                self.assertEqual(answer['status'], 'complete', answer)
                self.assertEqual(state.selected_vehicle_id, selected['vehicle_id'])
                self.assertEqual(state.negotiation.vehicle.model, '5008')
                self.assertEqual(state.negotiation.current_offer_myr, 29800)
                self.assertIsNone(state.negotiation.asking_price_myr)
                self.assertEqual(answer['result']['suggested_counter_price_myr'], 27300)
                self.assertEqual(answer['result']['status'], 'limited_advice')
                self.assertIn('2015 Peugeot 5008 1.6 THP', answer['message'])
                self.assertTrue(all(c['passed'] for c in answer['checks']))
                selection_request = backend.requests[2]['format']
                self.assertEqual(selection_request['properties']['arguments']['properties']['vehicle_id']['enum'], [selected['vehicle_id']])

    def test_invalid_or_ambiguous_references_ask_instead_of_giving_unlinked_advice(self):
        for option in ('option 999', 'option 0', 'option 1 or 2', 'option 1 and option 2', 'that one'):
            with self.subTest(option=option):
                state, cars, _ = checked_buyer()
                backend = ScriptedBackend(quote_patch(), planned('inspect_requirements', 'ask_user'))
                answer = AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF).handle(quote_message(option))
                self.assertEqual(answer['status'], 'needs_clarification')
                self.assertIn('vehicle_selection', state.pending_slots)
                self.assertIsNone(state.selected_vehicle_id)
                self.assertIsNone(answer['result'])

    def test_no_list_and_reset_cannot_reuse_old_option(self):
        for reset in (False, True):
            state, cars, _ = checked_buyer()
            agent = AgentController(state=state, cars=cars, as_of=AS_OF)
            if reset:
                agent.handle('/reset')
            else:
                state.ranked_vehicle_ids = []
            agent.backend = ScriptedBackend(quote_patch(), planned('inspect_requirements', 'ask_user'))
            answer = agent.handle(quote_message())
            self.assertEqual(answer['status'], 'needs_clarification')
            self.assertIn('Buy consultation first', answer['message'])

    def test_wrong_candidate_id_is_rejected_even_when_it_is_in_the_list(self):
        state, cars, _ = checked_buyer()
        runtime = ToolRuntime(state, cars, AS_OF, message='choose option 1')
        runtime.call('inspect_requirements', {})
        with self.assertRaises(ToolError):
            runtime.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[1]})
        runtime.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[0]})
        self.assertEqual(state.selected_vehicle_id, state.ranked_vehicle_ids[0])

    def test_selection_happens_before_questions_about_missing_money(self):
        state, cars, _ = checked_buyer()
        backend = ScriptedBackend(sensed(), planned('inspect_requirements',
            ('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[0]}), 'ask_user'))
        answer = AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF).handle('I want to negotiate for option 1.')
        self.assertEqual(answer['status'], 'needs_clarification')
        self.assertEqual(state.negotiation.vehicle.model, '5008')
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertIsNone(state.negotiation.buyer_total_budget_myr)
        self.assertIsNone(state.negotiation.asking_price_myr)

    def test_only_checked_rankings_are_retained_as_option_memory(self):
        state, cars, _ = checked_buyer()
        runtime = ToolRuntime(state, cars, AS_OF)
        runtime.call('inspect_requirements', {})
        result = runtime.call('rank_vehicles', {})
        self.assertEqual(state.ranked_vehicle_ids, [])
        with self.assertRaises(ToolError):
            runtime.call('select_vehicle', {'vehicle_id': result['top_vehicle_ids'][0]})
        runtime.call('check_result', {})
        self.assertEqual(state.ranked_vehicle_ids[0], result['top_vehicle_ids'][0])

    def test_removed_candidate_cannot_be_selected_from_stale_order(self):
        state, cars, _ = checked_buyer()
        selected = state.ranked_vehicle_ids[0]
        resolved = resolve_selection(state, [c for c in cars if c.vehicle_id != selected], 'option 1')
        self.assertTrue(resolved.requested)
        self.assertIsNone(resolved.vehicle_id)
        self.assertIn('Buy search again', resolved.question)

    def test_changed_buyer_facts_invalidate_previous_options(self):
        state, cars, _ = checked_buyer()
        backend = ScriptedBackend(sensed(updates=[update('buyer.budget_myr', 5000, 'RM5000')]),
                                  planned('inspect_requirements', 'ask_user'))
        answer = AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF).handle('Choose option 1. My budget is RM5000.')
        self.assertEqual(answer['status'], 'needs_clarification')
        self.assertEqual(state.ranked_vehicle_ids, [])
        self.assertIsNone(state.selected_vehicle_id)

    def test_negated_option_does_not_override_positive_choice(self):
        state, cars, _ = checked_buyer()
        self.assertFalse(resolve_selection(state, cars, 'Not option 1.').requested)
        self.assertEqual(resolve_selection(state, cars, 'Not option 1; choose option 2.').vehicle_id, state.ranked_vehicle_ids[1])

    def test_switch_after_selection_preserves_exact_mileage_but_clears_quotes(self):
        state, cars, _ = checked_buyer()
        # Use the same validated record with a controlled exact odometer, not
        # the range's midpoint. No production dataset is changed.
        selected = next(c for c in cars if c.vehicle_id == state.ranked_vehicle_ids[0])
        selected.mileage_km = 137000
        runtime = ToolRuntime(state, cars, AS_OF)
        runtime.call('inspect_requirements', {})
        runtime.call('select_vehicle', {'vehicle_id': selected.vehicle_id})
        state.negotiation.current_offer_myr = 12345
        switch_goal(state, 'negotiate')
        self.assertEqual(state.negotiation.mileage_km, 137000)
        self.assertIsNone(state.negotiation.current_offer_myr)

    def test_option_numbers_are_explicit_in_model_context(self):
        state, cars, _ = checked_buyer()
        context = context_for(state, cars)
        self.assertEqual([c['option_number'] for c in context['previously_ranked_candidates']], [1, 2, 3, 4, 5])

    def test_planner_cannot_skip_the_requested_selection(self):
        state, cars, _ = checked_buyer()
        switch_goal(state, 'negotiate')
        runtime = ToolRuntime(state, cars, AS_OF, message='option 1')
        runtime.call('inspect_requirements', {})
        with self.assertRaises(ToolError):
            runtime.call('advise_negotiation', {})
        with self.assertRaises(ToolError):
            runtime.call('ask_user', {})

    def test_explicit_identity_conflict_needs_clarification(self):
        state, cars, _ = checked_buyer()
        backend = ScriptedBackend(sensed(updates=[update('negotiation.vehicle.brand', 'Toyota', 'Toyota')]),
                                  planned('inspect_requirements', 'ask_user'))
        answer = AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF).handle('I want to negotiate for option 1, a Toyota.')
        self.assertEqual(answer['status'], 'needs_clarification')
        self.assertIn('does not match the brand', answer['message'])
        self.assertIsNone(state.selected_vehicle_id)

    def test_reselecting_another_car_clears_old_quotes_and_damage(self):
        state, cars, _ = checked_buyer()
        switch_goal(state, 'negotiate')
        first = ToolRuntime(state, cars, AS_OF, message='option 1')
        first.call('inspect_requirements', {})
        first.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[0]})
        state.negotiation.current_offer_myr = 29800
        state.negotiation.fees_myr = 1500
        state.negotiation.fees_confirmed_complete = True
        state.negotiation.major_accident_reported = True
        state.negotiation.buyer_total_budget_myr = 70000
        state.turn += 1
        second = ToolRuntime(state, cars, AS_OF, message='option 2')
        second.call('inspect_requirements', {})
        second.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[1]})
        self.assertEqual(state.negotiation.vehicle.model, 'Alza')
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertIsNone(state.negotiation.fees_myr)
        self.assertIsNone(state.negotiation.fees_confirmed_complete)
        self.assertIsNone(state.negotiation.major_accident_reported)
        self.assertEqual(state.negotiation.buyer_total_budget_myr, 70000)

    def test_streamlit_results_navigation_and_area_switch_keep_recommendations(self):
        for area in ('buy', 'negotiate'):
            with self.subTest(area=area):
                state, cars, ranking = checked_buyer()
                selected = state.ranked_vehicle_ids[0]
                backend = ScriptedBackend(quote_patch(), planned('inspect_requirements',
                    ('select_vehicle', {'vehicle_id': selected}), 'get_price_reference',
                    'advise_negotiation', 'check_result', 'finish'))
                ui = UISession(AgentController(state=state, cars=cars, backend=backend, as_of=AS_OF))
                app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
                app.session_state['ui_session'] = ui
                app.run()
                before = list(state.ranked_vehicle_ids)
                app.button(key='nav_results').click().run()
                app.button(key='nav_consultation').click().run()
                app.selectbox(key='task_area').set_value(area).run()
                self.assertEqual(state.ranked_vehicle_ids, before)
                self.assertEqual(state.goal, 'buy')
                self.assertFalse(backend.requests)
                app.chat_input[0].set_value(quote_message()).run()
                if ui.active_turn:
                    self.assertTrue(ui.active_turn.done.wait(2))
                    app.run()
                self.assertFalse(app.exception)
                self.assertEqual(ui.last_response['status'], 'complete')
                self.assertEqual(ui.controller.state.selected_vehicle_id, selected)
                self.assertIn('2015 Peugeot 5008', ui.last_response['message'])

    def test_different_listing_of_same_variant_is_new_car_but_same_listing_keeps_odometer(self):
        state, cars, result = checked_buyer()
        self.assertEqual(result['matches'][2]['vehicle']['variant'], result['matches'][3]['vehicle']['variant'])
        switch_goal(state, 'negotiate')
        runtime = ToolRuntime(state, cars, AS_OF, message='option 3')
        runtime.call('inspect_requirements', {})
        runtime.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[2]})
        state.negotiation.current_offer_myr = 40000
        state.negotiation.mileage_km = 66000
        state.provenance['negotiation.mileage_km'] = {'turn': state.turn, 'source': 'current user message'}
        state.turn += 1
        same = ToolRuntime(state, cars, AS_OF, message='option 3')
        same.call('inspect_requirements', {})
        same.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[2]})
        self.assertEqual(state.negotiation.current_offer_myr, 40000)
        self.assertEqual(state.negotiation.mileage_km, 66000)
        state.turn += 1
        other = ToolRuntime(state, cars, AS_OF, message='option 4')
        other.call('inspect_requirements', {})
        other.call('select_vehicle', {'vehicle_id': state.ranked_vehicle_ids[3]})
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertIsNone(state.negotiation.mileage_km)


if __name__ == '__main__':
    unittest.main()
