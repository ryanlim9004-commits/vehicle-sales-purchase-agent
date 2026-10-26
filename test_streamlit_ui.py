"""Offline tests of form grounding, per-tab state and actual Streamlit reruns.

Only model replies are scripted. The Controller and financial/matching tools
execute their real code; live browser/model acceptance is recorded separately.
"""
from datetime import date
import json
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from agent_controller import AgentController
from agent_grounding import apply_patch
from agent_state import SessionState
from buyer_profile import BuyerProfileFrame
from form_inputs import fields_for, prepare_form
from test_agent import ScriptedBackend, planned, sensed, update
from ui_session import UISession, SNAPSHOT_DATE, source_url, verified_result, display_money, inference_lock

ROOT = Path(__file__).resolve().parent


# Build a session whose planner is controlled but whose tools are real.
def session(*actions, state=None):
    return UISession(AgentController(state=state, backend=ScriptedBackend(planned(*actions)), as_of=SNAPSHOT_DATE))


# Use exact fixture amounts as explicit user entries, never as market-price labels.
def trade_entries():
    data = json.loads((ROOT/'examples/trade_in.json').read_text(encoding='utf-8'))
    values = {}
    for field in fields_for('trade_in'):
        value = data
        for part in field.path.split('.')[1:]:
            value = value.get(part) if isinstance(value, dict) else None
        if value is not None:
            values[field.path] = ('Yes' if value else 'No') if isinstance(value, bool) else str(value)
    return values


class FormAdapterTests(unittest.TestCase):
    # Missing numeric data stays unknown; known zero has an explicit input.
    def test_blank_unknown_zero_and_strict_validation(self):
        with self.assertRaises(ValueError):
            prepare_form('buy', {'buyer.budget_myr': ''})
        for raw in ('USD50000', 'NaN', '1e9', '50000.001', '-1', '0'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                prepare_form('buy', {'buyer.budget_myr': raw})
        with self.assertRaises(ValueError):
            prepare_form('buy', {'buyer.required_seats': '5.5'})
        _, patch = prepare_form('negotiate', {'negotiation.fees_myr': '0', 'negotiation.fees_confirmed_complete': 'Unknown'})
        self.assertEqual(patch.updates[0].value, 0)
        self.assertIsNone(patch.updates[1].value)

    # The adapter cannot introduce arbitrary leaf paths or another goal's facts.
    def test_unknown_paths_choices_and_empty_lists(self):
        for values in ({'seller.brand': 'Toyota'}, {'buyer.fuel_priority': 'maximum'}, {'buyer.usage': 'flying'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                prepare_form('buy', values)
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(excluded_brands=['Toyota']))
        message, patch = prepare_form('buy', {'buyer.excluded_brands': 'Unknown'}, state)
        apply_patch(state, patch, message)
        self.assertEqual(state.buyer.excluded_brands, [])

    # Unit selection is grounded again by the existing source-text guard.
    def test_form_distance_and_history_use_existing_guards(self):
        for raw, unit, expected in [('900', 'm', .9), ('50000', 'm', 50), ('900', 'miles', 1448.4096)]:
            state = SessionState()
            message, patch = prepare_form('sell', {'seller.mileage_km': raw, 'seller.year': '2020',
                                                 'seller.major_accident_reported': 'No', 'seller.flood_damage_reported': 'Unknown'},
                                          state, mileage_unit=unit)
            apply_patch(state, patch, message)
            self.assertAlmostEqual(state.seller.mileage_km, expected)
            self.assertFalse(state.seller.major_accident_reported)
            self.assertIsNone(state.seller.flood_damage_reported)

    # Forms skip language extraction only; the planner still requests actual tools.
    def test_buy_form_runs_actual_rank_checks_and_finish(self):
        ui = session('inspect_requirements', 'rank_vehicles', 'check_result', 'finish')
        text, patch = prepare_form('buy', {'buyer.budget_myr': '60000', 'buyer.family_size': '6', 'buyer.usage': 'City commuting',
                                         'buyer.fuel_priority': 'high', 'buyer.excluded_brands': 'Toyota'})
        answer = ui.submit(text, goal='buy', form_patch=patch)
        self.assertEqual(answer['status'], 'complete')
        self.assertEqual(answer['result']['matched_count'], 3)
        self.assertTrue(verified_result(answer))
        self.assertTrue(any(item['category'] == 'input' for item in answer['trace']))
        self.assertTrue(all(request['format']['title'] == 'ToolRequest' for request in ui.controller.backend.requests))

    # A form correction keeps unmentioned preference facts and clears stale IDs.
    def test_form_patch_preserves_facts_and_explicitly_replaces_lists(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=60000, family_size=6, usage=['city_commute'],
                                                               fuel_priority='high', excluded_brands=['Toyota', 'Honda']))
        text, patch = prepare_form('buy', {'buyer.budget_myr': '35000', 'buyer.excluded_brands': 'Toyota'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.budget_myr, 35000)
        self.assertEqual(state.buyer.fuel_priority, 'high')
        self.assertEqual(state.buyer.excluded_brands, ['Toyota'])

    # Blank form inputs do not reconfirm old cash quotes for a newly named car.
    def test_identity_edit_invalidates_previous_financial_quotes(self):
        state = SessionState(goal='negotiate')
        state.negotiation.vehicle.brand = 'Perodua'
        state.negotiation.current_offer_myr = 46000
        state.negotiation.buyer_total_budget_myr = 50000
        text, patch = prepare_form('negotiate', {'negotiation.vehicle.brand': 'Toyota'}, state)
        apply_patch(state, patch, text)
        self.assertIsNone(state.negotiation.current_offer_myr)
        self.assertEqual(state.negotiation.buyer_total_budget_myr, 50000)

    # Explicit forms can resolve the household assumption without changing its size.
    def test_household_answer_preserves_true_household_count(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(family_size=6))
        text, patch = prepare_form('buy', {'buyer.required_seats': '5', 'buyer.household_travels_together': 'No'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.family_size, 6)
        self.assertEqual(state.buyer.required_seats, 5)
        self.assertFalse(state.buyer.household_travels_together)

    # Four independent packages retain their own fees and gross amounts.
    def test_trade_form_executes_actual_calculator(self):
        ui = session('inspect_requirements', 'compare_trade_in', 'check_result', 'finish')
        text, patch = prepare_form('trade_in', trade_entries())
        answer = ui.submit(text, goal='trade_in', form_patch=patch)
        self.assertEqual(answer['status'], 'complete', answer['message'])
        self.assertEqual(answer['result']['paths']['trade_in']['cash_difference_myr'], 41500)
        self.assertEqual(answer['result']['paths']['private_sale']['cash_difference_myr'], 37000)
        self.assertEqual(ui.controller.state.trade_in.trade_in_quote.price_myr, 35000)

    # Seller forms retain default reference_only, with no fabricated adjustment.
    def test_sell_form_and_negotiation_reference_link(self):
        identity = {'brand': 'Perodua', 'model': 'Alza', 'variant': '1.5 SE', 'year': '2020', 'transmission': 'Automatic'}
        ui = session('inspect_requirements', 'estimate_vehicle_value', 'check_result', 'finish')
        values = {'seller.' + key: value for key, value in identity.items()} | {'seller.mileage_km': '50000', 'seller.condition': 'fair'}
        text, patch = prepare_form('sell', values, mileage_unit='m')
        answer = ui.submit(text, goal='sell', form_patch=patch)
        self.assertEqual(answer['result']['reference']['median_asking_price_myr'], 44800)
        self.assertEqual(ui.controller.state.seller.mileage_km, 50)
        self.assertIsNone(answer['result']['adjusted_scenario'])
        ui = session('inspect_requirements', 'get_price_reference', 'advise_negotiation', 'check_result', 'finish')
        values = {'negotiation.vehicle.' + key: value for key, value in identity.items()} | {
            'negotiation.role': 'buyer', 'negotiation.current_offer_myr': '46000', 'negotiation.fees_myr': '1500',
            'negotiation.fees_confirmed_complete': 'Yes', 'negotiation.buyer_total_budget_myr': '46000'}
        text, patch = prepare_form('negotiate', values)
        answer = ui.submit(text, goal='negotiate', form_patch=patch)
        self.assertEqual(answer['status'], 'complete', answer['message'])
        self.assertEqual(answer['result']['suggested_counter_price_myr'], 44500)


class UISessionTests(unittest.TestCase):
    # Re-rendering the same request ID must not execute another consultation.
    def test_duplicate_request_and_export_are_read_only(self):
        ui = session('inspect_requirements', 'ask_user')
        text, patch = prepare_form('buy', {'buyer.fuel_priority': 'high'})
        first = ui.submit(text, goal='buy', form_patch=patch, request_id='same')
        count = len(ui.controller.backend.requests)
        self.assertEqual(ui.submit(text, goal='buy', form_patch=patch, request_id='same'), first)
        saved = json.loads(ui.export_json())
        self.assertEqual(len(ui.controller.backend.requests), count)
        self.assertEqual(saved['consultation_as_of'], '2026-10-15')
        self.assertEqual(len(saved['conversation']), 1)

    # Each tab has a distinct controller; reset clears both history and facts.
    def test_session_isolation_reset_and_failure_visibility(self):
        left, right = session('inspect_requirements', 'ask_user'), session('inspect_requirements', 'ask_user')
        text, patch = prepare_form('buy', {'buyer.budget_myr': '50000'})
        left.submit(text, goal='buy', form_patch=patch)
        self.assertIsNone(right.controller.state.goal)
        left.reset()
        self.assertEqual(left.history, [])
        self.assertIsNone(left.controller.state.goal)
        self.assertIsNone(left.last_response)
        self.assertIsNone(verified_result({'status': 'timeout', 'result': {'price': 1}, 'checks': [{'passed': True}]}))
        self.assertIsNone(verified_result({'status': 'complete', 'result': {'price': 1}, 'checks': [{'passed': False}]}))
        self.assertIsNone(verified_result({'status': 'complete', 'result': {'price': 1}, 'checks': []}))

    # Unknown money and unsafe source schemes do not turn into zeros/active links.
    def test_display_unknown_and_safe_sources(self):
        self.assertEqual(display_money(None), 'Unknown')
        self.assertEqual(display_money(0), 'MYR 0.00')
        self.assertEqual(display_money(-100), 'MYR -100.00')
        self.assertIsNone(source_url('javascript:alert(1)'))
        self.assertIsNone(source_url('file:///secret'))
        self.assertEqual(source_url('https://example.com/car'), 'https://example.com/car')


class StreamlitAppTests(unittest.TestCase):
    # Mount the actual app with a controlled planner; production has no fake backend mode.
    def mount(self, ui):
        app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        return app.run()

    # Area selection and page reruns must not run a model or mutate task facts.
    def test_initial_render_navigation_and_rerun_make_no_requests(self):
        ui = session()
        app = self.mount(ui)
        self.assertFalse(app.exception)
        app.selectbox(key='task_area').set_value('trade_in').run()
        app.run()
        self.assertFalse(app.exception)
        self.assertIsNone(ui.controller.state.goal)
        self.assertEqual(ui.controller.backend.requests, [])
        self.assertNotIn('Current-date checks', [widget.label for widget in app.selectbox])

    # A real form submission updates memory, displays cards and is not repeated on rerun.
    def test_buy_form_submit_results_and_reset(self):
        ui = session('inspect_requirements', 'rank_vehicles', 'check_result', 'finish')
        app = self.mount(ui)
        for path, value in {'buyer.budget_myr': '60000', 'buyer.family_size': '6'}.items():
            app.text_input(key='field_buy_0_' + path).set_value(value)
        app.multiselect(key='field_buy_0_buyer.usage').set_value(['City commuting'])
        next(button for button in app.button if button.label == 'Submit details to Agent').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(ui.last_response['status'], 'complete')
        self.assertEqual(sum(item.value.startswith('**MYR ') for item in app.markdown), 3)
        count = len(ui.controller.backend.requests)
        app.run()
        self.assertEqual(len(ui.controller.backend.requests), count)
        next(button for button in app.button if button.label == 'New consultation / Reset').click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(ui.controller.state.goal)
        self.assertEqual(ui.history, [])

    # Invalid numeric form entries fail locally without invoking the model.
    def test_invalid_form_and_unknown_fees_are_not_false_success(self):
        ui = session()
        app = self.mount(ui)
        app.text_input(key='field_buy_0_buyer.budget_myr').set_value('USD60000')
        next(button for button in app.button if button.label == 'Submit details to Agent').click().run()
        self.assertTrue(app.error)
        self.assertFalse(app.exception)
        self.assertEqual(ui.controller.backend.requests, [])

    # A different tab holding the real shared lock cannot drop or auto-run a draft.
    def test_busy_model_keeps_submission_until_explicit_retry(self):
        ui = session('inspect_requirements', 'ask_user')
        app = self.mount(ui)
        app.text_input(key='field_buy_0_buyer.budget_myr').set_value('60000')
        lock = inference_lock()
        self.assertTrue(lock.acquire(blocking=False))
        try:
            next(button for button in app.button if button.label == 'Submit details to Agent').click().run()
            self.assertFalse(app.exception)
            saved = app.session_state['blocked_turn']
            self.assertIn('RM60000.00', saved['text'])
            self.assertIsNone(ui.controller.state.goal)
            self.assertEqual(ui.controller.backend.requests, [])
            self.assertTrue(app.chat_input[0].disabled)
            app.button(key='retry_submission').click().run()
            self.assertEqual(app.session_state['blocked_turn']['request_id'], saved['request_id'])
            self.assertEqual(ui.controller.backend.requests, [])
        finally:
            lock.release()
        app.run()  # Becoming free alone does not execute a saved draft.
        self.assertEqual(ui.controller.backend.requests, [])
        app.button(key='retry_submission').click().run()
        self.assertFalse(app.exception)
        self.assertNotIn('blocked_turn', app.session_state)
        self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
        self.assertEqual(len(ui.history), 1)
        count = len(ui.controller.backend.requests)
        app.run()
        self.assertEqual(len(ui.controller.backend.requests), count)

    # Discard and Reset both clear a blocked draft without ever touching the model.
    def test_discard_and_reset_clear_blocked_submission(self):
        ui = session()
        app = self.mount(ui)
        lock = inference_lock()
        self.assertTrue(lock.acquire(blocking=False))
        try:
            for action in ('discard_submission', 'reset'):
                app.text_input(key=f'field_buy_{ui.generation}_buyer.budget_myr').set_value('60000')
                next(button for button in app.button if button.label == 'Submit details to Agent').click().run()
                self.assertIn('blocked_turn', app.session_state)
                if action == 'reset':
                    next(button for button in app.button if button.label == 'New consultation / Reset').click().run()
                else:
                    app.button(key=action).click().run()
                self.assertFalse(app.exception)
                self.assertNotIn('blocked_turn', app.session_state)
                self.assertFalse(app.chat_input[0].disabled)
                self.assertEqual(app.text_input(key=f'field_buy_{ui.generation}_buyer.budget_myr').value, '')
                self.assertIsNone(ui.controller.state.goal)
                self.assertEqual(ui.controller.backend.requests, [])
        finally:
            lock.release()

    # Chat uses the original model extraction path and shows canonical questions.
    def test_chat_and_four_result_renderers(self):
        backend = ScriptedBackend(sensed('buy', 'buy a car', [update('buyer.fuel_priority', 'high', 'Save fuel')]),
                                  planned('inspect_requirements', 'ask_user'))
        ui = UISession(AgentController(backend=backend, as_of=SNAPSHOT_DATE))
        app = self.mount(ui)
        app.chat_input[0].set_value('I want to buy a car. Save fuel.').run()
        self.assertFalse(app.exception)
        self.assertEqual(ui.last_response['status'], 'needs_clarification')
        self.assertEqual(ui.controller.state.buyer.fuel_priority, 'high')
        # Render saved actual-tool observations for each financial goal.
        for goal, fixture, actions in [('sell', 'seller_alza.json', ['inspect_requirements', 'estimate_vehicle_value', 'check_result', 'finish']),
                                       ('negotiate', 'negotiation_buyer.json', ['inspect_requirements', 'get_price_reference', 'advise_negotiation', 'check_result', 'finish']),
                                       ('trade_in', 'trade_in.json', ['inspect_requirements', 'compare_trade_in', 'check_result', 'finish'])]:
            with self.subTest(goal=goal):
                state = SessionState(goal=goal)
                data = json.loads((ROOT/'examples'/fixture).read_text(encoding='utf-8'))
                attr = 'seller' if goal == 'sell' else 'negotiation' if goal == 'negotiate' else 'trade_in'
                setattr(state, attr, type(getattr(state, attr)).model_validate(data))
                ui = session(*actions, state=state)
                # A validated empty patch continues existing explicitly confirmed facts.
                from agent_state import TurnPatch
                ui.submit('Please continue.', goal=goal, form_patch=TurnPatch())
                self.assertEqual(ui.last_response['status'], 'complete')
                app = self.mount(ui)
                self.assertFalse(app.exception)
                self.assertTrue(app.dataframe or app.json)
                if goal == 'sell':
                    self.assertTrue(any('MYR 35,888.00 – MYR 45,000.00' in item.value for item in app.markdown))


if __name__ == '__main__':
    unittest.main()
