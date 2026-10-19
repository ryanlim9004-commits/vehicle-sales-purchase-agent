"""Actual Ollama development acceptance; never an independent relevance study."""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from agent_controller import AgentController


def main():
    root = Path(__file__).resolve().parent
    agent = AgentController(as_of=date(2026, 10, 15))
    report = {'run_on': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'model': 'qwen3:4b',
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
        report['passed'] = all(t['passed'] for t in report['turns'])
        (root/'v2-live-results.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(('PASS' if all(checks.values()) else 'FAIL') + f' v2 turn {i}: {actual["status"]}', flush=True)
        if actual['status'] != 'complete':
            break
    return 0 if report['passed'] and len(report['turns']) == 2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
