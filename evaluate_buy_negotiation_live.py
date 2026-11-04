"""Replay the recorded Buy -> option 1 negotiation flow using local Ollama.

This checks conversation continuity and real tool execution, not market accuracy.
Every run uses a new report file; failed runs remain available for inspection.
"""
import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import time

from agent_controller import AgentController
from team_check import default_report_path, now_malaysia, repository_identity
from ui_session import UISession


BUY_OPEN = 'I want to buy a bigger car for my family.'
BUY_DETAILS = ('My vehicle-price budget is RM65000. I need at least 7 seats for family travel. '
               'Comfort priority is high.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--switch-area', action='store_true', help='Select Negotiation in the UI adapter before the final turn.')
    args = parser.parse_args()
    output = args.output or default_report_path('buy-negotiation-live')
    if output.exists():
        parser.error('Use a new report path; do not overwrite earlier evidence.')
    output.parent.mkdir(parents=True, exist_ok=True)
    ui = UISession(AgentController(as_of=date(2026, 10, 15)))
    report = {'run_on': now_malaysia().isoformat(), 'source': repository_identity(),
              'model': 'qwen3:4b', 'switch_area': args.switch_area,
              'scope': 'Actual local Ollama + UI session adapter + Python tools; not a real browser or market assessment.',
              'turns': [], 'passed': False}
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def turn(name, text, goal, expected):
        print('RUN ' + name, flush=True)
        started = time.monotonic()
        response = ui.submit(text, goal=goal)
        checks = expected(response)
        report['turns'].append({'case': name, 'input': text, 'area': goal,
                                'elapsed_seconds': round(time.monotonic() - started, 2),
                                'checks': checks, 'passed': all(checks.values()), 'response': response,
                                'ranked_ids': list(ui.controller.state.ranked_vehicle_ids),
                                'selected_vehicle_id': ui.controller.state.selected_vehicle_id})
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(('PASS ' if all(checks.values()) else 'FAIL ') + name + ': ' + response['status'], flush=True)
        return response

    turn('buy_open', BUY_OPEN, 'buy', lambda r: {'clarifies': r['status'] == 'needs_clarification'})
    ranking = turn('buy_details', BUY_DETAILS, 'buy', lambda r: {
        'complete': r['status'] == 'complete', 'has_candidates': bool((r.get('result') or {}).get('matches')),
        'checked': bool(r['checks']) and all(c['passed'] for c in r['checks'])})
    matches = (ranking.get('result') or {}).get('matches') or []
    if matches:
        first = matches[0]['vehicle']
        price = Decimal(str(first['price_myr']))
        quote, budget = price + 2000, price + 1000
        message = ('I want to negotiate as the buyer for option 1. '
                   f'The seller current vehicle offer is RM{quote:,.2f} excluding fees. '
                   'Total applicable fees are RM1500. All fees are complete. '
                   f'My maximum total purchase budget including fees is RM{budget:,.2f}.')

        def negotiation_checks(response):
            profile = ui.controller.state.negotiation
            result = response.get('result') or {}
            return {'complete': response['status'] == 'complete',
                    'correct_selected_id': ui.controller.state.selected_vehicle_id == first['vehicle_id'],
                    'correct_identity': all(getattr(profile.vehicle, k) == first[k] for k in ('brand', 'model', 'variant', 'year', 'transmission')),
                    'current_offer_from_user': profile.current_offer_myr == float(quote),
                    'fees': profile.fees_myr == 1500 and profile.fees_confirmed_complete is True,
                    'budget': profile.buyer_total_budget_myr == float(budget),
                    'counter_matches_recording': result.get('suggested_counter_price_myr') == float(price - 500),
                    'checked': bool(response['checks']) and all(c['passed'] for c in response['checks'])}

        report['first_option'] = first
        turn('negotiate_option_1', message, 'negotiate' if args.switch_area else 'buy', negotiation_checks)
    report['passed'] = len(report['turns']) == 3 and all(t['passed'] for t in report['turns'])
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('Report: ' + str(output), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    # The killable Ollama worker requires a guarded entry point on Windows.
    raise SystemExit(main())
