"""Train a bounded historical teaching model, separately from market approval.

The user's 31 Oct instruction permits combining saved ads and historical
simulation records for this experiment. Original provenance and approval flags
are never changed. NumPy Ridge learns log scenario prices, not transaction or
dealer trade-in prices. Run this file to reproduce the model and its audit.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from statistics import median

import numpy as np

ROOT = Path(__file__).resolve().parent
ARTIFACT = ROOT / 'data/historical_price_model.json'
REPORT = ROOT / 'docs/historical-regression-results.json'
POLICY = {'version': 'historical-ridge-v1', 'ridge_alpha': 1.0,
          'minimum_model_groups': 5, 'maximum_mae_fraction': .20,
          'maximum_relative_error': .40,
          'target': 'Historical illustrative advertised vehicle price in MYR, excluding fees',
          'mileage_proxy': 'Interval midpoint for model features only; source intervals are preserved',
          'evaluation': 'Leave one conservative source group out; transforms fitted on each training fold',
          'authorization': 'User explicitly requested combining confirmed and historical simulation data on 31 Oct 2026'}


def normal(value):
    return ' '.join(str(value or '').casefold().split())


def fingerprint(cars):
    """Any catalogue change invalidates the fitted artifact, including provenance."""
    data = [v.model_dump(mode='json') for v in sorted(cars, key=lambda v: v.vehicle_id)]
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def model_key(row):
    return '|'.join(normal(row[k]) for k in ('brand', 'model', 'transmission'))


def prepare_rows(cars):
    """Preserve origins; collapse identical identity/year/mileage signatures.

    A repeated signature may be the same physical car. Keeping one stable row
    is conservative; it does not prove VIN independence for different rows.
    Dates remain unknown for simulation records and are never replaced by today.
    """
    selected, exclusions = {}, []
    for car in sorted(cars, key=lambda v: v.vehicle_id):
        if car.price_myr is None or car.variant is None:
            exclusions.append({'vehicle_id': car.vehicle_id, 'reason': 'Price/variant missing.'})
            continue
        if car.simulation is None and (car.source_kind != 'listing' or car.price_type != 'asking'):
            exclusions.append({'vehicle_id': car.vehicle_id, 'reason': 'Not an advertisement or labelled historical scenario.'})
            continue
        low = car.mileage_km if car.mileage_km is not None else car.mileage_min_km
        high = car.mileage_km if car.mileage_km is not None else car.mileage_max_km
        if low is None or high is None or not car.transmission:
            exclusions.append({'vehicle_id': car.vehicle_id, 'reason': 'Mileage bounds or transmission unknown; no mileage invented.'})
            continue
        row = {k: getattr(car, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}
        row.update(row_id=car.vehicle_id, price_myr=car.price_myr, mileage_min_km=low,
                   mileage_max_km=high, mileage_proxy_km=(low + high) / 2,
                   provenance='historical_simulation' if car.simulation else 'saved_asking_snapshot',
                   observed_on=car.observed_on.isoformat() if car.observed_on else None,
                   source_reference=car.source_reference, availability=car.availability)
        signature = '|'.join([model_key(row), normal(row['variant']), str(row['year']), str(low), str(high)])
        group = hashlib.sha256(signature.encode()).hexdigest()[:20]
        if group in selected:
            exclusions.append({'vehicle_id': car.vehicle_id, 'reason': 'Possible repeated vehicle signature; one stable representative retained.',
                               'retained_row_id': selected[group]['row_id']})
            continue
        row['group_id'] = group
        selected[group] = row
    return list(selected.values()), exclusions


def numerical(row):
    # Manufacturing year is used directly: missing ad dates cannot establish age
    # at observation. Do not claim a current depreciation curve from this slope.
    engine = re.search(r'(?<!\d)([0-6]\.\d)(?!\d)', row['variant'])
    return [float(row['year']), np.log1p(row['mileage_proxy_km']), float(engine.group(1)) if engine else 0.0]


def fit(rows):
    values = np.asarray([numerical(r) for r in rows], dtype=float)
    spec = {'mean': values.mean(axis=0).tolist(),
            'scale': np.where(values.std(axis=0) > 0, values.std(axis=0), 1.0).tolist(),
            'models': sorted({model_key(r) for r in rows})}
    matrix = design(rows, spec)
    target = np.log([r['price_myr'] for r in rows])
    penalty = np.eye(matrix.shape[1]) * POLICY['ridge_alpha']
    penalty[0, 0] = 0
    coef = np.linalg.solve(matrix.T @ matrix + penalty, matrix.T @ target)
    return spec, coef.tolist()


def design(rows, spec):
    result = []
    for row in rows:
        category = model_key(row)
        if category not in spec['models']:
            raise ValueError('Unseen brand/model/transmission: no prediction.')
        numbers = (np.asarray(numerical(row)) - spec['mean']) / spec['scale']
        result.append([1., *numbers.tolist(), *[float(category == c) for c in spec['models']]])
    return np.asarray(result)


def predict_rows(rows, spec, coefficients):
    values = np.exp(design(rows, spec) @ np.asarray(coefficients))
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Nonfinite or nonpositive model prediction.')
    return values


def train(cars):
    """Freeze a simple model/policy; report failures without relaxing thresholds."""
    rows, exclusions = prepare_rows(cars)
    if len(rows) < 10:
        raise ValueError('Not enough historical rows to run this experiment.')
    groups = defaultdict(list)
    for row in rows:
        groups[model_key(row)].append(row)
    observations = defaultdict(list)
    # Singleton categories are included in fitting but never sold as validated
    # price coverage. Only repeated models receive a cross-validation score.
    for held in rows:
        category = model_key(held)
        if len(groups[category]) < POLICY['minimum_model_groups']:
            continue
        training = [r for r in rows if r['group_id'] != held['group_id']]
        spec, coef = fit(training)
        prediction = float(predict_rows([held], spec, coef)[0])
        base = median(r['price_myr'] for r in training if model_key(r) == category)
        observations[category].append({'row_id': held['row_id'], 'held_out_group': held['group_id'],
                                       'actual_price_myr': held['price_myr'], 'prediction_myr': prediction,
                                       'baseline_myr': base,
                                       'training_group_digest': hashlib.sha256('|'.join(sorted(r['group_id'] for r in training)).encode()).hexdigest()})
    scores = {}
    for category, items in observations.items():
        error = np.asarray([r['prediction_myr'] - r['actual_price_myr'] for r in items])
        actual = np.asarray([r['actual_price_myr'] for r in items])
        baseline_error = np.asarray([r['baseline_myr'] - r['actual_price_myr'] for r in items])
        mae, base = float(np.abs(error).mean()), float(np.abs(baseline_error).mean())
        relative = float(np.abs(error / actual).max())
        passed = mae < base and mae / actual.mean() <= POLICY['maximum_mae_fraction'] and relative <= POLICY['maximum_relative_error']
        scores[category] = {'group_count': len(items), 'mae_myr': mae, 'rmse_myr': float(np.sqrt((error**2).mean())),
                            'baseline_mae_myr': base, 'mae_fraction_of_mean': float(mae / actual.mean()),
                            'maximum_relative_error': relative, 'eligible_for_historical_demo': bool(passed),
                            'predictions': items}
    spec, coefficients = fit(rows)
    artifact = {'schema_version': 1, 'scope': 'historical_simulation_only',
                'market_validated': False, 'dataset_sha256': fingerprint(cars), 'policy': POLICY,
                'preprocessing': spec, 'coefficients': coefficients, 'training_rows': rows,
                'model_evaluation': scores}
    artifact['model_id'] = 'historical-ridge-' + hashlib.sha256(json.dumps(artifact, sort_keys=True).encode()).hexdigest()[:16]
    report = {k: artifact[k] for k in ('model_id', 'scope', 'market_validated', 'dataset_sha256', 'policy', 'model_evaluation')}
    report.update(input_records=len(cars), training_rows=len(rows),
                  provenance_counts=dict(Counter(r['provenance'] for r in rows)), exclusions=exclusions,
                  eligible_models=[k for k, v in scores.items() if v['eligible_for_historical_demo']],
                  sparse_models={k: len(v) for k, v in groups.items() if len(v) < POLICY['minimum_model_groups']},
                  limitations=['Historical prices with unknown dates cannot establish current market value.',
                               'Manufacturing year, interval midpoint and displacement are features; causal depreciation/mileage effects are not established.',
                               'Generation/trim equipment, condition and damage are not learned. Seen variants and numeric ranges constrain use.',
                               'Source-signature grouping is conservative, not verified cross-site VIN deduplication.',
                               'Grouped leave-one-out development evaluation is not independent or chronological market validation.',
                               'MAE is an average error, not a confidence interval or guaranteed bound.',
                               'Sold/reserved advertisements remain asking labels; no transaction/dealer-offer training labels exist.'])
    return artifact, report


@lru_cache(maxsize=4)
def _read_artifact(path, modified_ns, length):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_artifact(cars, path=ARTIFACT):
    try:
        info = Path(path).stat()
        result = _read_artifact(str(path), info.st_mtime_ns, info.st_size)
        if (result['schema_version'] != 1 or result['scope'] != 'historical_simulation_only'
                or result['market_validated'] is not False or result['policy'] != POLICY
                or result['dataset_sha256'] != fingerprint(cars)):
            return None
        model_id = result['model_id']
        payload = {k: v for k, v in result.items() if k != 'model_id'}
        if model_id != 'historical-ridge-' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]:
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def estimate(profile, cars, *, artifact_path=ARTIFACT):
    """Return an explicitly historical prediction, or a concrete refusal reason."""
    outcome = {'status': 'unavailable', 'scope': 'historical_simulation_only', 'market_validated': False,
               'estimated_asking_price_myr': None, 'illustrative_error_band_myr': None}
    artifact = load_artifact(cars, artifact_path)
    if artifact is None:
        return outcome | {'reason': 'Historical model unavailable or catalogue changed. Re-run training and review its report.'}
    identity = {k: getattr(profile, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}
    if any(v is None for v in identity.values()):
        return outcome | {'reason': 'Brand, model, exact variant, manufacturing year and transmission are required.'}
    category = model_key(identity)
    score = artifact['model_evaluation'].get(category)
    if score is None or not score['eligible_for_historical_demo']:
        return outcome | {'reason': 'This brand/model/transmission lacks enough evaluated source groups or did not beat the median baseline.', 'model_key': category}
    rows = [r for r in artifact['training_rows'] if model_key(r) == category]
    variants = [r for r in rows if normal(r['variant']) == normal(profile.variant)]
    if not variants:
        return outcome | {'reason': 'Exact variant was not seen in training; no automatic trim substitution.'}
    year_low, year_high = min(r['year'] for r in variants), max(r['year'] for r in variants)
    if not year_low <= profile.year <= year_high:
        return outcome | {'reason': f'Manufacturing year is outside the seen variant range {year_low}-{year_high}; no extrapolation.'}
    mileage = getattr(profile, 'mileage_km', None)
    if mileage is None:
        return outcome | {'reason': 'Odometer mileage with a distance unit is needed for the historical regression reference.', 'needs_mileage': True}
    low, high = min(r['mileage_min_km'] for r in variants), max(r['mileage_max_km'] for r in variants)
    if not low <= mileage <= high:
        return outcome | {'reason': f'Odometer is outside the seen variant range {low:g}-{high:g} km; no extrapolation.'}
    query = identity | {'mileage_proxy_km': mileage}
    prediction = float(predict_rows([query], artifact['preprocessing'], artifact['coefficients'])[0])
    # This simple visual error guide is labelled honestly; it is NOT calibrated
    # coverage or a range of observed comparables for this input vehicle.
    width = score['mae_myr']
    from valuation import money
    return {'status': 'historical_prediction', 'scope': 'historical_simulation_only', 'market_validated': False,
            'model_id': artifact['model_id'], 'dataset_sha256': artifact['dataset_sha256'], 'model_key': category,
            'estimated_asking_price_myr': money(prediction),
            'illustrative_error_band_myr': [money(max(.01, prediction - width)), money(prediction + width)],
            'error_band_basis': 'Prediction +/- development leave-one-source-group-out MAE; not a confidence interval or guaranteed range.',
            'evaluation': {k: v for k, v in score.items() if k != 'predictions'},
            'input': identity | {'mileage_km': mileage},
            'training_scope': {'manufacturing_year_range_for_variant': [year_low, year_high],
                               'mileage_range_km_for_variant': [low, high],
                               'model_group_count': len(rows), 'variant_group_count': len(variants)},
            'sources': [{'vehicle_id': r['row_id'], 'source_reference': r['source_reference'],
                         'provenance': r['provenance'], 'observed_on': r['observed_on']} for r in rows],
            'limitations': ['Historical illustrative price; not current market value, transaction price, dealer trade-in offer or guaranteed private-sale proceeds.',
                           'Training mileage intervals use midpoint proxies; individual odometers and dates are not inferred.',
                           'No learned condition/damage adjustment; different generations/trim equipment and unverified source assumptions can affect the result.',
                           'Only development evaluation; obtain independent, dated market data before making market-accuracy claims.']}


def verify_prediction(prediction, cars=None):
    """Recompute against the current hashed dataset/model; reject edited output."""
    from seller_profile import SellerVehicleFrame
    from vehicle_frame import load_agent_vehicles
    try:
        canonical = estimate(SellerVehicleFrame.model_validate(prediction['input']),
                             cars if cars is not None else load_agent_vehicles())
        return canonical['status'] == 'historical_prediction' and canonical == prediction
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ARTIFACT)
    parser.add_argument('--report', type=Path, default=REPORT)
    args = parser.parse_args()
    from vehicle_frame import load_agent_vehicles
    artifact, report = train(load_agent_vehicles())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('sparse_models', 'model_evaluation')}, indent=2))


if __name__ == '__main__':
    main()
