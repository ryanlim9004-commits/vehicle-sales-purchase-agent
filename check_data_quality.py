"""Reproducible source/grain/completeness checks for the curated seed dataset."""
# Learning guide:
# Profile the saved listing snapshot and compare local source receipts.
# Report missingness, possible duplicate ads and exact comparable-group coverage.
# The collection date is fixed for reproducibility; this is not a live stock check.
import json
from collections import Counter
from datetime import date
from pathlib import Path
from vehicle_frame import load_vehicles

ROOT = Path(__file__).resolve().parent


# Compare local IDs, URLs and recorded fields; agreement proves local lineage consistency, not
# advertisement truth.
def check_receipts(rows, receipts):
    """Check local lineage consistency, not whether the original advert is true."""
    issues = []
    by_id = {v.vehicle_id: v.model_dump(mode='json') for v in rows}
    sources = receipts.get('sources', [])
    receipt_ids = [r.get('vehicle_id') for r in sources]
    if len(receipt_ids) != len(set(receipt_ids)):
        issues.append('Duplicate vehicle IDs in source receipts.')
    if set(receipt_ids) != set(by_id):
        issues.append('Source-receipt IDs do not exactly cover the dataset IDs.')
    for receipt in sources:
        identity = receipt.get('vehicle_id')
        row = by_id.get(identity)
        if row is None:
            continue
        if receipt.get('url') != row['source_reference']:
            issues.append(f'{identity}: source URL differs from its receipt.')
        fields = receipt.get('fields', {})
        required = {'brand', 'model', 'variant', 'year', 'price_myr', 'price_type', 'seats', 'mileage_km', 'mileage_min_km', 'mileage_max_km', 'availability', 'source_updated_on'}
        for name in sorted(required | set(fields)):
            if name not in fields or fields[name] != row.get(name):
                issues.append(f'{identity}: {name} differs from or is missing in its receipt.')
    return issues


# Summarize a validated dataset, receipt issues and exact comparable coverage using the fixed
# collection date.
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
    receipt_check = {'status': 'not_checked', 'note': 'No matching curated receipt file selected.'}
    if Path(path).resolve() == (ROOT/'data'/'vehicles_real.json').resolve():
        receipt_path = ROOT/'data'/'source_receipts.json'
        if receipt_path.exists():
            receipt_issues = check_receipts(rows, json.loads(receipt_path.read_text(encoding='utf-8')))
            critical.extend(receipt_issues)
            receipt_check = {'status': 'failed' if receipt_issues else 'passed', 'checked_records': len(rows), 'issues': receipt_issues,
                             'note': 'Local receipt consistency only; this does not independently verify source truth or current stock.'}
        else:
            critical.append('Curated source receipt file is missing.')
            receipt_check = {'status': 'failed', 'issues': ['Receipt file missing.']}
    groups = Counter((v.brand, v.model, v.variant, v.year, v.transmission) for v in rows
                     if v.source_kind == 'listing' and v.price_type == 'asking' and v.availability == 'listed_snapshot'
                     and v.price_myr is not None and v.source_updated_on is not None
                     and 0 <= (date(2026, 10, 15) - v.source_updated_on).days <= 90
                     and v.observed_on <= date(2026, 10, 15))
    # Total rows alone do not establish valuation support: count eligible
    # observations separately for each exact identity under the freshness rule.
    comparable_groups = [dict(zip(('brand', 'model', 'variant', 'year', 'transmission'), signature), count=n, meets_minimum_three=n >= 3)
                         for signature, n in sorted(groups.items(), key=lambda item: str(item[0]))]
    return {'snapshot_date': '2026-10-15', 'row_count': count,
            'grain': 'one source advertisement/inventory ID; cross-platform VIN identity is not verified',
            'unique_ids': len({v.vehicle_id for v in rows}), 'unique_source_urls': len(set(urls)),
            'availability': dict(Counter(v.availability for v in rows)),
            'price_type': dict(Counter(v.price_type for v in rows)),
            'by_model': dict(Counter(f'{v.brand} {v.model}' for v in rows)),
            'missingness': missing, 'mileage_exact_or_range_count': known_mileage,
            'source_update_older_than_60_days_ids': old, 'possible_duplicate_signatures': duplicates,
            'receipt_check': receipt_check,
            'valuation_comparable_groups': comparable_groups,
            'comparable_policy': 'Exact brand/model/variant/year/transmission; eligible asking snapshots with known updates within 90 days of 2026-10-15; minimum three. Not a statistical sufficiency guarantee.',
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
