import json
import unittest
from pathlib import Path
from buyer_profile import BuyerProfileFrame
from vehicle_frame import PassengerCarFrame, load_vehicles
from matching import filter_vehicles
from scoring import rank_vehicles
from check_data_quality import profile_data
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent


def vehicle(key, price, fuel=None, **changes):
    row = dict(vehicle_id=key, brand='TestBrand', model='Synthetic', year=2023, price_myr=price, seats=5,
               source_kind='synthetic_demo', source_reference='Unit test fixture', observed_on='2026-10-15')
    if fuel is not None:
        row.update(fuel_km_per_l=fuel, fuel_basis='synthetic_demo', fuel_source_reference='Unit test fixture')
    return PassengerCarFrame.model_validate_json(json.dumps(row | changes))


def profile(**changes):
    return BuyerProfileFrame.model_validate(dict(budget_myr=50000, required_seats=5, usage=['city_commute']) | changes)


def rank(p, cars):
    return rank_vehicles(p, filter_vehicles(p, cars))


class ScoringTests(unittest.TestCase):
    def test_preference_changes_order(self):
        cars = [vehicle('cheap', 20000, 11), vehicle('efficient', 40000, 24)]
        self.assertEqual(rank(profile(), cars)['top_vehicle_ids'][0], 'cheap')
        self.assertEqual(rank(profile(fuel_priority='high'), cars)['top_vehicle_ids'][0], 'efficient')

    def test_excluded_and_over_budget_never_ranked(self):
        cars = [vehicle('ok', 40000, 20), vehicle('over', 60000, 25), vehicle('excluded', 30000, 25, brand='Excluded')]
        self.assertEqual(rank(profile(fuel_priority='high', excluded_brands=['Excluded']), cars)['top_vehicle_ids'], ['ok'])

    def test_fixed_weights_missing_feature_not_rewarded(self):
        result = rank(profile(fuel_priority='high'), [vehicle('missing', 30000), vehicle('known', 30000, 20)])
        missing = next(r for r in result['matches'] if r['vehicle']['vehicle_id'] == 'missing')
        self.assertIsNone(missing['score_breakdown']['fuel']['normalized_value'])
        self.assertLess(missing['weighted_data_coverage_percent'], 100)
        self.assertGreater(missing['score_upper_bound'], missing['score'])
        self.assertEqual(result['top_vehicle_ids'][0], 'known')
        self.assertAlmostEqual(sum(result['scoring_weights'].values()), 1)

    def test_mixed_fuel_bases_disabled_globally(self):
        cars = [vehicle('A', 30000, 20), vehicle('B', 30000, 20, fuel_basis='MDC_claim')]
        result = rank(profile(fuel_priority='high'), cars)
        self.assertNotIn('fuel', result['scoring_weights'])
        self.assertTrue(any('incompatible' in note for note in result['scoring_notes']))

    def test_folded_boot_not_scored_for_full_passenger_load(self):
        cars = [vehicle('folded', 30000, boot_litres=600, boot_configuration='third_row_folded', specs_source_reference='Fixture')]
        row = rank(profile(space_priority='high'), cars)['matches'][0]
        self.assertIn('luggage', row['missing_scoring_features'])

    def test_components_reconcile_and_clipped(self):
        row = rank(profile(fuel_priority='high'), [vehicle('A', 30000, 90)])['matches'][0]
        self.assertAlmostEqual(row['score'], sum(c['weighted_points'] for c in row['score_breakdown'].values()), places=3)
        self.assertTrue(all(c['normalized_value'] is None or 0 <= c['normalized_value'] <= 1 for c in row['score_breakdown'].values()))
        self.assertLessEqual(row['score_upper_bound'], 100)

    def test_ties_stable_and_original_filter_not_mutated(self):
        p = profile()
        original = filter_vehicles(p, [vehicle('B', 30000), vehicle('A', 30000)])
        before = json.dumps(original)
        result = rank_vehicles(p, original)
        self.assertEqual(result['top_vehicle_ids'], ['A', 'B'])
        self.assertEqual(json.dumps(original), before)

    def test_empty_and_clarification(self):
        for p in [profile(), BuyerProfileFrame()]:
            self.assertEqual(rank(p, [])['top_vehicle_ids'], [])

    def test_preferred_brand_weight(self):
        cars = [vehicle('other', 30000), vehicle('preferred', 30000, brand='Toyota')]
        result = rank(profile(preferred_brands=['toyota']), cars)
        self.assertEqual(result['top_vehicle_ids'][0], 'preferred')


class RealDataTests(unittest.TestCase):
    def setUp(self):
        self.cars = load_vehicles(ROOT/'data'/'vehicles_real.json')

    def test_source_coverage_and_prices(self):
        self.assertEqual(len(self.cars), 17)
        self.assertTrue(all(v.price_type == 'asking' and v.source_kind == 'listing' for v in self.cars))
        receipts = json.loads((ROOT/'data'/'source_receipts.json').read_text(encoding='utf-8'))
        self.assertEqual({r['url'] for r in receipts['sources']}, {v.source_reference for v in self.cars})
        self.assertEqual(profile_data(ROOT/'data'/'vehicles_real.json')['critical_issues'], [])

    def test_sold_reserved_records_excluded(self):
        result = rank(profile(budget_myr=100000, required_seats=5), self.cars)
        self.assertTrue(all(r['vehicle']['availability'] == 'listed_snapshot' for r in result['matches']))
        rejected = [r for r in result['rejected'] if any(x['rule_id'] == 'FILTER_AVAILABILITY' for x in r['reasons'])]
        self.assertEqual(len(rejected), 6)

    def test_old_alza_not_assigned_new_specs(self):
        old = [v for v in self.cars if v.model == 'Alza' and v.year == 2020]
        self.assertEqual(len(old), 3)
        self.assertTrue(all(v.fuel_km_per_l is None and v.boot_litres is None for v in old))

    def test_real_mileage_preserves_ranges(self):
        ranged = next(v for v in self.cars if v.vehicle_id == 'CL18923892')
        self.assertIsNone(ranged.mileage_km)
        self.assertEqual((ranged.mileage_min_km, ranged.mileage_max_km), (65000, 70000))

    def test_real_reference_values_and_boot_configuration(self):
        av = next(v for v in self.cars if v.vehicle_id == 'PT_7PRLM3GLPK')
        x = next(v for v in self.cars if v.vehicle_id == 'CS_C606800')
        self.assertEqual((av.fuel_km_per_l, x.fuel_km_per_l), (22, 21))
        new_alza = next(v for v in self.cars if v.vehicle_id == 'CL18751444')
        self.assertEqual((new_alza.boot_litres, new_alza.boot_configuration), (137, 'all_seats_up'))

    def test_invalid_source_or_units_rejected(self):
        raw = self.cars[0].model_dump(mode='json')
        for changes in [{'price_type': 'transaction'}, {'variant': None}, {'source_reference': 'unverified'}, {'mileage_min_km': 80000, 'mileage_max_km': 70000}, {'fuel_km_per_l': 20}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PassengerCarFrame.model_validate_json(json.dumps(raw | changes))


if __name__ == '__main__':
    unittest.main()
