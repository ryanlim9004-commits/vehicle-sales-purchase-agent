"""Actual local Ollama acceptance for the historical fallback, not market validation."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time

from agent_controller import AgentController
from form_inputs import prepare_form, fields_for
from team_check import default_report_path, repository_identity

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or default_report_path('historical-regression-live')
    if output.exists():
        parser.error('Choose a new output file; earlier evidence is never overwritten.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'run_on': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'source': repository_identity(), 'model': 'qwen3:4b',
              'scope': 'Two natural-language turns and one structured-form turn with the actual Ollama planner and actual tools. No independent relevance/market-accuracy/browser acceptance claim.',
              'turns': [], 'passed': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream)
    messages = [
        ('sell', 'I want to sell my Toyota Alphard 2.5 G S C Package. Manufacturing year is 2018. Transmission is Automatic. Odometer is 65000 km. Condition is good. No major accident and no flood damage.', 'historical_reference'),
        ('negotiate', 'I want to negotiate as the buyer of a Toyota Alphard 2.5 G S C Package. Manufacturing year is 2018. Transmission is Automatic. Odometer is 65000 km. The seller current offer is RM230000 excluding fees. Total applicable fees are RM1000 and all fees are complete. My maximum total purchase budget including fees is RM300000.', 'historical_advice'),
        ('trade_in', None, 'comparison_ready')]
    for goal, message, expected in messages:
        agent = AgentController(as_of=date(2026, 10, 15))
        patch = None
        if goal == 'trade_in':
            values = json.loads((ROOT / 'examples/trade_in_historical_alphard.json').read_text())
            entries = {}
            for field in fields_for(goal):
                current = values
                for part in field.path.split('.')[1:]:
                    current = current.get(part) if isinstance(current, dict) else None
                if current is not None:
                    entries[field.path] = ('Yes' if current else 'No') if isinstance(current, bool) else str(current)
            message, patch = prepare_form(goal, entries)
        print('RUN ' + goal, flush=True)
        start = time.monotonic()
        response = agent.handle(message, form_patch=patch)
        result = response.get('result') or {}
        model = result.get('historical_regression') if goal == 'sell' else result.get('valuation_evidence', {}).get('historical_regression') if goal == 'negotiate' else result.get('asking_price_context', {}).get('historical_regression')
        checks = {'complete': response['status'] == 'complete', 'expected_result': result.get('status') == expected,
                  'historical_scope': bool(model) and model.get('market_validated') is False,
                  'actual_tool_checks': bool(response.get('checks')) and all(c['passed'] for c in response['checks']),
                  'confirmed_odometer': getattr(agent.state, {'sell': 'seller', 'negotiate': 'negotiation', 'trade_in': 'trade_in'}[goal]).mileage_km == 65000}
        if goal == 'negotiate' and result.get('suggested_counter_price_myr') is not None:
            checks['counter_within_budget'] = result['suggested_counter_price_myr'] + 1000 <= 300000
        if goal == 'trade_in':
            checks['user_quotes_preserved'] = result.get('paths', {}).get('trade_in', {}).get('gross_offer_myr') == 160000 and result.get('paths', {}).get('private_sale', {}).get('gross_offer_myr') == 180000
        report['turns'].append({'goal': goal, 'input': message, 'structured_form': patch is not None,
                                'elapsed_seconds': round(time.monotonic() - start, 2), 'checks': checks,
                                'passed': all(checks.values()), 'response': response})
        report['passed'] = len(report['turns']) == 3 and all(r['passed'] for r in report['turns'])
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(('PASS ' if all(checks.values()) else 'FAIL ') + goal + ': ' + response['status'], flush=True)
    print('Live report: ' + str(output), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
