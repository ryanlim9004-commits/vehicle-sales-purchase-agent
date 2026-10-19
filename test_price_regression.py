"""Synthetic engineering checks only: not trained Malaysian market evidence."""
import json
import unittest
from pathlib import Path
from datetime import date
import numpy as np
from pydantic import ValidationError
from price_regression import PriceRow, PriceDataset, gate, split_groups, fit_ridge, design, experiment


def synthetic_row(i, model='TeachingA'):
    # Fake domain/brand labels are intentionally obvious; never saved as stock.
    return PriceRow.model_validate_json(json.dumps({
        'row_id': f'{model}-{i}', 'vehicle_group_id': f'{model}-car-{i}', 'dedup_evidence': 'Synthetic unit-test group only',
        'brand': 'Synthetic', 'model': model, 'variant': 'Test', 'transmission': 'Automatic',
        'year': 2018+i%7, 'mileage_km': 10000+i*1000, 'asking_price_myr': 10000+(i%7)*2000-i*10,
        'observed_on': '2026-10-16', 'source_updated_on': '2026-10-15',
        'source': {'source_id': f'{model}-{i}', 'family': 'test', 'url': f'https://example.invalid/{model}/{i}', 'author': 'Synthetic test', 'locator': 'Unit test, not a Malaysian listing'}
    }))


class RegressionPreparationTests(unittest.TestCase):
    def dataset(self):
        # Permission true here is fixture metadata, not a real permission claim.
        return PriceDataset(checked_on=date(2026, 10, 16), use_permissions_verified=True,
                            permission_basis_ref='Synthetic engineering fixture; never market training',
                            rows=[synthetic_row(i, model) for model in ('TeachingA', 'TeachingB') for i in range(60)])

    def test_current_dataset_blocks_training_without_artifact(self):
        data = PriceDataset.model_validate_json((Path(__file__).parent/'data/regression_manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(gate(data))
        result = experiment(data)
        self.assertEqual(result['status'], 'blocked_by_data')
        self.assertNotIn('coefficients', result)
        self.assertFalse(result['active_in_agent'])

    def test_permission_and_freshness_gates(self):
        data = self.dataset()
        self.assertEqual(gate(data), [])
        data.use_permissions_verified = False
        data.rows[0].source_updated_on = date(2025, 1, 1)
        issues = gate(data)
        self.assertTrue(any('permission' in i for i in issues))
        self.assertTrue(any('Stale' in i for i in issues))

    def test_price_basis_and_unknown_fees(self):
        row = synthetic_row(1).model_dump(mode='json')
        self.assertIsNone(row['known_fees_myr'])
        row['target_basis'] = 'transaction'
        with self.assertRaises(ValidationError):
            PriceRow.model_validate_json(json.dumps(row))

    def test_duplicate_car_and_url_cannot_leak(self):
        data = self.dataset()
        repeat = data.rows[0].model_copy(deep=True)
        repeat.row_id += '-repeat'
        repeat.asking_price_myr += 1000
        data.rows.append(repeat)
        train, test = split_groups(data.rows)
        self.assertFalse({r.vehicle_group_id for r in train} & {r.vehicle_group_id for r in test})
        self.assertEqual(len(train)+len(test), 120)
        repeat.vehicle_group_id = 'unresolved-other-car'
        self.assertTrue(any('source URL' in i for i in gate(data)))

    def test_training_only_preprocessing_and_finite_predictions(self):
        train, test = split_groups(self.dataset().rows)
        spec, coefficients = fit_ridge(train)
        self.assertTrue(np.isfinite(design(test, spec) @ coefficients).all())
        self.assertAlmostEqual(spec['mean'][1], np.mean([r.mileage_km for r in train]))
        before = json.dumps(spec)
        test[0].mileage_km = 999999
        design(test, spec)
        self.assertEqual(json.dumps(spec), before)
        unseen = synthetic_row(1, 'Unseen')
        with self.assertRaises(ValueError):
            design([unseen], spec)

    def test_experiment_reports_baseline_holdout_and_never_enables(self):
        result = experiment(self.dataset())
        self.assertIn(result['status'], ('candidate_passed', 'candidate_failed'))
        self.assertIn('identity_median_baseline_mae_myr', result['holdout'])
        self.assertFalse(set(result['train_groups']) & set(result['test_groups']))
        self.assertFalse(result['active_in_agent'])


if __name__ == '__main__':
    unittest.main()
