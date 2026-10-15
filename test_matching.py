import json
import tempfile
import unittest
from pathlib import Path
from pydantic import ValidationError
from buyer_profile import BuyerProfileFrame
from vehicle_frame import load_vehicles, PassengerCarFrame
from matching import filter_vehicles

DATA = Path(__file__).resolve().parent / 'data' / 'vehicles_demo.json'


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.vehicles = load_vehicles(DATA)

    def profile(self, **changes):
        return BuyerProfileFrame.model_validate(dict(budget_myr=60000, family_size=6, usage=['city_commute']) | changes)

    def ids(self, result):
        return [item['vehicle']['vehicle_id'] for item in result['matches']]

    def test_family_and_inclusive_budget_boundary(self):
        result = filter_vehicles(self.profile(), self.vehicles)
        self.assertEqual(self.ids(result), ['DEMO001', 'DEMO002', 'DEMO006'])
        self.assertEqual(result['checked_count'], 8)
        self.assertTrue(all(v['vehicle']['price_myr'] <= 60000 and v['vehicle']['seats'] >= 6 for v in result['matches']))

    def test_excluded_brand_case_and_whitespace(self):
        result = filter_vehicles(self.profile(excluded_brands=[' tOyOtA ']), self.vehicles)
        self.assertEqual(self.ids(result), ['DEMO001', 'DEMO006'])
        rejected = next(r for r in result['rejected'] if r['vehicle_id'] == 'DEMO002')
        self.assertEqual(rejected['reasons'][0]['rule_id'], 'FILTER_EXCLUDED_BRAND')

    def test_missing_values_are_not_eligible(self):
        result = filter_vehicles(self.profile(), self.vehicles)
        reasons = {r['vehicle_id']: r['reasons'][0]['rule_id'] for r in result['rejected']}
        self.assertEqual(reasons['DEMO007'], 'FILTER_PRICE_UNKNOWN')
        self.assertEqual(reasons['DEMO008'], 'FILTER_SEATS_UNKNOWN')

    def test_all_failed_constraints_explained(self):
        result = filter_vehicles(self.profile(budget_myr=30000, excluded_brands=['Toyota']), self.vehicles)
        row = next(r for r in result['rejected'] if r['vehicle_id'] == 'DEMO005')
        self.assertEqual({r['rule_id'] for r in row['reasons']}, {'FILTER_BUDGET', 'FILTER_SEATS', 'FILTER_EXCLUDED_BRAND'})
        self.assertEqual(result['status'], 'no_matches')
        self.assertEqual(result['constraints']['maximum_price_myr'], 30000)

    def test_missing_and_conflicting_profile_blocks_filtering(self):
        for profile in [BuyerProfileFrame(), self.profile(required_seats=5), self.profile(preferred_brands=['Toyota'], excluded_brands=[' toyota '])]:
            result = filter_vehicles(profile, self.vehicles)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertEqual(result['checked_count'], 0)

    def test_preferred_brand_is_soft_not_exclusion(self):
        result = filter_vehicles(self.profile(preferred_brands=['TOYOTA']), self.vehicles)
        self.assertEqual(self.ids(result), ['DEMO001', 'DEMO002', 'DEMO006'])
        self.assertEqual([r['vehicle']['vehicle_id'] for r in result['matches'] if r['preferred_brand_match']], ['DEMO002'])

    def test_frame_inheritance_defaults_and_validation(self):
        self.assertEqual(self.vehicles[0].wheels, 4)
        self.assertEqual(self.vehicles[0].currency, 'MYR')
        raw = self.vehicles[0].model_dump(mode='json')
        for changes in [{'price_myr': -1}, {'seats': 'seven'}, {'brand': ' '}, {'currency': 'USD'}, {'price_myr': float('inf')}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PassengerCarFrame.model_validate_json(json.dumps(raw | changes))

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'duplicates.json'
            row = self.vehicles[0].model_dump(mode='json')
            path.write_text(json.dumps([row, row]), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                load_vehicles(path)


if __name__ == '__main__':
    unittest.main()
