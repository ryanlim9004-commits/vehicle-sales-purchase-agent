"""Question guidance must match the real catalogue and never become user facts."""
from datetime import date
from copy import deepcopy
import unittest

from streamlit.testing.v1 import AppTest
from agent_controller import AgentController
from agent_state import SessionState
from agent_tools import ToolRuntime, requirements
from form_inputs import fields_for, parse_number
from question_examples import (catalogue_choices, example_for, guided_question, guided_questions,
                               catalogue_notice, form_guidance, identity_frame)
from seller_profile import SellerVehicleFrame
from test_agent import ScriptedBackend, sensed, planned, update
from ui_session import UISession
from vehicle_frame import load_agent_vehicles

AS_OF = date(2026, 10, 15)
MESSAGES = {'sell': 'I want to sell a car.', 'negotiate': 'I want to negotiate.',
            'trade_in': 'I want to compare trade-in with private sale.'}


class QuestionExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cars = load_agent_vehicles()

    def test_initial_question_examples_are_parent_qualified_and_read_only(self):
        state = SessionState(goal='sell')
        before = state.model_dump()
        pending = requirements(state, AS_OF)
        questions = guided_questions(pending, state, self.cars)
        self.assertIn('e.g. Perodua, Toyota', questions[0])
        self.assertIn('Alza [Perodua]', questions[1])
        self.assertIn('1.5 SE [Perodua Alza]', questions[2])
        for value in catalogue_choices('brand', state, self.cars):
            self.assertTrue(any(car.brand == value for car in self.cars))
        self.assertEqual(before, state.model_dump())

    def test_brand_model_variant_and_year_restrict_examples(self):
        state = SessionState(goal='sell', seller=SellerVehicleFrame(brand='Toyota', model='Alphard'))
        choices = catalogue_choices('variant', state, self.cars)
        valid = {car.variant for car in self.cars if car.brand == 'Toyota' and car.model == 'Alphard'}
        self.assertTrue(set(choices) <= valid)
        self.assertNotIn('1.5 SE', choices)
        state.seller.variant = '2.5 G S C Package'
        years = catalogue_choices('year', state, self.cars)
        valid_years = {str(car.year) for car in self.cars if car.brand == 'Toyota' and car.model == 'Alphard' and car.variant == state.seller.variant}
        self.assertTrue(set(years) <= valid_years)

    def test_unknown_identity_uses_labelled_format_examples_and_empty_catalogue_stays_honest(self):
        state = SessionState(goal='sell', seller=SellerVehicleFrame(brand='Not in catalogue'))
        self.assertEqual(catalogue_choices('model', state, self.cars), [])
        guidance = example_for('seller.model', state, self.cars)
        self.assertIn('format examples from other saved models', guidance)
        self.assertIn('Alza [Perodua]', guidance)
        self.assertIn('not in the saved vehicle catalogue', catalogue_notice(state, self.cars))
        self.assertEqual(state.seller.brand, 'Not in catalogue')
        state = SessionState(goal='sell')
        self.assertEqual(catalogue_choices('brand', state, []), [])
        self.assertNotIn('Toyota', example_for('seller.brand', state, []))

    def test_axia_reproduction_keeps_vehicle_and_provides_examples_for_every_identity_question(self):
        self.assertFalse(any(car.model.casefold() == 'axia' for car in self.cars))
        for goal in MESSAGES:
            with self.subTest(goal=goal):
                state = SessionState(goal=goal)
                frame = identity_frame(state, goal)
                frame.brand, frame.model = 'perodua', 'axia'
                before = state.model_dump()
                notice = catalogue_notice(state, self.cars)
                self.assertIn('perodua axia is not in the saved vehicle catalogue', notice)
                prefix = 'seller' if goal == 'sell' else 'negotiation.vehicle' if goal == 'negotiate' else 'trade_in.current_vehicle'
                variant = example_for(prefix + '.variant', state, self.cars)
                self.assertIn('e.g.', variant)
                self.assertIn('Perodua Alza', variant)
                self.assertIn('format examples from other saved models', variant)
                self.assertIn('e.g. 2020', example_for(prefix + '.year', state, self.cars))
                self.assertIn('e.g. Automatic', example_for(prefix + '.transmission', state, self.cars))
                self.assertEqual(before, state.model_dump())
                if goal == 'sell':
                    questions = guided_questions(requirements(state, AS_OF), state, self.cars)
                    self.assertEqual(len(questions), 4)  # One notice, three actual questions.
                    self.assertEqual(sum('not in the saved vehicle catalogue' in q for q in questions), 1)
                    self.assertTrue(all('(e.g.' in q for q in questions[1:]))

    def test_form_numeric_placeholders_are_accepted_without_units_or_currency_symbols(self):
        state = SessionState()
        for goal in MESSAGES:
            for field in fields_for(goal):
                if field.kind not in ('integer', 'number', 'money', 'distance'):
                    continue
                with self.subTest(slot=field.path):
                    hint, placeholder = form_guidance(field, state, self.cars, goal=goal)
                    self.assertTrue(hint)
                    self.assertTrue(placeholder.startswith('e.g. '))
                    value = parse_number(placeholder[5:], field.kind)
                    self.assertGreaterEqual(value, 0)
                    if field.kind == 'money':
                        self.assertIn('omit the currency symbol', hint)
                    if field.kind == 'distance':
                        self.assertIn('choose the odometer unit', hint)

    def test_unsupported_axia_still_has_no_fabricated_valuation(self):
        from valuation import estimate_vehicle_value
        profile = SellerVehicleFrame(brand='Perodua', model='Axia', variant='1.0 G', year=2020,
                                     transmission='Automatic', mileage_km=65000., condition='good')
        result = estimate_vehicle_value(profile, self.cars, as_of=AS_OF)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['reference'])
        self.assertIsNone(result['historical_regression']['estimated_asking_price_myr'])

    def test_every_initial_required_question_in_all_three_goals_has_guidance(self):
        for goal in MESSAGES:
            with self.subTest(goal=goal):
                state = SessionState(goal=goal)
                missing = requirements(state, AS_OF)
                for slot, question in missing.items():
                    self.assertIn(' (', guided_question(question, slot, state, self.cars))
                runtime = ToolRuntime(state, self.cars, AS_OF)
                inspected = runtime.call('inspect_requirements', {})['questions']
                asked = runtime.call('ask_user', {})['questions']
                self.assertEqual(inspected, asked)
                self.assertTrue(all(q.count(' (e.g.') == 1 for q in asked))

    def test_tool_validation_and_regression_mileage_questions_also_get_examples_once(self):
        state = SessionState(goal='negotiate')
        state.negotiation.vehicle.brand = 'Toyota'
        state.negotiation.vehicle.model = 'Alphard'
        q = guided_question('What is the exact vehicle variant?', 'tool_question_0', state, self.cars)
        self.assertIn('2.5 G S', q)
        self.assertEqual(q, guided_question(q, 'tool_question_0', state, self.cars))
        q = guided_question('What is the odometer reading? Say Unknown if unavailable.', 'negotiation.mileage_km', state, self.cars)
        self.assertIn('65000 km', q)
        self.assertIn('actual odometer', q)

    def test_form_examples_cover_all_fields_without_quote_or_zero_defaults(self):
        state = SessionState()
        original = deepcopy(state.model_dump())
        for goal in MESSAGES:
            for field in fields_for(goal):
                with self.subTest(slot=field.path):
                    hint = example_for(field.path, state, self.cars, goal=goal)
                    self.assertTrue(hint)
                    if field.kind == 'money':
                        self.assertIn('format', hint)
        self.assertEqual(original, state.model_dump())
        self.assertEqual(example_for('buyer.budget_myr', state, self.cars, goal='buy'), '')

    def test_controller_returns_examples_but_does_not_record_them_as_user_facts(self):
        for goal, message in MESSAGES.items():
            with self.subTest(goal=goal):
                backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'ask_user'))
                agent = AgentController(backend=backend, as_of=AS_OF)
                result = agent.handle(message)
                self.assertEqual(result['status'], 'needs_clarification')
                self.assertIn('(e.g.', result['message'])
                self.assertIsNone(agent.state.seller.brand)
                self.assertIsNone(agent.state.negotiation.current_offer_myr)
                self.assertIsNone(agent.state.trade_in.loan_settlement_myr)

    def test_model_cannot_copy_brand_from_previous_question_without_current_evidence(self):
        backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'ask_user'),
                                  sensed(updates=[update('seller.brand', 'Perodua', 'Perodua')]),
                                  planned('inspect_requirements', 'ask_user'))
        agent = AgentController(backend=backend, as_of=AS_OF)
        first = agent.handle(MESSAGES['sell'])
        self.assertIn('Perodua', first['message'])
        second = agent.handle('Please continue.')
        self.assertEqual(second['status'], 'needs_clarification')
        self.assertIsNone(agent.state.seller.brand)

    def test_streamlit_chat_and_empty_forms_display_examples_for_all_three_areas(self):
        for goal, message in MESSAGES.items():
            with self.subTest(goal=goal):
                backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'ask_user'))
                ui = UISession(AgentController(backend=backend, as_of=AS_OF))
                app = AppTest.from_file('streamlit_app.py', default_timeout=30)
                app.session_state['ui_session'] = ui
                app.session_state['task_area'] = goal
                app.run()
                self.assertFalse(app.exception)
                prefix = 'seller' if goal == 'sell' else 'negotiation.vehicle' if goal == 'negotiate' else 'trade_in.current_vehicle'
                field = app.text_input(key=f'field_{goal}_0_{prefix}.brand')
                self.assertEqual(field.value, '')
                self.assertIn('Perodua', field.placeholder)
                captions = '\n'.join(item.value for item in app.caption)
                self.assertIn('e.g. 65000 with km selected below', captions)
                if goal != 'sell':
                    self.assertIn('omit the currency symbol', captions)
                    self.assertIn('All fees are complete', captions)
                self.assertEqual(backend.requests, [])
                app.chat_input[0].set_value(message).run()
                self.assertFalse(app.exception)
                self.assertEqual(ui.last_response['status'], 'needs_clarification')
                self.assertIn('(e.g.', ui.last_response['message'])
                app.run()  # The next rerender shows the newly completed turn.
                self.assertIn('(e.g.', '\n'.join(item.value for item in app.text))

    def test_axia_question_guidance_is_visible_in_real_streamlit_text_and_form(self):
        state = SessionState(goal='sell', seller=SellerVehicleFrame(brand='perodua', model='axia'))
        backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'ask_user'))
        ui = UISession(AgentController(state=state, backend=backend, as_of=AS_OF))
        ui.submit('Please continue.', goal='sell')
        app = AppTest.from_file('streamlit_app.py', default_timeout=30)
        app.session_state['ui_session'] = ui
        app.session_state['task_area'] = 'sell'
        app.run()
        self.assertFalse(app.exception)
        text = '\n'.join(item.value for item in app.text)
        self.assertIn('perodua axia is not in the saved vehicle catalogue', text)
        self.assertIn('What is the exact vehicle variant? (e.g.', text)
        captions = '\n'.join(item.value for item in app.caption)
        self.assertIn('format examples from other saved models', captions)
        self.assertIn('e.g. 65000 with km selected below', captions)
        self.assertEqual(ui.controller.state.seller.model, 'axia')
        self.assertEqual(app.text_input(key='field_sell_1_seller.variant').value, '')


if __name__ == '__main__':
    unittest.main()
