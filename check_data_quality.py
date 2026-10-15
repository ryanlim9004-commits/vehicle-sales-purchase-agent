"""Reproducible source/grain/completeness checks for the curated seed dataset."""
import json
from collections import Counter
from datetime import date
from pathlib import Path
from vehicle_frame import load_vehicles

ROOT = Path(__file__).resolve().parent


def profile_data(path):
    rows = load_vehicles(path)
    count = len(rows)
    urls = [v.source_reference for v in rows]
    critical = []
    if len(urls) != len(set(urls)):
        critical.append('Duplicate source URLs: possible repeated advertisements.')
    if any(v.observed_on > date(2026, 10, 15) for v in rows):
        critical.append('Observation date beyond this fixed 2026-10-15 collection snapshot.')
    fields = ['variant', 'price_myr', 'seats', 'mileage_km', 'fuel_km_per_l', 'boot_litres', 'condition', 'source_updated_on']
    missing = {f: {'null_count': sum(getattr(v, f) is None for v in rows),
                   'null_percent': round(100 * sum(getattr(v, f) is None for v in rows) / count, 2) if count else 0} for f in fields}
    known_mileage = sum(v.mileage_km is not None or (v.mileage_min_km is not None and v.mileage_max_km is not None) for v in rows)
    old = [v.vehicle_id for v in rows if v.source_updated_on and (v.observed_on - v.source_updated_on).days > 60]
    signature_groups = {}
    for v in rows:
        signature = (v.brand, v.model, v.variant, v.year, v.price_myr, v.mileage_km, v.mileage_min_km, v.mileage_max_km)
        signature_groups.setdefault(signature, []).append(v.vehicle_id)
    duplicates = [ids for ids in signature_groups.values() if len(ids) > 1]
    return {'snapshot_date': '2026-10-15', 'row_count': count,
            'grain': 'one source advertisement/inventory ID; cross-platform VIN identity is not verified',
            'unique_ids': len({v.vehicle_id for v in rows}), 'unique_source_urls': len(set(urls)),
            'availability': dict(Counter(v.availability for v in rows)),
            'price_type': dict(Counter(v.price_type for v in rows)),
            'by_model': dict(Counter(f'{v.brand} {v.model}' for v in rows)),
            'missingness': missing, 'mileage_exact_or_range_count': known_mileage,
            'source_update_older_than_60_days_ids': old, 'possible_duplicate_signatures': duplicates,
            'critical_issues': critical,
            'limitations': ['Small convenience sample, not representative of the Malaysian market.',
                           'No verified transaction prices or independently inspected condition labels.',
                           'No VIN-based cross-platform deduplication; distinct ads do not prove distinct cars.',
                           'Source update dates and retrieved cached pages cannot confirm current stock.',
                           'Fuel claims use different conditions; scoring disables mixed-basis fuel comparison.',
                           'Missing mileage points may be available as ranges; no midpoint imputation.']}


if __name__ == '__main__':
    result = profile_data(ROOT/'data'/'vehicles_real.json')
    (ROOT/'data'/'quality_report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['critical_issues'] else 0)
