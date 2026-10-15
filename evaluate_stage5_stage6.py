"""Acceptance scenarios for data/scoring and valuation. Optional real Ollama calls."""
import argparse
import json
from datetime import date
from pathlib import Path
from buyer_profile import BuyerProfileFrame
from seller_profile import SellerVehicleFrame, extract_seller_profile
from main import extract_profile
from vehicle_frame import load_vehicles
from matching import filter_vehicles
from scoring import rank_vehicles
from valuation import estimate_vehicle_value
from check_data_quality import profile_data

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def run(live=False):
    cars = load_vehicles(ROOT/'data/vehicles_real.json')
    city = BuyerProfileFrame.model_validate_json((ROOT/'examples/city_buyer.json').read_text(encoding='utf-8'))
    family = BuyerProfileFrame(budget_myr=60000, family_size=6, usage=['city_commute'], fuel_priority='high', excluded_brands=['Toyota'])
    seller = SellerVehicleFrame.model_validate_json((ROOT/'examples/seller_alza.json').read_text(encoding='utf-8'))
    checks = []

    def record(name, expected, actual):
        checks.append({'case': name, 'expected': expected, 'actual': actual, 'passed': expected == actual})

    quality = profile_data(ROOT/'data/vehicles_real.json')
    record('source_receipt_and_quality', {'critical_issues': [], 'receipts': 'passed'},
           {'critical_issues': quality['critical_issues'], 'receipts': quality['receipt_check']['status']})
    ranking = rank_vehicles(city, filter_vehicles(city, cars))
    record('city_lifestyle_ranking', ['PT_K4EDNMNYPG', 'PT_7PRLM3GLPK', 'CS_C606800'], ranking['top_vehicle_ids'])
    family_result = rank_vehicles(family, filter_vehicles(family, cars))
    record('family_unknown_fuel_is_disclosed', {'matches': 3, 'fuel_scored': False, 'explained': True},
           {'matches': family_result['matched_count'], 'fuel_scored': 'fuel' in family_result['scoring_weights'],
            'explained': any('no fuel-economy recommendation' in note for note in family_result['scoring_notes'])})
    result = estimate_vehicle_value(seller, cars, as_of=AS_OF)
    record('seller_reference', {'status': 'reference_only', 'median': 44800, 'count': 3},
           {'status': result['status'], 'median': result['reference']['median_asking_price_myr'], 'count': result['reference']['comparable_count']})
    insufficient = seller.model_copy(update={'model': 'Bezza', 'variant': '1.3 AV', 'year': 2023})
    record('insufficient_comparables', 'insufficient_evidence', estimate_vehicle_value(insufficient, cars, as_of=AS_OF)['status'])
    record('future_manufacturing_year', 'needs_clarification', estimate_vehicle_value(seller.model_copy(update={'year': 2027}), cars, as_of=AS_OF)['status'])
    record('major_damage', 'inspection_required', estimate_vehicle_value(seller.model_copy(update={'flood_damage_reported': True}), cars, as_of=AS_OF)['status'])
    scenario = estimate_vehicle_value(seller, cars, as_of=AS_OF, illustrative_adjustments=True)
    record('explicit_educational_scenario', {'value': 43092, 'market_validated': False},
           {'value': scenario['adjusted_scenario']['scenario_midpoint_myr'], 'market_validated': scenario['adjusted_scenario']['market_validated']})
    if live:
        buyer_text = 'Budget RM50000, at least five seats, mainly city commuting. Fuel economy and a spacious boot are high priorities.'
        buyer = extract_profile(buyer_text, 'qwen3:4b')
        ranked = rank_vehicles(buyer, filter_vehicles(buyer, cars))
        record('live_buyer_text_to_rank', {'status': 'matches_found', 'top': ranking['top_vehicle_ids']},
               {'status': ranked['status'], 'top': ranked['top_vehicle_ids']})
        seller_text = 'I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 50000 m, fair condition. No major accident and no flood damage.'
        extracted = extract_seller_profile(seller_text, 'qwen3:4b')
        value = estimate_vehicle_value(extracted, cars, as_of=AS_OF)
        record('live_seller_metres_to_reference', {'mileage_km': 50.0, 'status': 'reference_only', 'median': 44800},
               {'mileage_km': extracted.mileage_km, 'status': value['status'], 'median': value['reference']['median_asking_price_myr'] if value['reference'] else None})
    return {'reviewed_on': AS_OF.isoformat(), 'scope': 'Bounded development acceptance scenarios, not market or general language accuracy.',
            'live_model': 'qwen3:4b' if live else None, 'checks': checks, 'passed': all(c['passed'] for c in checks)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Also run two real Ollama extraction-to-tool scenarios')
    parser.add_argument('--output', type=Path, default=ROOT/'stage5-stage6-acceptance.json')
    args = parser.parse_args()
    result = run(args.live)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for check in result['checks']:
        print(('PASS' if check['passed'] else 'FAIL') + ' ' + check['case'])
    raise SystemExit(0 if result['passed'] else 1)
