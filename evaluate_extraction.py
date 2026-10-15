"""Small inspectable live-model evaluation, separate from rule unit tests."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from main import extract_profile
from buyer_profile import reason_about_profile

CASES = [
    ('family', 'Budget RM60000, six-person family, mainly city commuting, save fuel.', {'budget_myr': 60000, 'family_size': 6, 'required_seats': None, 'usage': ['city_commute'], 'fuel_priority': 'high'}),
    ('missing', 'I want to buy a fuel-efficient car.', {'budget_myr': None, 'family_size': None, 'required_seats': None, 'usage': [], 'fuel_priority': 'high'}),
    ('negation', 'Budget RM50k, at least five seats for city commuting. Do not recommend Toyota.', {'budget_myr': 50000, 'required_seats': 5, 'usage': ['city_commute'], 'excluded_brands': ['Toyota'], 'preferred_brands': []}),
    ('monthly', 'I can only pay RM800 per month and want to buy a car.', {'budget_myr': None}),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:4b')
    args = parser.parse_args()
    records = []
    for name, text, expected in CASES:
        start = perf_counter()
        try:
            profile = extract_profile(text, args.model)
            actual = profile.model_dump()
            mismatches = {k: {'expected': v, 'actual': actual[k]} for k, v in expected.items() if actual[k] != v}
            record = {'case': name, 'input': text, 'expected': expected, 'actual': actual,
                      'passed': not mismatches, 'mismatches': mismatches,
                      'reasoning': reason_about_profile(profile)}
        except Exception as error:
            record = {'case': name, 'input': text, 'passed': False, 'error': str(error)}
        record['seconds'] = round(perf_counter() - start, 2)
        records.append(record)
        print(name, 'PASS' if record['passed'] else 'FAIL', record['seconds'], 'seconds', flush=True)
    Path('evaluation-results-english.json').write_text(json.dumps({'model': args.model, 'cases': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if all(r['passed'] for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
