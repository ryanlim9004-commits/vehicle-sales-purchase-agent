"""Reproducible live English extraction + curated-data scoring smoke test."""
# Learning guide:
# Exercise actual English extraction, hard filtering and lifestyle scoring.
# Expected top IDs belong to the frozen dataset and the stated scoring policy.
# Running the script replaces stage3-live-results.json; no website search occurs.
import json
from pathlib import Path
from time import perf_counter
from main import extract_profile
from vehicle_frame import load_vehicles
from matching import filter_vehicles
from scoring import rank_vehicles

ROOT = Path(__file__).resolve().parent
CASES = [
    {'name':'city_luggage', 'text':'Budget RM50000, at least five seats, mainly city commuting. Fuel economy and a spacious boot are high priorities.',
     'expected':{'budget_myr':50000, 'required_seats':5, 'usage':['city_commute'], 'fuel_priority':'high', 'space_priority':'high'},
     'expected_top':'PT_K4EDNMNYPG'},
    {'name':'six_person', 'text':'Budget RM60000, six-person family, mainly city commuting. Save fuel and do not want Toyota.',
     'expected':{'budget_myr':60000, 'family_size':6, 'usage':['city_commute'], 'fuel_priority':'high', 'excluded_brands':['Toyota']},
     'expected_top':'CL18923892'},
]


if __name__ == '__main__':
    records = []
    cars = load_vehicles(ROOT/'data'/'vehicles_real.json')
    for case in CASES:
        start = perf_counter()
        try:
            p = extract_profile(case['text'], 'qwen3:4b')
            result = rank_vehicles(p, filter_vehicles(p, cars))
            actual = p.model_dump()
            mismatches = {k:{'expected':v,'actual':actual[k]} for k,v in case['expected'].items() if actual[k] != v}
            record = dict(case=case['name'], input=case['text'], expected=case['expected'], actual=actual,
                          mismatches=mismatches, result=result,
                          passed=not mismatches and result['top_vehicle_ids'][0] == case['expected_top'])
        except Exception as error:
            record = dict(case=case['name'], passed=False, error=str(error))
        record['seconds'] = round(perf_counter()-start, 2)
        records.append(record)
        print(record['case'], 'PASS' if record['passed'] else 'FAIL', record['seconds'], 'seconds', flush=True)
    (ROOT/'stage3-live-results.json').write_text(json.dumps({'model':'qwen3:4b','cases':records},ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if all(r['passed'] for r in records) else 1)
