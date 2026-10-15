"""Regression checks for the Stage 5 acceptance review."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from pydantic import ValidationError
from buyer_profile import BuyerProfileFrame
from matching import filter_vehicles
from scoring import rank_vehicles
from vehicle_frame import PassengerCarFrame, load_vehicles
from check_data_quality import profile_data

ROOT = Path(__file__).resolve().parent


class Stage5AuditTests(unittest.TestCase):
    def setUp(self):
        self.cars = load_vehicles(ROOT / 'data/vehicles_real.json')
        self.profile = BuyerProfileFrame(budget_myr=50000, required_seats=5, usage=['city_commute'])

    def test_transaction_record_never_recommended_for_purchase(self):
        raw = self.cars[0].model_dump(mode='json')
        raw.update(source_kind='transaction', price_type='transaction')
        car = PassengerCarFrame.model_validate_json(json.dumps(raw))
        result = filter_vehicles(self.profile, [car])
        self.assertEqual(result['matched_count'], 0)
        self.assertTrue(any(r['rule_id'] == 'FILTER_PRICE_BASIS' for r in result['rejected'][0]['reasons']))

    def test_mileage_point_must_agree_with_range(self):
        raw = self.cars[0].model_dump(mode='json')
        for changes in [{'mileage_km': 900}, {'mileage_km': 80000}, {'mileage_km': 80000, 'mileage_min_km': None}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PassengerCarFrame.model_validate_json(json.dumps(raw | changes))

    def test_manufacturing_year_cannot_be_after_observation(self):
        raw = self.cars[0].model_dump(mode='json')
        with self.assertRaises(ValidationError):
            PassengerCarFrame.model_validate_json(json.dumps(raw | {'year': 2027}))

    def test_real_features_require_real_https_evidence(self):
        raw = next(v for v in self.cars if v.fuel_km_per_l is not None).model_dump(mode='json')
        for changes in [{'fuel_basis': 'synthetic_demo'}, {'fuel_source_reference': 'unverified'}, {'specs_source_reference': ' '}, {'fuel_source_reference': 'http://example.test/specs'}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PassengerCarFrame.model_validate_json(json.dumps(raw | changes))

    def test_receipts_are_compared_by_id_and_field(self):
        from check_data_quality import check_receipts
        receipts = json.loads((ROOT / 'data/source_receipts.json').read_text(encoding='utf-8'))
        self.assertEqual(check_receipts(self.cars, receipts), [])
        changed = deepcopy(receipts)
        changed['sources'][0]['fields']['price_myr'] += 100
        self.assertTrue(any('price_myr' in issue for issue in check_receipts(self.cars, changed)))
        for modified in [dict(receipts, sources=receipts['sources'][1:]), dict(receipts, sources=receipts['sources'] + [receipts['sources'][0]])]:
            self.assertTrue(check_receipts(self.cars, modified))

    def test_quality_reports_comparable_coverage_and_receipt_check(self):
        result = profile_data(ROOT / 'data/vehicles_real.json')
        self.assertEqual(result['receipt_check']['status'], 'passed')
        sufficient = [g for g in result['valuation_comparable_groups'] if g['meets_minimum_three']]
        self.assertEqual([(g['model'], g['year'], g['count']) for g in sufficient], [('Alza', 2020, 3)])

    def test_real_rank_is_not_price_order_and_respects_constraints(self):
        p = self.profile.model_copy(update={'fuel_priority': 'high', 'space_priority': 'high'})
        filtered = filter_vehicles(p, self.cars)
        ranked = rank_vehicles(p, filtered)
        self.assertEqual(ranked['top_vehicle_ids'], ['PT_K4EDNMNYPG', 'PT_7PRLM3GLPK', 'CS_C606800'])
        self.assertNotEqual(ranked['top_vehicle_ids'][0], filtered['matches'][0]['vehicle']['vehicle_id'])
        self.assertTrue(all(r['vehicle']['price_myr'] <= 50000 and r['vehicle']['seats'] >= 5 for r in ranked['matches']))


if __name__ == '__main__':
    unittest.main()
