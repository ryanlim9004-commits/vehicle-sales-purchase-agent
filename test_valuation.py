# Learning guide:
# Offline tests for comparable selection, price arithmetic and refusal states.
# The date is fixed so freshness boundaries and expected prices are repeatable.
# The illustrative scenario is tested as teaching arithmetic, not market accuracy.
import json
import unittest
from datetime import date
from pathlib import Path
from pydantic import ValidationError
from seller_profile import SellerVehicleFrame
from vehicle_frame import load_vehicles
from valuation import estimate_vehicle_value, money

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


# Exercise selection/refusal states and default/illustrative price arithmetic on dated saved
# evidence.
class ValuationTests(unittest.TestCase):
    # Prepare fresh fixtures for this test so another test cannot change its starting assumptions.
    def setUp(self):
        self.cars = load_vehicles(ROOT/'data'/'vehicles_real.json')
        self.seller = SellerVehicleFrame.model_validate_json((ROOT/'examples'/'seller_alza.json').read_text(encoding='utf-8'))

    # Run the real valuation tool using the fixed date and optional policy arguments.
    def estimate(self, seller=None, cars=None, **kwargs):
        return estimate_vehicle_value(seller or self.seller, self.cars if cars is None else cars, as_of=AS_OF, **kwargs)

    # Create a changed typed vehicle record without mutating the shared source fixture.
    def modified(self, **changes):
        return SellerVehicleFrame.model_validate(self.seller.model_dump() | changes)

    # The selected three asking prices reproduce the reference median and observed range.
    def test_reference_reconciles_with_three_listings(self):
        result = self.estimate()
        self.assertEqual(result['status'], 'reference_only')
        self.assertEqual({c['vehicle_id'] for c in result['comparables']}, {'CL18923892','CL19122669','CL19418670'})
        self.assertEqual(result['reference']['median_asking_price_myr'], 44800)
        self.assertEqual(result['reference']['observed_asking_range_myr'], [35888,45000])
        self.assertIsNone(result['adjusted_scenario'])
        self.assertFalse(result['reference']['personalized_for_mileage_or_condition'])

    # Too few exact comparables returns insufficient evidence and no invented valuation.
    def test_insufficient_data_does_not_guess(self):
        result = self.estimate(self.modified(model='Bezza', variant='1.3 AV', year=2023))
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['reference'])

    # Missing or conflicting seller facts produce questions before price calculation.
    def test_missing_and_ambiguous_facts(self):
        for seller in [SellerVehicleFrame(), self.modified(condition='unknown'), self.modified(clarification_notes=['Is the stated year manufacture or registration?'])]:
            result = self.estimate(seller)
            self.assertEqual(result['status'], 'needs_clarification')
            self.assertTrue(result['clarification_questions'])
            self.assertIsNone(result['reference'])

    # Reported major accident/flood damage must route to inspection instead of ordinary pricing.
    def test_major_damage_withholds_estimate(self):
        for change in [{'major_accident_reported':True}, {'flood_damage_reported':True}]:
            result = self.estimate(self.modified(**change), illustrative_adjustments=True)
            self.assertEqual(result['status'], 'inspection_required')
            self.assertIsNone(result['adjusted_scenario'])

    # A manufacturing year after the consultation date cannot receive a normal valuation.
    def test_future_manufacturing_year_requests_clarification(self):
        result = self.estimate(self.modified(year=2027))
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertIsNone(result['reference'])
        self.assertTrue(any('year' in q for q in result['clarification_questions']))

    # Different variant/year/transmission records must not enter an exact comparable group.
    def test_comparable_identity_and_year_transmission(self):
        for change in [{'year':2019}, {'variant':'1.5 AV'}, {'transmission':'Manual'}]:
            self.assertEqual(self.estimate(self.modified(**change))['status'], 'insufficient_evidence')
        self.assertEqual(len(self.estimate(self.modified(brand=' perodua ', model='ALZA', variant='1.5 se'))['comparables']),3)

    # Repeated IDs or source URLs cannot inflate the comparable sample.
    def test_duplicate_sources_not_counted_twice(self):
        one = self.cars[0]
        result = self.estimate(cars=[one,one,one])
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(len(result['comparables']),1)

    # Old, future-dated or unavailable ads fail the valuation evidence window.
    def test_stale_future_or_unavailable_not_counted(self):
        base = [v for v in self.cars if v.vehicle_id in {'CL18923892','CL19122669','CL19418670'}]
        changes = [{'source_updated_on':date(2026,1,1)}, {'source_updated_on':None}, {'availability':'sold'}, {'observed_on':date(2026,10,16)}]
        for change in changes:
            cars = [v.model_copy(update=change) for v in base]
            with self.subTest(change=change):
                self.assertEqual(self.estimate(cars=cars)['status'],'insufficient_evidence')

    # Fictional teaching prices must not influence a real-source valuation reference.
    def test_synthetic_not_pooled_with_real(self):
        demo = load_vehicles(ROOT/'data'/'vehicles_demo.json')
        self.assertEqual(self.estimate(cars=demo)['status'],'insufficient_evidence')

    # The optional uncalibrated scenario preserves mileage intervals and reconciles its teaching
    # formula.
    def test_illustrative_math_and_mileage_ranges(self):
        result = self.estimate(illustrative_adjustments=True)
        scenario = result['adjusted_scenario']
        self.assertEqual(result['status'],'illustrative_scenario')
        self.assertFalse(scenario['market_validated'])
        self.assertEqual(scenario['reference_mileage_interval_km'],[100000,105000])
        self.assertEqual(scenario['mileage_factor_interval'],[1.01,1.015])
        self.assertEqual(scenario['scenario_midpoint_myr'],43092)
        self.assertEqual(scenario['scenario_range_myr'],[34434.54,43391.25])

    # Do not apply teaching mileage factors beyond the supported envelope or with missing
    # comparable mileage.
    def test_adjustment_extrapolation_and_missing_mileage_withheld(self):
        result = self.estimate(self.modified(mileage_km=500000),illustrative_adjustments=True)
        self.assertEqual(result['status'],'reference_only')
        self.assertIsNone(result['adjusted_scenario'])
        cars = [v.model_copy(update={'mileage_km':None,'mileage_min_km':None,'mileage_max_km':None}) for v in self.cars]
        self.assertIsNone(self.estimate(cars=cars,illustrative_adjustments=True)['adjusted_scenario'])

    # A good/fair/poor condition label must not establish a clean accident/flood history.
    def test_self_reported_condition_not_automatic_damage_history(self):
        result = self.estimate(self.modified(major_accident_reported=None, flood_damage_reported=None))
        self.assertTrue(any('Damage history is unknown' in x for x in result['limitations']))

    # Strict seller Frames reject malformed values instead of silently coercing them.
    def test_invalid_seller_types_rejected(self):
        for data in [{'mileage_km':-1}, {'mileage_km':'90k'}, {'major_accident_reported':'false'}, {'unallowed':'value'}]:
            with self.subTest(data=data),self.assertRaises(ValidationError):
                SellerVehicleFrame.model_validate(data)
        self.assertEqual(money(1.005),1.01)


if __name__ == '__main__':
    unittest.main()
