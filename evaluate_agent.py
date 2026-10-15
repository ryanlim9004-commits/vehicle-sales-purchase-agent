"""Actual local-model, multi-turn acceptance; never substitutes scripted replies."""
import argparse
import json
import time
from datetime import date
from pathlib import Path
from agent_controller import AgentController

ROOT = Path(__file__).resolve().parent

CASES = {
    'buy': [
        ('I want to buy a car. Save fuel.', {'status': 'needs_clarification'}),
        ('My vehicle budget is RM60000, a six-person family, mainly city commuting. Exclude Toyota.', {'status': 'complete', 'result.matched_count': 3}),
        ('Change my budget to RM35000.', {'status': 'complete', 'result.status': 'no_matches', 'facts.family_size': 6, 'facts.fuel_priority': 'high'}),
        ('/reset', {'status': 'reset', 'goal': None})],
    'sell': [
        ('I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, odometer 50000 m, fair condition. No major accident and no flood damage.',
         {'status': 'complete', 'facts.mileage_km': 50, 'result.reference.median_asking_price_myr': 44800})],
    'negotiate': [
        ('I want to negotiate as a buyer for a Perodua Alza 1.5 SE, manufactured in 2020, automatic. The seller currently quotes RM46000 excluding fees. My total purchase budget including fees is RM46000. All fees total RM1500 and are confirmed complete.',
         {'status': 'complete', 'result.suggested_counter_price_myr': 44500, 'result.valuation_evidence.reference.median_asking_price_myr': 44800})],
    'trade_in': [
        ('I want to compare trade-in with private sale. My current car is a Perodua Alza 1.5 SE, manufactured in 2020, automatic. The trade-in gross offer is RM35000 and trade-in disposal fees are RM500. The old loan settlement is RM10000.',
         {'status': 'needs_clarification', 'goal': 'trade_in', 'facts.loan_settlement_myr': 10000, 'facts.trade_in_quote.price_myr': 35000, 'facts.current_vehicle.model': 'Alza'}),
        ('The replacement price using trade-in is RM65000, with replacement fees RM1000. The replacement price after private sale is RM65000, with replacement fees RM1000. Private-sale gross proceeds are RM40000, and private-sale disposal fees are RM1000. All fees for both replacement quotes and both disposal quotes are confirmed complete. Available cash is RM50000. Lowest net cost is my priority.',
         {'status': 'complete', 'result.paths.trade_in.cash_difference_myr': 41500, 'result.paths.private_sale.cash_difference_myr': 37000,
          'result.comparison.private_sale_cash_advantage_myr': 4500, 'result.asking_price_context.reference.median_asking_price_myr': 44800})]
}


def projected(result, path):
    value = result
    for part in path.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=list(CASES), help='Run one scenario group instead of all groups')
    parser.add_argument('--output', type=Path, default=ROOT/'stage8-live-results.json')
    args = parser.parse_args()
    report = {'reviewed_on': '2026-10-15', 'model': 'qwen3:4b',
              'planning_protocol': 'Schema-constrained JSON tool requests; Python validates, executes and checks actual observations. Not Ollama native tool_calls.',
              'scope': 'Development acceptance, synthetic user quotes and frozen real-source snapshots; not holdout language accuracy or market/transaction accuracy.', 'turns': []}
    for case in [args.case] if args.case else CASES:
        agent = AgentController(as_of=date(2026, 10, 15))
        for index, (message, expected) in enumerate(CASES[case], 1):
            print(f'RUN {case} turn {index}', flush=True)
            start = time.monotonic()
            actual = agent.handle(message)
            values = {path: projected(actual, path) for path in expected}
            passed = values == expected
            report['turns'].append({'case': case, 'turn': index, 'input': message, 'expected': expected,
                                    'actual': values, 'passed': passed, 'elapsed_seconds': round(time.monotonic() - start, 2), 'response': actual})
            report['passed'] = all(t['passed'] for t in report['turns'])
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(('PASS' if passed else 'FAIL') + f' {case} turn {index}: {actual["status"]}', flush=True)
            if actual['status'] in ('timeout', 'model_error', 'protocol_error', 'tool_error_limit', 'step_limit'):
                break
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
