"""Reproducible coverage audit; counts are not market accuracy measurements."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from vehicle_frame import load_vehicles
from vehicle_evidence import load_catalogue, evidence_for_vehicle
from price_regression import PriceDataset, gate

ROOT = Path(__file__).resolve().parent


def audit():
    cars = load_vehicles(ROOT/'data/vehicles_real.json')
    catalogue = load_catalogue()
    evidence_date = catalogue.reviewed_on
    listing_scopes = []
    for car in cars:
        evidence = evidence_for_vehicle(car, as_of=evidence_date, catalogue=catalogue)
        listing_scopes.append({'vehicle_id': car.vehicle_id, 'availability': car.availability,
                               'evidence_profile_id': evidence['profile_id'],
                               'reference_available': {key: evidence[key]['normalized_value'] is not None for key in ('safety', 'comfort', 'reliability')}})
    research_scopes = []
    for p in catalogue.profiles:
        identity = dict(brand=p.brand, model=p.model, year=p.years[0], variant=p.variants[0], transmission=p.transmissions[0])
        e = evidence_for_vehicle(identity, as_of=evidence_date, catalogue=catalogue, research_profile_id=p.profile_id)
        research_scopes.append({'profile_id': p.profile_id, 'years': p.years, 'variants': p.variants,
                                'automatic_matching': p.automatic_matching, 'review_count': len(e['reviews']), 'safety_present': e['safety']['report'] is not None,
                                'numeric_comfort_reference': e['comfort']['normalized_value'],
                                'numeric_reliability_reference': e['reliability']['normalized_value']})
    manifest = PriceDataset.model_validate_json((ROOT/'data/regression_manifest.json').read_bytes())
    return {'audited_on': datetime.now(timezone(timedelta(hours=8))).date().isoformat(), 'research_reviewed_on': evidence_date.isoformat(),
            'price_snapshot_date': '2026-10-15', 'price_rows': len(cars),
            'availability_counts': dict(Counter(c.availability for c in cars)),
            'price_type_counts': dict(Counter(c.price_type for c in cars)),
            'research_profile_count': len(catalogue.profiles),
            'research_model_count': len({(p.brand, p.model) for p in catalogue.profiles}),
            'listing_evidence_coverage': listing_scopes, 'research_profiles': research_scopes,
            'regression': {'active': False, 'usable_training_rows': len(manifest.rows), 'issues': gate(manifest)},
            'sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('data/vehicles_real.json', 'data/model_evidence_v2.json', 'data/regression_manifest.json')},
            'limits': ['Research profiles do not expand purchasable stock or price-comparable coverage.',
                       'Published sources and saved snapshots are not live inventory, observed transaction prices or verified failure statistics.',
                       'Current numeric review coverage is not independent relevance validation.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('audited_on', 'price_rows', 'research_profile_count', 'research_model_count', 'regression')}, indent=2))
