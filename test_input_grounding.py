import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from buyer_profile import BuyerProfileFrame, reason_about_profile
from seller_profile import SellerVehicleFrame, extract_seller_profile
from main import extract_profile
from input_grounding import mileage_from_text, budget_from_text, ground_seller, ground_buyer, buyer_extraction_text
from valuation import estimate_vehicle_value
from vehicle_frame import load_vehicles


class DistanceTests(unittest.TestCase):
    def test_metres_not_kilometres(self):
        for raw, expected in [('900m',0.9),('900 m',0.9),('50000 m',50),('900 metres',0.9),('900 meters',0.9),('1.5 km',1.5),('90k km',90000),('90,000 km',90000),('90 000 km',90000)]:
            with self.subTest(raw=raw):
                value, evidence, issue=mileage_from_text(raw)
                self.assertEqual(value,expected)
                self.assertIsNone(issue)
                self.assertTrue(evidence)

    def test_miles_exact_conversion(self):
        for raw in ['900 miles','900mi','900 mile']:
            self.assertAlmostEqual(mileage_from_text(raw)[0],1448.4096)

    def test_units_missing_invalid_or_conflicting(self):
        for raw in ['odometer 90000','90k','900 cm','90000 km or 80000 km','-900 km','over 90000 km','about 90k km','roughly 90k km','~90k km','between 80k and 90k km','80-90k km','90,00 km']:
            with self.subTest(raw=raw):
                self.assertIsNone(mileage_from_text(raw)[0])
                self.assertTrue(mileage_from_text(raw)[2])

    def test_equivalent_readings_not_a_conflict(self):
        self.assertEqual(mileage_from_text('90000 m, which is 90 km')[0],90)

    def test_daily_distance_not_odometer(self):
        self.assertEqual(mileage_from_text('I drive 30 km daily, odometer 90k km.')[0],90000)
        self.assertIsNone(mileage_from_text('I commute 90 km daily.')[0])
        self.assertEqual(mileage_from_text('Odometer 90000 km, commute 50km/day.')[0],90000)

    def test_word_numbers(self):
        self.assertEqual(mileage_from_text('ninety thousand kilometres')[0],90000)
        self.assertEqual(budget_from_text('Budget sixty thousand ringgit.')[0],60000)


class MoneyTests(unittest.TestCase):
    def test_total_myr_formats(self):
        for text in ['Budget RM50k, five seats','budgetRM50000, city commuting.','MYR 50,000.','50000 MYR','50000 ringgit']:
            with self.subTest(text=text):
                self.assertEqual(budget_from_text(text)[0],50000)

    def test_missing_foreign_or_malformed_currency(self):
        for text in ['Budget 50000','Budget USD50000','Budget $50000','Budget RM50,00','Budget RM-50000','RM50000 or SGD50000','platform50000']:
            with self.subTest(text=text):
                self.assertIsNone(budget_from_text(text)[0])
        message=buyer_extraction_text('Budget USD50000, five seats, city commuting.')
        self.assertIn('five seats, city commuting',message)
        self.assertNotIn('USD50000',message)
        self.assertEqual(buyer_extraction_text('Budget RM50000, five seats.'),'Budget RM50000, five seats.')

    def test_monthly_not_total_and_mixed_total_supported(self):
        self.assertIsNone(budget_from_text('RM800 per month')[0])
        self.assertIsNone(budget_from_text('monthly budget RM800')[0])
        text='My monthly budget is RM800, and my maximum total purchase budget is RM50000.'
        self.assertEqual(budget_from_text(text)[0],50000)
        result=ground_buyer(text,BuyerProfileFrame(budget_myr=800,clarification_notes=['Monthly budget is not a total budget.']))
        self.assertEqual(result.budget_myr,50000)
        self.assertEqual(result.clarification_notes,[])

    def test_ranges_and_conflicting_totals(self):
        for text in ['Budget RM40k to 50k','Budget between RM40k and RM50k','Budget RM40k-RM50k']:
            self.assertEqual(budget_from_text(text)[0],50000)
        for text in ['I want to buy a car. Budget RM40000 but budget RM50000.','RM50000 to RM40000']:
            self.assertIsNone(budget_from_text(text)[0])


class GuardIntegrationTests(unittest.TestCase):
    def seller(self, **changes):
        return SellerVehicleFrame.model_validate({'brand':'Perodua','model':'Alza','variant':'1.5 SE','year':2020,'transmission':'Automatic','mileage_km':90000,'condition':'fair'} | changes)

    def test_overrides_even_a_wrong_model_number(self):
        result=ground_seller('Manufactured in 2020, mileage 900m.',self.seller(mileage_km=90000))
        self.assertEqual(result.mileage_km,0.9)
        self.assertTrue(result.input_validation_notes)

    def test_registration_only_and_conflicting_manufacture_years(self):
        for text in ['Registered in 2021, manufacturing year unknown, 90k km.','Registered in May 2021, manufacturing year unknown, 90k km.','Manufactured in 2020, manufactured in 2021, 90k km.']:
            result=ground_seller(text,self.seller())
            self.assertIsNone(result.year)
            self.assertTrue(result.clarification_notes)

    def test_cannot_invent_year(self):
        result=ground_seller('Mileage 90k km, fair condition.',self.seller(year=2020))
        self.assertIsNone(result.year)

    def test_damage_unknown_not_clean_history(self):
        result=ground_seller('Manufactured in 2020, 90k km. Not sure whether it had a major accident or flood damage.',self.seller(major_accident_reported=False,flood_damage_reported=False))
        self.assertIsNone(result.major_accident_reported)
        self.assertIsNone(result.flood_damage_reported)
        result=ground_seller('Manufactured in 2020, 90k km, good condition.',self.seller(major_accident_reported=False,flood_damage_reported=False))
        self.assertIsNone(result.major_accident_reported)
        self.assertIsNone(result.flood_damage_reported)

    def test_explicit_no_damage_preserved(self):
        for history in ['No major accident and no flood damage.','No major accident or flood damage.','Accident-free and flood-free.']:
            result=ground_seller('Manufactured in 2020, 90k km. '+history,self.seller(major_accident_reported=False,flood_damage_reported=False))
            self.assertFalse(result.major_accident_reported)
            self.assertFalse(result.flood_damage_reported)

    def test_unclear_mileage_blocks_valuation(self):
        result=ground_seller('Manufactured in 2020, odometer 90000, unit unspecified.',self.seller())
        cars=load_vehicles(Path(__file__).resolve().parent/'data'/'vehicles_real.json')
        valuation=estimate_vehicle_value(result,cars,as_of=date(2026,10,15))
        self.assertEqual(valuation['status'],'needs_clarification')
        self.assertIsNone(valuation['reference'])

    def test_unclear_budget_blocks_matching(self):
        profile=ground_buyer('Budget USD50000, five seats, city commuting.',BuyerProfileFrame(budget_myr=50000,required_seats=5,usage=['city_commute']))
        self.assertFalse(reason_about_profile(profile)['ready_for_matching'])
        self.assertIsNone(profile.budget_myr)

    def test_budget_issue_does_not_erase_explicit_other_requirements(self):
        result=ground_buyer('Budget USD50000, five seats, city commuting.',BuyerProfileFrame())
        self.assertEqual(result.required_seats,5)
        self.assertEqual(result.usage,['city_commute'])
        self.assertIsNone(result.budget_myr)
        for text in ["Budget USD50000, I do not need five seats.",'Budget USD50000, at most five seats.','Budget USD50000, not city commuting.']:
            result=ground_buyer(text,BuyerProfileFrame())
            self.assertIsNone(result.required_seats)
            self.assertEqual(result.usage,[])

    def test_actual_extract_entry_points_apply_guards(self):
        raw=self.seller().model_dump_json()
        with patch('ollama.Client') as client:
            client.return_value.chat.return_value=SimpleNamespace(message=SimpleNamespace(content=raw))
            self.assertEqual(extract_seller_profile('Manufactured in 2020, 50000 m.').mileage_km,50)
        raw=BuyerProfileFrame(budget_myr=50000,required_seats=5,usage=['city_commute']).model_dump_json()
        with patch('ollama.Client') as client:
            client.return_value.chat.return_value=SimpleNamespace(message=SimpleNamespace(content=raw))
            self.assertIsNone(extract_profile('Budget USD50000, five seats, city commuting.','qwen3:4b').budget_myr)


if __name__=='__main__':
    unittest.main()
