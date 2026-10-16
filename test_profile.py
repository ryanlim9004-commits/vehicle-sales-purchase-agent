# Learning guide:
# Offline unit tests for buyer Frames, rule chaining and clarification.
# Assertions compare intended facts and rule outcomes with actual Python results.
# Run all test files with python -m unittest; no running Ollama is needed.
import unittest
from pydantic import ValidationError
from buyer_profile import BuyerProfileFrame, reason_about_profile


# Group offline tests of explicit buyer facts, derived rules and blocking conflicts.
class ProfileTests(unittest.TestCase):
    # Family size derives seats and then a minimum vehicle capacity, with the expected rule trace.
    def test_family_rule_chain(self):
        result = reason_about_profile(BuyerProfileFrame(budget_myr=60000, family_size=6, usage=['city_commute'], fuel_priority='high'))
        self.assertIsNone(result['extracted_profile']['required_seats'])
        self.assertEqual(result['derived_facts']['minimum_vehicle_seats'], 6)
        self.assertEqual([r['rule_id'] for r in result['fired_rules']], ['BUY_01', 'BUY_02', 'BUY_03'])
        self.assertTrue(result['ready_for_matching'])

    # A fuel-only request must ask for missing essentials instead of inventing a budget.
    def test_missing_does_not_invent_budget(self):
        result = reason_about_profile(BuyerProfileFrame())
        self.assertIsNone(result['derived_facts']['budget_myr'])
        self.assertEqual(set(result['missing_slots']), {'budget_myr', 'required_seats', 'usage'})
        self.assertFalse(result['ready_for_matching'])

    # A household/seat contradiction blocks matching until the user resolves it.
    def test_seat_conflict_requires_clarification(self):
        result = reason_about_profile(BuyerProfileFrame(budget_myr=60000, family_size=6, required_seats=5, usage=['family_travel']))
        self.assertFalse(result['ready_for_matching'])
        self.assertEqual(result['derived_facts']['required_seats'], 5)
        self.assertTrue(result['clarification_questions'])

    # Invalid numeric ranges and misleading types must fail frame validation.
    def test_negative_and_wrong_type_rejected(self):
        for data in [{'budget_myr': -1}, {'required_seats': 'six'}, {'required_seats': True}, {'unexpected': 'value'}]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                BuyerProfileFrame.model_validate(data)

    # Excluded brands stay separate from preferences, and contradictory brand facts require
    # clarification.
    def test_negated_brand_and_ambiguity(self):
        result = reason_about_profile(BuyerProfileFrame(budget_myr=50000, required_seats=5, usage=['city_commute'], excluded_brands=['Toyota']))
        self.assertEqual(result['extracted_profile']['preferred_brands'], [])
        self.assertTrue(result['ready_for_matching'])
        ambiguous = reason_about_profile(BuyerProfileFrame(clarification_notes=['Only monthly budget provided']))
        self.assertFalse(ambiguous['ready_for_matching'])


if __name__ == '__main__':
    unittest.main()
