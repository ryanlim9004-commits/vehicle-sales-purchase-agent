"""Scenario integration checks, not validation of real market/specification accuracy."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from pydantic import ValidationError
from build_simulation_data import convert
from vehicle_frame import PassengerCarFrame, load_agent_vehicles, load_vehicles
from buyer_profile import BuyerProfileFrame
from seller_profile import SellerVehicleFrame
from matching import filter_vehicles
from lifestyle_v2 import rank_vehicles_v2
from scoring import rank_vehicles
from valuation import estimate_vehicle_value
from agent_controller import AgentController
from agent_state import SessionState
from test_agent import ScriptedBackend, sensed, planned
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


class SimulationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / 'data/historical_simulation_source.json').read_text(encoding='utf-8'))
        self.sim = load_vehicles(ROOT / 'data/vehicles_simulation.json')

    def profile(self, **changes):
        return BuyerProfileFrame.model_validate(dict(budget_myr=30000, required_seats=5, usage=['family_travel'], fuel_priority='high') | changes)

    def test_reproducible_conversion_and_no_fabricated_dates(self):
        self.assertEqual([v.model_dump() for v in convert(self.source)], [v.model_dump() for v in self.sim])
        self.assertEqual(len(self.sim), 97)
        self.assertEqual(len(load_agent_vehicles()), 114)
        self.assertEqual(len({v.simulation.source_record_group_id for v in self.sim}), 97)
        for v, original in zip(self.sim, self.source['records']):
            self.assertIsNone(v.observed_on)
            self.assertEqual(v.availability, 'unknown')
            self.assertEqual(v.price_type, 'illustrative')
            self.assertEqual(v.seats, original['specifications']['seats'])
            self.assertEqual(v.price_myr, original['asking_price_myr'])
            self.assertAlmostEqual(v.fuel_km_per_l, 100 / v.simulation.fuel_l_per_100km, places=5)
            self.assertEqual(v.mileage_min_km, original['mileage']['minimum_km'])

    def test_year_and_group_conflicts_fail_before_import(self):
        duplicate = deepcopy(self.source)
        duplicate['records'].append(deepcopy(duplicate['records'][0]))
        with self.assertRaises(ValueError):
            convert(duplicate)
        wrong_year = deepcopy(self.source)
        wrong_year['records'][0]['identity']['manufacturing_year'] = 2014
        with self.assertRaises(ValueError):
            convert(wrong_year)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'duplicates.json'
            rows = [v.model_dump(mode='json') for v in self.sim[:1]] * 2
            rows[1] = dict(rows[1], vehicle_id='different-id-same-source-group')
            path.write_text(json.dumps(rows), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_vehicles(path)

    def test_simulation_cannot_relabel_as_real_listing(self):
        row = self.sim[0].model_dump()
        with self.assertRaises(ValidationError):
            PassengerCarFrame.model_validate(row | dict(source_kind='listing', price_type='asking'))

    def test_buy_expands_coverage_but_preserves_hard_constraints(self):
        p = self.profile(excluded_brands=['Ford'])
        result = filter_vehicles(p, load_agent_vehicles())
        self.assertEqual(result['matched_count'], 4)
        self.assertTrue(all(r['vehicle']['price_myr'] <= 30000 and r['vehicle']['seats'] >= 5 and r['vehicle']['brand'] != 'Ford' for r in result['matches']))
        six = filter_vehicles(self.profile(required_seats=6), load_agent_vehicles())
        self.assertEqual([r['vehicle']['vehicle_id'] for r in six['matches']], ['SIM-MRC-V1-0246'])

    def test_mixed_cycles_and_estimates_are_not_fuel_comparisons(self):
        p = self.profile()
        filtered = filter_vehicles(p, load_agent_vehicles())
        for scorer in (rank_vehicles, rank_vehicles_v2):
            result = scorer(p, filtered)
            self.assertTrue(any('incompatible' in note for note in result['scoring_notes']))
            self.assertTrue('fuel' not in result['scoring_weights'])
            if scorer == rank_vehicles_v2:
                self.assertEqual(result['raw_scoring_weights']['fuzzy_lifestyle'], 2)  # luggage only
        estimated = next(v for v in self.sim if v.simulation.specification_match_quality == 'simulation_default')
        p = self.profile(budget_myr=1000000, required_seats=2)
        singleton = rank_vehicles_v2(p, filter_vehicles(p, [estimated]))
        self.assertTrue(any('incompatible' in n for n in singleton['scoring_notes']))

    def test_simulation_never_changes_market_reference(self):
        seller = SellerVehicleFrame.model_validate_json((ROOT / 'examples/seller_alza.json').read_text())
        real = estimate_vehicle_value(seller, load_vehicles(ROOT / 'data/vehicles_real.json'), as_of=AS_OF)
        mixed = estimate_vehicle_value(seller, load_agent_vehicles(), as_of=AS_OF)
        self.assertEqual(mixed['reference'], real['reference'])
        self.assertEqual(mixed['comparables'], real['comparables'])
        v = self.sim[0]
        unsupported = SellerVehicleFrame(brand=v.brand, model=v.model, variant=v.variant, year=v.year, transmission=v.transmission, mileage_km=100000, condition='good')
        result = estimate_vehicle_value(unsupported, load_agent_vehicles(), as_of=AS_OF)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['reference'])

    def test_actual_controller_uses_default_simulation_and_checks_results(self):
        backend = ScriptedBackend(sensed(), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(backend=backend, state=SessionState(goal='buy', buyer=self.profile()), as_of=AS_OF)
        response = agent.handle('Show my matches.')
        self.assertEqual(response['status'], 'complete')
        self.assertEqual(response['result']['matched_count'], 5)
        self.assertTrue(all(c['passed'] for c in response['checks']))
        self.assertIn('2013 Ford Fiesta 1.5 Sport', response['message'])
        self.assertIn('MYR 21,999.00', response['message'])
        self.assertIn('70,000–75,000 km', response['message'])
        self.assertNotIn('SIMULATION', response['message'])
        self.assertNotIn('SIM-MRC', response['message'])
        self.assertNotIn('Unknown scoring features', response['message'])
        self.assertTrue(all(r['vehicle']['simulation'] for r in response['result']['matches']))
        self.assertTrue(all(r['vehicle_evidence']['safety']['normalized_value'] is None for r in response['result']['matches']))

    def test_ui_shows_vehicle_information_with_ids_only_in_details(self):
        p = self.profile()
        result = rank_vehicles_v2(p, filter_vehicles(p, load_agent_vehicles()))
        app = AppTest.from_string('from streamlit_app import render_buy\nimport streamlit as st\nrender_buy(st.session_state.result)')
        app.session_state.result = result
        app.run()
        self.assertFalse(app.exception)
        captions = '\n'.join(item.value for item in app.caption)
        self.assertFalse(any('SIM-MRC' in line for line in captions.splitlines() if line.startswith('RANK ')))
        self.assertIn('Record ID: SIM-MRC-V1-0934', captions)
        self.assertIn('Source observation date: Unknown', captions)
        self.assertNotIn('Historical scenario price', captions)
        self.assertNotIn('ID', app.dataframe[0].value.columns)
        self.assertNotIn('Supported score', app.dataframe[0].value.columns)
        self.assertIn('5.8 L/100 km', app.dataframe[0].value['Fuel reference'].tolist()[0])
        self.assertIn('Vehicle details and sources', [item.label for item in app.expander])


if __name__ == '__main__':
    unittest.main()
