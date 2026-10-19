"""Prepared, gated asking-price regression experiment; not an active sale tool.

Run without --train to inspect the data gap. Training requires a documented
usable Malaysian dataset. No model is generated from the current 17 snapshots.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median
import numpy as np
from pydantic import Field, model_validator
from vehicle_evidence import EvidenceFrame, Source, normalized

ROOT = Path(__file__).resolve().parent
POLICY = {'minimum_unique_vehicles': 100, 'minimum_groups_per_identity': 15,
          'maximum_source_age_days': 90, 'ridge_alpha': 1.0, 'holdout_fraction': .2,
          'maximum_mae_fraction_of_mean_price': .20}


class PriceRow(EvidenceFrame):
    # A verified anonymous car group keeps repeat/cross-site ads together.
    row_id: str = Field(min_length=1)
    vehicle_group_id: str = Field(min_length=1)
    dedup_evidence: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    model: str = Field(min_length=1)
    variant: str = Field(min_length=1)
    transmission: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    mileage_km: float = Field(ge=0, le=1500000)
    asking_price_myr: float = Field(gt=0)
    # Unknown fees are retained, not silently included in the target.
    known_fees_myr: float | None = Field(default=None, ge=0)
    fees_complete: bool | None = None
    target_basis: str = 'advertised_vehicle_price_excluding_fees'
    observed_on: date
    source_updated_on: date
    source: Source

    @model_validator(mode='after')
    def consistent_dates(self):
        if self.source_updated_on > self.observed_on or self.year > self.observed_on.year:
            raise ValueError('Price observation dates/year conflict.')
        if self.target_basis != 'advertised_vehicle_price_excluding_fees':
            raise ValueError('Do not mix transaction, total-on-road or aggregate proxy labels.')
        if self.fees_complete is True and self.known_fees_myr is None:
            raise ValueError('Complete fees need an explicit amount, including explicit zero.')
        return self


class PriceDataset(EvidenceFrame):
    schema_version: int = 1
    market: str = 'Malaysia'
    use_permissions_verified: bool = False
    permission_basis_ref: str | None = None
    checked_on: date
    rows: list[PriceRow]


def identity(row):
    # No adjacent trim/year substitution; year is a numerical input within scope.
    return '|'.join(normalized(getattr(row, k)) for k in ('brand', 'model', 'variant', 'transmission'))


def gate(dataset):
    """Return concrete problems; a count threshold is policy, not proof of quality."""
    issues = []
    if dataset.schema_version != 1 or dataset.market != 'Malaysia':
        issues.append('Expected schema 1 Malaysian row-level asking-price data.')
    if not dataset.use_permissions_verified or not dataset.permission_basis_ref:
        issues.append('Dataset use conditions/permission have not been documented and verified.')
    if len({r.row_id for r in dataset.rows}) != len(dataset.rows):
        issues.append('Duplicate row IDs.')
    groups = defaultdict(list)
    source_groups = defaultdict(set)
    for row in dataset.rows:
        groups[row.vehicle_group_id].append(row)
        source_groups[row.source.url].add(row.vehicle_group_id)
        age = (dataset.checked_on - row.source_updated_on).days
        if row.observed_on > dataset.checked_on or not 0 <= age <= POLICY['maximum_source_age_days']:
            issues.append('Stale/future price source: ' + row.row_id)
    if any(len(ids) > 1 for ids in source_groups.values()):
        issues.append('A source URL is assigned to multiple vehicle groups; deduplication is unresolved.')
    if len(groups) < POLICY['minimum_unique_vehicles']:
        issues.append('Fewer than 100 independently deduplicated vehicles; count is a course policy floor, not statistical assurance.')
    counts = Counter()
    for key, rows in groups.items():
        if len({identity(r) for r in rows}) != 1 or len({r.year for r in rows}) != 1:
            issues.append('Conflicting identity within vehicle group: ' + key)
        counts[identity(rows[0])] += 1
    if len(counts) < 2 or any(n < POLICY['minimum_groups_per_identity'] for n in counts.values()):
        issues.append('Need at least two exact identities, each with 15 unique cars, before a stratified group holdout.')
    return list(dict.fromkeys(issues))


def split_groups(rows):
    # Collapse repeat ads to the most recently checked row, before splitting.
    groups = defaultdict(list)
    for row in rows:
        groups[row.vehicle_group_id].append(row)
    strata = defaultdict(list)
    for group in groups.values():
        row = max(group, key=lambda r: (r.observed_on, r.source_updated_on, r.row_id))
        strata[identity(row)].append(row)
    train, test = [], []
    for items in strata.values():
        # Hash order is stable across Python processes and platform versions.
        items.sort(key=lambda r: hashlib.sha256(('split-v1:' + r.vehicle_group_id).encode()).hexdigest())
        count = max(3, int(len(items) * POLICY['holdout_fraction']))
        test.extend(items[:count])
        train.extend(items[count:])
    return train, test


def numeric(row):
    return [row.observed_on.year - row.year, row.mileage_km]


def design(rows, spec):
    # Means, scales and category vocabulary are fitted on training data only.
    matrix = []
    for row in rows:
        category = identity(row)
        if category not in spec['identities']:
            raise ValueError('Unseen identity: abstain rather than extrapolate.')
        numbers = (np.asarray(numeric(row)) - spec['mean']) / spec['scale']
        matrix.append([1.0, *numbers, *[float(category == c) for c in spec['identities']]])
    return np.asarray(matrix, dtype=float)


def fit_ridge(train):
    # Small educational closed-form Ridge: solve, do not invert the matrix.
    values = np.asarray([numeric(r) for r in train], dtype=float)
    spec = {'mean': values.mean(axis=0).tolist(), 'scale': np.where(values.std(axis=0) > 0, values.std(axis=0), 1).tolist(),
            'identities': sorted({identity(r) for r in train})}
    x = design(train, spec)
    y = np.asarray([r.asking_price_myr for r in train])
    penalty = np.eye(x.shape[1]) * POLICY['ridge_alpha']
    penalty[0, 0] = 0  # The intercept is not penalized.
    coefficients = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    return spec, coefficients


def experiment(dataset):
    issues = gate(dataset)
    if issues:
        return {'status': 'blocked_by_data', 'issues': issues, 'policy': POLICY, 'active_in_agent': False}
    train, test = split_groups(dataset.rows)
    spec, coefficients = fit_ridge(train)
    prediction = design(test, spec) @ coefficients
    actual = np.asarray([r.asking_price_myr for r in test])
    baseline = {c: median(r.asking_price_myr for r in train if identity(r) == c) for c in spec['identities']}
    base_error = np.asarray([baseline[identity(r)] for r in test]) - actual
    error = prediction - actual
    mae = float(np.abs(error).mean())
    baseline_mae = float(np.abs(base_error).mean())
    accepted = bool(np.isfinite(prediction).all() and (prediction > 0).all() and mae < baseline_mae and mae / actual.mean() <= POLICY['maximum_mae_fraction_of_mean_price'])
    # Even a passing experiment is not silently enabled in production.
    return {'status': 'candidate_passed' if accepted else 'candidate_failed', 'active_in_agent': False,
            'target': 'Malaysian advertised vehicle asking price excluding fees; never transaction or dealer offer',
            'policy': POLICY, 'preprocessing': spec, 'coefficients': coefficients.tolist(),
            'feature_order': ['intercept', 'age_at_observation_years_standardized', 'mileage_km_standardized', *spec['identities']],
            'holdout': {'mae_myr': mae, 'rmse_myr': float(np.sqrt((error ** 2).mean())), 'identity_median_baseline_mae_myr': baseline_mae},
            'train_row_ids': [r.row_id for r in train], 'test_row_ids': [r.row_id for r in test],
            'train_groups': [r.vehicle_group_id for r in train], 'test_groups': [r.vehicle_group_id for r in test],
            'checked_on': dataset.checked_on.isoformat(), 'permission_basis_ref': dataset.permission_basis_ref,
            'limits': ['Fixed grouped development holdout; not independent external market validation.',
                       'No historical trend, brand depreciation curve, condition/damage penalty or causal mileage effect is established.',
                       'Before activation: per-identity error review, independent cases, date/domain limits, checker and UI integration. MAE is not a confidence interval.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT/'data/regression_manifest.json')
    parser.add_argument('--train', action='store_true', help='Run only after data gates pass; outputs an inactive candidate experiment')
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    dataset = PriceDataset.model_validate_json(raw)
    result = experiment(dataset) if args.train else {'status': 'ready_for_experiment' if not gate(dataset) else 'blocked_by_data', 'issues': gate(dataset), 'policy': POLICY, 'active_in_agent': False}
    result.update(dataset_sha256=hashlib.sha256(raw).hexdigest(), row_count=len(dataset.rows))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
