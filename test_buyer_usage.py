"""User-reported usage regressions across source evidence, memory, forms and UI."""
from datetime import date
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from agent_controller import AgentController
from agent_grounding import apply_patch, grounded_value
from agent_state import SessionState, SlotUpdate, TurnPatch
from buyer_profile import BuyerProfileFrame
from buyer_usage import explicit_buyer_usages, parse_usage_list
from form_inputs import prepare_form
from input_grounding import ground_buyer
from test_agent import ScriptedBackend, planned, sensed, update
from ui_session import UISession

AS_OF = date(2026, 10, 15)
ROOT = Path(__file__).resolve().parent


def buyer_state():
    return SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=60000, required_seats=5,
                                                           usage=['city_commute'], fuel_priority='high'))


class BuyerUsageTests(unittest.TestCase):
    def test_reported_chat_phrase_and_normal_variants(self):
        for text in ('i want a long distance travel', 'I need long-distance driving.',
                     'I need long distance trips.', 'Road trips are my main use.'):
            with self.subTest(text=text):
                self.assertEqual([label for label, _ in explicit_buyer_usages(text)], ['long_distance'])

    def test_followup_model_omission_adds_use_without_erasing_memory(self):
        state = buyer_state()
        state.selected_vehicle_id, state.ranked_vehicle_ids = 'old', ['old']
        apply_patch(state, TurnPatch(), 'i want a long distance travel')
        self.assertEqual(state.buyer.usage, ['city_commute', 'long_distance'])
        self.assertEqual(state.buyer.budget_myr, 60000)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertEqual(state.ranked_vehicle_ids, [])
        self.assertIsNone(state.selected_vehicle_id)
        self.assertEqual(state.provenance['buyer.usage']['evidence'], 'i want a long distance travel')

    def test_model_partial_list_does_not_hide_another_explicit_use(self):
        state = buyer_state()
        text = 'Add family trips and long distance travel.'
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.usage', value=['family_travel'], evidence='family trips', operation='add')])
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.usage, ['city_commute', 'family_travel', 'long_distance'])

    def test_actual_model_copied_previous_use_does_not_reject_new_use(self):
        state = buyer_state()
        message = 'i want a long distance travel'
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.usage', value=['city_commute', 'long_distance'], evidence=message)])
        apply_patch(state, patch, message)
        self.assertEqual(state.buyer.usage, ['city_commute', 'long_distance'])
        self.assertNotIn('buyer.usage', state.issues)

    def test_copied_old_use_alone_keeps_memory_and_source_recovers_new_use(self):
        state = buyer_state()
        message = 'i want a long distance travel'
        apply_patch(state, TurnPatch(updates=[SlotUpdate(slot='buyer.usage', value=['city_commute'], evidence=message)]), message)
        self.assertEqual(state.buyer.usage, ['city_commute', 'long_distance'])
        self.assertNotIn('buyer.usage', state.issues)

    def test_only_use_replaces_even_when_model_omits_patch(self):
        state = buyer_state()
        apply_patch(state, TurnPatch(), 'Only long distance travel.')
        self.assertEqual(state.buyer.usage, ['long_distance'])

    def test_only_brand_does_not_erase_an_old_use(self):
        state = buyer_state()
        apply_patch(state, TurnPatch(), 'Only Toyota. I also need long distance travel.')
        self.assertEqual(state.buyer.usage, ['city_commute', 'long_distance'])

    def test_negated_uncertain_and_unstated_uses_are_not_added(self):
        for text in ('No long distance travel.', 'Do not use it for commuting.',
                     'Remove family trips.', 'Maybe long-distance driving.',
                     'Not sure about road trips.', 'Long distance travel is not needed.',
                     'Fuel priority is high.', 'I want travel.'):
            with self.subTest(text=text):
                self.assertEqual(explicit_buyer_usages(text), [])

    def test_removal_is_not_recovered_as_an_addition(self):
        state = buyer_state()
        state.buyer.usage.append('long_distance')
        apply_patch(state, TurnPatch(updates=[SlotUpdate(slot='buyer.usage', value=['long_distance'],
                    evidence='Remove long distance travel', operation='remove')]), 'Remove long distance travel')
        self.assertEqual(state.buyer.usage, ['city_commute'])

    def test_wrong_canonical_label_and_negated_add_need_clarification(self):
        for phrase, value in [('Save fuel.', ['long_distance']), ('long distance travel', ['family_travel']),
                              ('No long distance travel.', ['long_distance'])]:
            with self.subTest(phrase=phrase), self.assertRaises(ValueError):
                grounded_value(SlotUpdate(slot='buyer.usage', value=value, evidence=phrase), phrase, buyer_state())

    def test_human_aliases_keep_source_and_normalize_to_enums(self):
        phrase = 'long distance travel'
        value = grounded_value(SlotUpdate(slot='buyer.usage', value=[phrase], evidence=phrase), phrase, buyer_state())
        self.assertEqual(value, ['long_distance'])

    def test_form_accepts_unambiguous_aliases_and_deduplicates(self):
        state = buyer_state()
        text, patch = prepare_form('buy', {'buyer.usage': 'long distance travel, commute, city_commute'}, state)
        apply_patch(state, patch, text)
        self.assertCountEqual(state.buyer.usage, ['long_distance', 'city_commute'])

    def test_reported_ambiguous_form_has_actionable_error_and_is_atomic(self):
        state = buyer_state()
        before = state.model_dump()
        with self.assertRaisesRegex(ValueError, 'ambiguous.*Family travel or Long-distance driving'):
            prepare_form('buy', {'buyer.budget_myr': '50000', 'buyer.usage': 'travel,commute'}, state)
        self.assertEqual(state.model_dump(), before)

    def test_unknown_with_a_selected_use_is_not_a_silent_clear(self):
        with self.assertRaisesRegex(ValueError, 'Unknown by itself'):
            prepare_form('buy', {'buyer.usage': 'Unknown,City commuting'})

    def test_clear_form_is_not_repopulated_by_recovery(self):
        state = buyer_state()
        text, patch = prepare_form('buy', {'buyer.usage': 'Unknown'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.usage, [])

    def test_single_turn_extraction_recovers_partial_list(self):
        profile = ground_buyer('Budget RM60000, commuting and long distance travel.',
                               BuyerProfileFrame(usage=['city_commute']))
        self.assertEqual(profile.usage, ['city_commute', 'long_distance'])

    def test_controller_uses_real_tools_after_omitted_followup(self):
        backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(state=buyer_state(), backend=backend, as_of=AS_OF)
        result = agent.handle('i want a long distance travel')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(agent.state.buyer.usage, ['city_commute', 'long_distance'])
        self.assertTrue(result['checks'] and all(check['passed'] for check in result['checks']))

    def test_actual_ui_multiselect_replaces_uses_without_losing_budget(self):
        backend = ScriptedBackend(planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        ui = UISession(AgentController(state=buyer_state(), backend=backend, as_of=AS_OF))
        app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        app.run()
        app.multiselect(key='field_buy_0_buyer.usage').set_value(['Long-distance driving', 'Family travel'])
        next(button for button in app.button if button.label == 'Submit details to Agent').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(ui.last_response['status'], 'complete')
        self.assertCountEqual(ui.controller.state.buyer.usage, ['family_travel', 'long_distance'])
        self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)


if __name__ == '__main__':
    unittest.main()
