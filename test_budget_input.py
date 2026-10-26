"""Check money scale, currency and correction behavior through real tools."""
from datetime import date
import unittest
from agent_controller import AgentController
from agent_grounding import apply_patch, money_from_evidence
from agent_state import SessionState, SlotUpdate, TurnPatch
from buyer_profile import BuyerProfileFrame
from form_inputs import parse_number, prepare_form
from input_grounding import budget_from_text, mileage_from_text
from test_agent import ScriptedBackend, planned, sensed, update


class BudgetInputTests(unittest.TestCase):
    def test_explicit_myr_million_formats_and_range(self):
        for text, expected in [('Budget RM1million', 1000000), ('Budget RM1 million', 1000000),
                               ('Budget MYR1m', 1000000), ('Budget 1 million ringgit', 1000000),
                               ('Budget RM1.25 million', 1250000), ('Budget RM1000k', 1000000),
                               ('Budget RM60000 to 1 million', 1000000)]:
            with self.subTest(text=text):
                value, _, issue = budget_from_text(text)
                self.assertEqual(value, expected)
                self.assertIsNone(issue)

    def test_money_m_does_not_change_distance_m(self):
        self.assertEqual(budget_from_text('Budget RM1m')[0], 1000000)
        self.assertEqual(mileage_from_text('Odometer 1 m')[0], .001)
        self.assertEqual(mileage_from_text('Odometer 900 m')[0], .9)

    def test_unsupported_currency_and_scale_give_actionable_questions(self):
        for text in ('Budget 1million', 'Budget USD1 million', 'Budget RM1 billion',
                     'Budget RM1billion', 'Budget RM1e6', 'Budget RM50000.001'):
            with self.subTest(text=text):
                value, _, issue = budget_from_text(text)
                self.assertIsNone(value)
                self.assertTrue(issue)
                self.assertTrue('RM' in issue or 'MYR' in issue)

    def test_form_scale_is_exact_and_invalid_formats_are_not_guessed(self):
        for text in ('1million', '1 million', '1,000,000', '1000k', 'one million'):
            self.assertEqual(parse_number(text, 'money'), 1000000)
        for text in ('USD1million', '1billion', '1e6', 'NaN', '1.234', '9'*100):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, '60000|two decimal'):
                parse_number(text, 'money')

    def test_budget_form_uses_the_shared_controller_grounding(self):
        state = SessionState(goal='buy')
        text, patch = prepare_form('buy', {'buyer.budget_myr': '1million'}, state)
        apply_patch(state, patch, text)
        self.assertEqual(state.buyer.budget_myr, 1000000)
        self.assertNotIn('buyer.budget_myr', state.issues)
        for raw in ('0', '-1'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'greater than 0.*1 million'):
                prepare_form('buy', {'buyer.budget_myr': raw}, state)

    def test_full_budget_source_corrects_truncated_model_evidence(self):
        state = SessionState(goal='buy')
        patch = TurnPatch(updates=[SlotUpdate(slot='buyer.budget_myr', value=1, evidence='RM1')])
        apply_patch(state, patch, 'My maximum budget is RM1 million.')
        self.assertEqual(state.buyer.budget_myr, 1000000)
        self.assertTrue(any(row.get('rule_id') == 'BUY_BUDGET_SOURCE' for row in state.trace))

    def test_invalid_correction_does_not_reuse_a_previous_budget(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=60000, required_seats=5, usage=['city_commute']))
        apply_patch(state, TurnPatch(), 'Change my maximum budget to 1million.')
        self.assertIsNone(state.buyer.budget_myr)
        self.assertIn('RM1 million', state.issues['buyer.budget_myr'])
        self.assertEqual(state.buyer.required_seats, 5)
        self.assertEqual(state.buyer.usage, ['city_commute'])
        apply_patch(state, TurnPatch(), 'My budget is RM1million.')
        self.assertEqual(state.buyer.budget_myr, 1000000)
        self.assertNotIn('buyer.budget_myr', state.issues)

    def test_unrelated_money_does_not_replace_the_confirmed_budget(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=60000))
        apply_patch(state, TurnPatch(), 'Keep my budget unchanged; another car costs RM1 million.')
        self.assertEqual(state.buyer.budget_myr, 60000)

    def test_large_budget_runs_matching_without_an_inventory_price_cap(self):
        state = SessionState(goal='buy', buyer=BuyerProfileFrame(required_seats=5, usage=['family_travel']))
        backend = ScriptedBackend(sensed(updates=[update('buyer.budget_myr', 1, 'RM1')]),
                                  planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(state=state, backend=backend, as_of=date(2026, 10, 15))
        answer = agent.handle('My maximum budget is RM1 million.')
        self.assertEqual(answer['status'], 'complete')
        self.assertEqual(answer['result']['constraints']['maximum_price_myr'], 1000000)
        self.assertTrue(answer['result']['matches'])
        self.assertTrue(all(check['passed'] for check in answer['checks']))

    def test_shared_cash_quote_parser_keeps_the_same_scale(self):
        self.assertEqual(money_from_evidence('RM1.2 million', 'negotiation.current_offer_myr'), 1200000)


if __name__ == '__main__':
    unittest.main()
