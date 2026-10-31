"""Convert the user's completed historical scenarios to validated Agent records.

Run with the project interpreter. This checks consistency, not source truth.
The original asking amounts are preserved as illustrative scenario prices.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import re
from vehicle_frame import PassengerCarFrame, load_vehicles

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/historical_simulation_source.json'
OUTPUT = ROOT / 'data/vehicles_simulation.json'
AUDIT = ROOT / 'docs/simulation-data-audit.json'
DATASET_URL = 'https://www.kaggle.com/datasets/tanshihjen/malaysia-resale-carlist'


def convert(data):
    if data.get('simulation_only') is not True:
        raise ValueError('Input must explicitly identify the simulation scope.')
    cars, groups, ids = [], set(), set()
    for row in data['records']:
        identity, spec = row['identity'], row['specifications']
        group = row['source_record_group_id']
        if row['simulation_only'] is not True or row['approved_for_regression'] is not False:
            raise ValueError('These records must remain simulation-only and unapproved for training.')
        if group in groups or row['record_id'] in ids:
            raise ValueError('Repeated source group or record ID; year alternatives cannot count twice.')
        groups.add(group)
        ids.add(row['record_id'])
        pair = re.match(r'^\s*(\d{4})\s*/\s*(\d{4})\b', row['raw_description'])
        if not pair or (identity['manufacturing_year'], row['registration_year']) != tuple(map(int, pair.groups())):
            raise ValueError('Year fields disagree with the user-supplied first-year/second-year simulation rule.')
        if spec['fuel_consumption_unit'] != 'L/100 km':
            raise ValueError('Unsupported fuel unit; an explicit conversion is required.')
        for field in ('brand', 'model', 'variant'):
            if not identity.get(field) or not identity[field].strip():
                raise ValueError(f'Missing identity: {field}')
        mileage = row['mileage']
        # A source interval remains an interval. No midpoint is manufactured.
        lower, upper = mileage['minimum_km'], mileage['maximum_km']
        car = PassengerCarFrame(
            vehicle_id='SIM-' + row['record_id'], brand=identity['brand'], model=identity['model'],
            variant=identity['variant'], year=identity['manufacturing_year'],
            price_myr=row['asking_price_myr'], seats=spec['seats'],
            source_kind='synthetic_demo', price_type='illustrative',
            source_reference=DATASET_URL + '#' + group,
            observed_on=None, source_updated_on=None, availability='unknown',
            transmission=row['raw_transmission'],
            mileage_km=int(lower) if mileage['parse_status'] == 'exact' else None,
            mileage_min_km=int(lower) if lower is not None else None,
            mileage_max_km=int(upper) if upper is not None else None,
            fuel_km_per_l=round(100 / spec['fuel_consumption'], 6), fuel_basis='synthetic_demo',
            fuel_source_reference=spec['specification_reference_url'],
            specs_source_reference=spec['specification_reference_url'],
            simulation={
                'source_record_group_id': group, 'source_row_number': row['source_row_number'],
                'raw_description': row['raw_description'], 'registration_year': row['registration_year'],
                'year_assumption': 'First year = manufacture; second year = registration. Simulation assumption only.',
                'fuel_l_per_100km': spec['fuel_consumption'], 'fuel_test_cycle': spec['fuel_consumption_test_cycle'],
                'specification_match_quality': spec['specification_match_quality'],
                'specification_reference_url': spec['specification_reference_url'],
                'specification_notes': spec['specification_notes'], 'simulation_only': True,
            },
            evidence_notes=[
                'User-completed historical simulation; identity, seats and fuel assumptions are not independently verified.',
                'Scenario price retains a historical asking amount; not current inventory, transaction price or market valuation evidence.',
                'Per-listing URL/date unknown. Dataset page and specification links do not identify or verify this physical vehicle.',
                'No regression approval; one source group appears once. Unique source rows do not prove VIN-distinct vehicles.',
            ],
        )
        cars.append(car)
    return cars


def main():
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    cars = convert(data)
    OUTPUT.write_text(json.dumps([v.model_dump(mode='json') for v in cars], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    loaded = load_vehicles(OUTPUT)
    identities = Counter((v.brand, v.model, v.variant, v.year, v.transmission) for v in loaded)
    audit = {
        'checked_on': '2026-10-31', 'scope': 'Local structure and consistency checks only; no external source verification.',
        'source_file': SOURCE.name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'output_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        'input_records': len(data['records']), 'loaded_simulation_records': len(loaded),
        'unique_source_groups': len({v.simulation.source_record_group_id for v in loaded}),
        'brands': sorted({v.brand for v in loaded}), 'brand_model_pairs': len({(v.brand, v.model) for v in loaded}),
        'seat_counts': dict(sorted(Counter(v.seats for v in loaded).items())),
        'fuel_cycles': dict(Counter(v.simulation.fuel_test_cycle for v in loaded)),
        'specification_quality': dict(Counter(v.simulation.specification_match_quality for v in loaded)),
        'price_range_myr': [min(v.price_myr for v in loaded), max(v.price_myr for v in loaded)],
        'largest_exact_identity_group': max(identities.values()),
        'all_listing_dates_unknown': all(v.observed_on is None and v.source_updated_on is None for v in loaded),
        'simulation_used_by_buy': True, 'simulation_used_as_market_valuation_evidence': False,
        'regression_approved_rows_added': 0,
        'limitations': ['97 slash-year source records only, not the entire 974-row CSV.',
                       'Latest supplied file supersedes the earlier two-alternative year review scheme.',
                       'Seat layouts and fuel values are user-supplied scenario assumptions.',
                       'Mixed or unspecified fuel cycles/estimated specifications disable fuel comparison for the eligible candidate set.',
                       'No accident, flood, fee, comfort, reliability or safety facts are invented.'],
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
