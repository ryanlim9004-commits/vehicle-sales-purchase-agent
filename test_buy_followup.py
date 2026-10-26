"""Buy clarification answers must resolve old issues without inventing facts."""
from datetime import date
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from agent_controller import AgentController
from agent_grounding import apply_patch, grounded_value
from agent_state import SessionState, SlotUpdate, TurnPatch
from agent_tools import requirements
from buyer_profile import BuyerProfileFrame
from buyer_usage import ambiguous_buyer_travel
from form_inputs import prepare_form
from test_agent import ScriptedBackend, planned, sensed, update
from ui_session import UISession

AS_OF = date(2026, 10, 15)
FIRST = 'I want to buy a car. i want a car with 4 seat, for travel use, comfortable, safe fuel'
SECOND = 'family travel, maximum purchase rm20000'


def state_with_usage_question():
    state = SessionState(goal='buy', buyer=BuyerProfileFrame(required_seats=4, comfort_priority='high'))
    state.issues['buyer.usage'] = 'Previous usage validation failed.'
    state.pending_slots = ['buyer.usage', 'buyer.budget_myr']
    return state


class BuyFollowupTests(unittest.TestCase):
    def test_explicit_answer_recovers_despite_old_issue_and_model_omission(self):
        state = state_with_usage_question()
        apply_patch(state, TurnPatch(updates=[SlotUpdate(slot='buyer.budget_myr', value=20000, evidence='maximum purchase rm20000')]), SECOND)
        self.assertEqual(state.buyer.usage, ['family_travel'])
        self.assertEqual(state.buyer.budget_myr, 20000)
        self.assertEqual(state.buyer.required_seats, 4)
        self.assertEqual(state.buyer.comfort_priority, 'high')
        self.assertNotIn('buyer.usage', requirements(state, AS_OF))

    def test_repeated_known_answer_also_clears_stale_issue(self):
        state = state_with_usage_question()
        state.buyer.usage = ['family_travel']
        apply_patch(state, TurnPatch(), 'family travel')
        self.assertNotIn('buyer.usage', state.issues)
        self.assertEqual(state.buyer.usage, ['family_travel'])

    def test_bad_model_label_does_not_erase_old_uses_before_source_recovery(self):
        state = state_with_usage_question()
        state.buyer.usage = ['long_distance']
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.usage', value=['city_commute'], evidence='family travel')])
        apply_patch(state, patch, 'family travel')
        self.assertEqual(state.buyer.usage, ['long_distance', 'family_travel'])
        self.assertNotIn('buyer.usage', state.issues)

    def test_negation_and_unrelated_words_do_not_resolve_a_usage_question(self):
        for message in ('Not family travel.', 'Fuel priority is high.', 'Budget RM20000.'):
            with self.subTest(message=message):
                state = state_with_usage_question()
                apply_patch(state, TurnPatch(), message)
                self.assertIn('buyer.usage', state.issues)
                self.assertEqual(state.buyer.usage, [])

    def test_bare_travel_is_remembered_with_a_targeted_question(self):
        state = SessionState(goal='buy')
        apply_patch(state, TurnPatch(), 'for travel use')
        self.assertEqual(state.buyer.usage, [])
        self.assertEqual(state.provenance['buyer.usage_pending']['evidence'], 'travel')
        self.assertIn('You mentioned travel', state.issues['buyer.usage'])
        apply_patch(state, TurnPatch(), 'family travel')
        self.assertNotIn('buyer.usage_pending', state.provenance)
        self.assertNotIn('buyer.usage', state.issues)

    def test_household_and_negated_travel_are_not_generic_use_requests(self):
        for message in ('All household members travel together.', 'No travel.', 'Do not use it for travel.'):
            self.assertIsNone(ambiguous_buyer_travel(message))

    def test_explicit_form_clears_pending_wording(self):
        state = SessionState(goal='buy')
        apply_patch(state, TurnPatch(), 'travel')
        text, patch = prepare_form('buy', {'buyer.usage': 'Unknown'}, state)
        apply_patch(state, patch, text)
        self.assertNotIn('buyer.usage_pending', state.provenance)

    def test_safe_fuel_does_not_invent_two_preferences(self):
        state = SessionState(goal='buy')
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.fuel_priority', value='high', evidence='safe fuel'),
                                  SlotUpdate(slot='buyer.safety_priority', value='high', evidence='safe fuel'),
                                  SlotUpdate(slot='buyer.comfort_priority', value='high', evidence='comfortable'),
                                  SlotUpdate(slot='buyer.required_seats', value=4, evidence='4 seat')])
        apply_patch(state, patch, FIRST)
        self.assertIsNone(state.buyer.fuel_priority)
        self.assertIsNone(state.buyer.safety_priority)
        self.assertEqual(state.buyer.comfort_priority, 'high')
        self.assertEqual(state.buyer.required_seats, 4)
        self.assertIn('buyer.fuel_safety_wording', state.issues)

    def test_unknown_budget_does_not_resolve_fuel_safety_wording(self):
        state = SessionState(goal='buy')
        apply_patch(state, TurnPatch(), 'safe fuel')
        apply_patch(state, TurnPatch(), 'My budget is unknown.')
        self.assertIn('buyer.fuel_safety_wording', state.issues)

    def test_both_can_answer_the_single_pending_choice(self):
        state = SessionState(goal='buy')
        apply_patch(state, TurnPatch(), 'safe fuel')
        state.pending_slots = ['buyer.fuel_safety_wording']
        apply_patch(state, TurnPatch(), 'Both please.')
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertEqual(state.buyer.safety_priority, 'high')
        self.assertNotIn('buyer.fuel_safety_wording', state.issues)

    def test_both_does_not_answer_several_unresolved_questions(self):
        state = state_with_usage_question()
        apply_patch(state, TurnPatch(), 'safe fuel')
        apply_patch(state, TurnPatch(), 'both')
        self.assertIsNone(state.buyer.fuel_priority)
        self.assertIsNone(state.buyer.safety_priority)
        self.assertIn('buyer.fuel_safety_wording', state.issues)

    def test_named_no_preference_clears_only_that_priority(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(safety_priority='high', fuel_priority='high'))
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.safety_priority', value=None, evidence='no safety preference')])
        apply_patch(state, patch, 'I have no safety preference.')
        self.assertIsNone(state.buyer.safety_priority)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        with self.assertRaises(ValueError):
            grounded_value(SlotUpdate(slot='buyer.fuel_priority', value=None, evidence='no safety preference'), 'no safety preference', state)

    def test_source_usage_answer_does_not_hide_foreign_currency_error(self):
        state = state_with_usage_question()
        text = 'family travel, maximum purchase USD20000'
        apply_patch(state, TurnPatch(updates=[SlotUpdate(slot='buyer.budget_myr', value=20000, evidence='maximum purchase USD20000')]), text)
        self.assertEqual(state.buyer.usage, ['family_travel'])
        self.assertIsNone(state.buyer.budget_myr)
        self.assertIn('buyer.budget_myr', requirements(state, AS_OF))

    def test_named_no_preference_accepts_invalid_model_enum_as_explicit_clear(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(safety_priority='high', fuel_priority='high'))
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.safety_priority', value='no preference', evidence='no safety preference')])
        apply_patch(state, patch, 'I have no safety preference.')
        self.assertIsNone(state.buyer.safety_priority)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertNotIn('buyer.safety_priority', state.issues)

    def test_named_no_preference_recovers_model_omission_and_old_issue(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(safety_priority='high', fuel_priority='high'))
        state.issues['buyer.safety_priority'] = 'State high, medium or low for this priority.'
        apply_patch(state, TurnPatch(), 'I have no safety preference.')
        self.assertIsNone(state.buyer.safety_priority)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertNotIn('buyer.safety_priority', state.issues)

    def test_validated_priority_form_resolves_the_same_wording_question(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=20000, required_seats=4, usage=['family_travel']))
        apply_patch(state, TurnPatch(), 'safe fuel')
        text, patch = prepare_form('buy', {'buyer.fuel_priority': 'high', 'buyer.safety_priority': 'Unknown'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertIsNone(state.buyer.safety_priority)
        self.assertNotIn('buyer.fuel_safety_wording', state.issues)
        self.assertFalse(requirements(state, AS_OF))

    def test_budget_form_does_not_resolve_an_unrelated_preference_question(self):
        state = SessionState(goal='buy')
        apply_patch(state, TurnPatch(), 'safe fuel')
        text, patch = prepare_form('buy', {'buyer.budget_myr': '20000'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.budget_myr, 20000)
        self.assertIn('buyer.fuel_safety_wording', state.issues)

    def test_full_conversation_asks_only_remaining_question_then_finishes_checked(self):
        backend = ScriptedBackend(
            sensed('buy', 'buy a car', [update('buyer.required_seats', 4, '4 seat'), update('buyer.comfort_priority', 'high', 'comfortable')]),
            planned('inspect_requirements', 'ask_user'),
            sensed(updates=[update('buyer.budget_myr', 20000, 'maximum purchase rm20000')]), planned('inspect_requirements', 'ask_user'),
            sensed(updates=[update('buyer.fuel_priority', 'high', 'save fuel'), update('buyer.safety_priority', None, 'no safety preference')]),
            planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'),
            sensed(updates=[update('buyer.budget_myr', 60000, 'budget RM60000')]), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(backend=backend, as_of=AS_OF)
        self.assertEqual(agent.handle(FIRST)['status'], 'needs_clarification')
        second = agent.handle(SECOND)
        self.assertEqual(second['status'], 'needs_clarification')
        self.assertEqual(agent.state.pending_slots, ['buyer.fuel_safety_wording'])
        self.assertEqual(agent.state.buyer.usage, ['family_travel'])
        third = agent.handle('I mean save fuel. I have no safety preference.')
        self.assertEqual(third['status'], 'complete')
        self.assertEqual(third['result']['status'], 'no_matches')
        self.assertEqual(third['result']['constraints']['maximum_price_myr'], 20000)
        self.assertEqual(third['result']['constraints']['minimum_seats'], 4)
        self.assertTrue(third['checks'] and all(check['passed'] for check in third['checks']))
        fourth = agent.handle('Change my budget RM60000.')
        self.assertEqual(fourth['status'], 'complete')
        self.assertTrue(fourth['result']['matches'])
        self.assertTrue(all(row['vehicle']['seats'] >= 4 for row in fourth['result']['matches']))

    def test_browser_pending_use_caption_disappears_after_answer(self):
        ui = UISession(AgentController(backend=ScriptedBackend(), as_of=AS_OF))
        ui.controller.state.goal = 'buy'
        apply_patch(ui.controller.state, TurnPatch(), 'travel')
        app = AppTest.from_file(str(Path(__file__).resolve().parent/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Use described: travel' in caption.value for caption in app.caption))
        apply_patch(ui.controller.state, TurnPatch(), 'family travel')
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(any('Use described: travel' in caption.value for caption in app.caption))


if __name__ == '__main__':
    unittest.main()
