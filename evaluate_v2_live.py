"""Actual Ollama development acceptance; never an independent relevance study."""
import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from agent_controller import AgentController
from team_check import default_report_path, repository_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New local report; defaults to a timestamped file under team_results/')
    parser.add_argument('--tester', default=None, help='Optional actual tester label; does not establish independent evaluation')
    args = parser.parse_args()
    output = args.output or default_report_path('live-v2')
    if output.exists():
        parser.error('Output already exists. Choose a new path; historical evidence is never overwritten.')
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        # Reserve this run's file before any inference. Only this run updates it.
        with output.open('x', encoding='utf-8') as stream:
            json.dump({'passed': False, 'status': 'started', 'turns': []}, stream)
    except OSError as error:
        parser.error('Cannot create the new report: ' + str(error))
    agent = AgentController(as_of=date(2026, 10, 15))
    report = {'run_on': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'model': 'qwen3:4b',
              'tester': args.tester, 'source': repository_identity(), 'expected_turns': 2,
              'scope': 'Two real Ollama CLI turns using actual tools/checks. Development acceptance; not market accuracy, independent relevance or browser-export proof.', 'turns': []}
    messages = [
        'I want to buy a car. My vehicle-price budget is RM60000. I need 5 seats for city commuting. Safety priority is high. Comfort priority is medium. Reliability priority is high. Fuel priority is high.',
        'Change my vehicle-price budget to RM55000. Luggage-space priority is high. Exclude Toyota.'
    ]
    for i, message in enumerate(messages, 1):
        print(f'RUN v2 turn {i}', flush=True)
        start = time.monotonic()
        actual = agent.handle(message)
        checks = {'complete': actual['status'] == 'complete',
                  'safety_priority': agent.state.buyer.safety_priority == 'high',
                  'comfort_priority': agent.state.buyer.comfort_priority == 'medium',
                  'reliability_priority': agent.state.buyer.reliability_priority == 'high',
                  'tool_checks': bool(actual.get('checks')) and all(c['passed'] for c in actual['checks'])}
        result = actual.get('result') or {}
        checks['policy'] = result.get('ranking_policy') == 'sugeno-lifestyle-v2.0'
        if i == 2:
            traces = [r['fuzzy_trace'] for r in result.get('matches', [])]
            supported = [t for t in traces if t['normalized_value'] is not None]
            unknown = [t for t in traces if t['normalized_value'] is None]
            checks.update(budget_correction=agent.state.buyer.budget_myr == 55000,
                          space_priority=agent.state.buyer.space_priority == 'high',
                          exclusion='toyota' in [b.casefold() for b in agent.state.buyer.excluded_brands],
                          nine_fuzzy_rules_for_supported_inputs=bool(supported) and all(len(t['rules']) == 9 for t in supported),
                          no_rules_invented_for_unknown_inputs=all(not t['rules'] and t['unknown_reason'] for t in unknown))
        report['turns'].append({'turn': i, 'input': message, 'checks': checks, 'passed': all(checks.values()),
                                'elapsed_seconds': round(time.monotonic()-start, 2), 'response': actual})
        report['completed_turns'] = len(report['turns'])
        report['passed'] = len(report['turns']) == 2 and all(t['passed'] for t in report['turns'])
        output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(('PASS' if all(checks.values()) else 'FAIL') + f' v2 turn {i}: {actual["status"]}', flush=True)
        if actual['status'] != 'complete':
            break
    print('Live report: ' + str(output), flush=True)
    return 0 if report['passed'] and len(report['turns']) == 2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
