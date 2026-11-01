"""Replay the reported N10 text and inclusive-quote boundary with local Ollama."""
import argparse
from datetime import date
import json
from pathlib import Path
import time

from agent_controller import AgentController
from team_check import default_report_path, now_malaysia, repository_identity

N10_INPUT = ('I want to negotiate as the buyer of a Toyota Alphard 2.5 G S C Package. '
             'Manufacturing year is 2018. Transmission is Automatic. Odometer is 65000 km. '
             'The seller current vehicle offer is RM230000 excluding fees. '
             'Total applicable fees are RM1000. All fees are complete. '
             'My maximum total purchase budget including fees is RM300000.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or default_report_path('n10-live')
    if output.exists():
        parser.error('Use a new report path; earlier evidence must be preserved.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'run_on': now_malaysia().isoformat(), 'source': repository_identity(),
              'model': 'qwen3:4b', 'scope': 'Actual local extraction/planning/tools; not browser or market validation.',
              'turns': [], 'passed': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream)
    fresh, inclusive = AgentController(as_of=date(2026, 10, 15)), AgentController(as_of=date(2026, 10, 15))
    cases = [(fresh, 'n10_exact_screenshot', N10_INPUT, 230000.),
             (inclusive, 'inclusive_quote_still_blocked', N10_INPUT.replace('RM230000 excluding fees', 'RM230000 including all fees'), None),
             (inclusive, 'bare_quote_correction', 'The seller current vehicle offer is RM229000 excluding fees. Total applicable fees are RM1000. All fees are complete.', 229000.)]
    for agent, name, message, offer in cases:
        print('RUN ' + name, flush=True)
        start = time.monotonic()
        response = agent.handle(message)
        profile, result = agent.state.negotiation, response.get('result') or {}
        checks = {'source_offer': profile.current_offer_myr == offer,
                  'not_misfiled_as_asking': profile.asking_price_myr is None,
                  'fees_preserved': profile.fees_myr == 1000,
                  'budget_preserved': profile.buyer_total_budget_myr == 300000}
        if offer is None:
            checks['asks_for_bare_quote'] = response['status'] == 'needs_clarification' and 'negotiation.current_offer_myr' in agent.state.pending_slots
        else:
            checks.update(complete=response['status'] == 'complete', historical=result.get('status') == 'historical_advice',
                          counter=result.get('suggested_counter_price_myr') == 187371.70,
                          tool_checks=bool(response['checks']) and all(c['passed'] for c in response['checks']))
        report['turns'].append({'case': name, 'input': message, 'elapsed_seconds': round(time.monotonic() - start, 2),
                                'checks': checks, 'passed': all(checks.values()), 'response': response})
        report['passed'] = len(report['turns']) == len(cases) and all(t['passed'] for t in report['turns'])
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(('PASS ' if all(checks.values()) else 'FAIL ') + name + ': ' + response['status'], flush=True)
    print('Report: ' + str(output), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    # Required for the existing killable Ollama process on Windows.
    raise SystemExit(main())
