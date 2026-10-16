"""Saved Stage 7 acceptance examples. No model calls or live market queries."""
# Learning guide:
# Recheck five actual CLI runs and three direct financial-tool scenarios.
# All consultation quotes and time estimates here are synthetic fixtures.
# Running the script replaces stage7-results.json; no model or market calls occur.
import json
import subprocess
import sys
from pathlib import Path
from consultation_frames import TradeInFrame
from trade_in import compare_trade_in

ROOT = Path(__file__).resolve().parent


# Invoke the real single-turn CLI with this interpreter and parse JSON only when its process
# exits successfully.
def cli(name, *flags):
    args = [sys.executable, str(ROOT/'main.py'), '--fixture', str(ROOT/'examples'/name), *flags]
    process = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if process.returncode:
        raise RuntimeError(f'CLI acceptance failed: {name}: {process.stderr}')
    return json.loads(process.stdout)


# Collect eight deterministic acceptance cases, including linked references, unknown fees and
# package/cash-limit changes.
def run():
    records = []

    # Compare selected nested output fields with explicit expectations and retain the full
    # result as evidence.
    def record(name, result, expected):
        actual = {}
        for path in expected:
            value = result
            for name_part in path.split('.'):
                value = value[name_part]
            actual[path] = value
        records.append({'case': name, 'expected': expected, 'actual': actual, 'passed': expected == actual, 'result': result})

    reference = ['--valuation-seller', str(ROOT/'examples/seller_alza.json'), '--as-of', '2026-10-15']
    record('buyer_with_actual_valuation_tool', cli('negotiation_buyer.json', '--negotiate', *reference),
           {'status': 'advice_ready', 'suggested_counter_price_myr': 44500, 'calculations.offered_total_cost_myr': 47500})
    record('seller_with_actual_valuation_tool', cli('negotiation_seller.json', '--negotiate', *reference),
           {'status': 'advice_ready', 'suggested_counter_price_myr': 44800, 'calculations.minimum_vehicle_price_myr': 44000})
    record('trade_in_vs_private_sale', cli('trade_in.json', '--trade-in'),
           {'status': 'comparison_ready', 'paths.trade_in.cash_difference_myr': 41500, 'paths.private_sale.cash_difference_myr': 37000,
            'comparison.private_sale_cash_advantage_myr': 4500, 'suggested_path': 'private_sale'})
    record('unknown_fees_no_fabricated_total', cli('trade_in_unknown_fees.json', '--trade-in'),
           {'status': 'needs_clarification', 'paths.private_sale.cash_difference_myr': None, 'comparison': None, 'suggested_path': None})
    record('buyer_without_price_evidence', cli('negotiation_buyer.json', '--negotiate', '--as-of', '2026-10-15'),
           {'status': 'limited_advice', 'price_position': 'not_assessed', 'suggested_counter_price_myr': 44500})
    data = json.loads((ROOT/'examples/trade_in.json').read_text(encoding='utf-8'))
    cheaper = json.loads(json.dumps(data))
    cheaper['trade_in_replacement']['price_myr'] = 60000
    record('different_replacement_quote_reverses_financial_result', compare_trade_in(TradeInFrame.model_validate(cheaper)),
           {'suggested_path': 'trade_in', 'comparison.private_sale_cash_advantage_myr': -500})
    record('explicit_speed_priority', compare_trade_in(TradeInFrame.model_validate(data | {'priority': 'speed'})),
           {'suggested_path': 'trade_in', 'time_comparison.faster_path': 'trade_in'})
    record('available_cash_overrides_speed_priority', compare_trade_in(TradeInFrame.model_validate(data | {'priority': 'speed', 'available_cash_myr': 40000})),
           {'suggested_path': 'private_sale', 'paths.trade_in.within_available_cash': False})
    return {'reviewed_on': '2026-10-15', 'method': 'Five real CLI runs and three direct tool acceptance scenarios; all consultation quotes and time estimates are synthetic fixtures.',
            'reference_basis': 'CLI negotiation cases call the actual valuation tool on the saved real-source listing snapshot.',
            'limitations': 'No Ollama extraction, autonomous agent, executed negotiation, or market-success evaluation is claimed.',
            'cases': records, 'passed': all(r['passed'] for r in records)}


if __name__ == '__main__':
    result = run()
    (ROOT/'stage7-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for item in result['cases']:
        print(('PASS' if item['passed'] else 'FAIL') + ' ' + item['case'])
    raise SystemExit(0 if result['passed'] else 1)
