"""Actual local Ollama multi-turn acceptance; not real-deal/market validation."""
import argparse
from datetime import date
import json
from pathlib import Path
import time

from agent_controller import AgentController
from form_inputs import fields_for, prepare_form
from team_check import default_report_path, repository_identity, now_malaysia

ROOT = Path(__file__).resolve().parent


def trade_form(agent):
    data = json.loads((ROOT/'examples/trade_in.json').read_text())
    data['priority'] = 'speed'
    data['trade_in_quote']['estimated_completion_days'] = None
    data['private_sale_quote']['estimated_completion_days'] = None
    entries = {}
    for field in fields_for('trade_in'):
        value = data
        for part in field.path.split('.')[1:]:
            value = value.get(part) if isinstance(value, dict) else None
        if value is not None:
            entries[field.path] = ('Yes' if value else 'No') if isinstance(value, bool) else str(value)
    return prepare_form('trade_in', entries, agent.state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or default_report_path('financial-audit-live')
    if output.exists():
        parser.error('Choose a new output file to preserve earlier evidence.')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'run_on': now_malaysia().isoformat(), 'source': repository_identity(), 'model': 'qwen3:4b',
              'scope': 'Actual two-goal multi-turn development acceptance; quoted amounts/time estimates are teaching fixtures, not market transactions or independent users.',
              'turns': [], 'passed': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream)
    negotiation = AgentController(as_of=date(2026, 10, 15))
    trade = AgentController(as_of=date(2026, 10, 15))
    initial = ('I want to negotiate. I am the buyer. The vehicle is Perodua Alza 1.5 SE, manufactured in 2020, Automatic. '
               'The seller current vehicle offer is RM46000 excluding fees. Applicable fees are RM1500. All fees are complete. '
               'My total purchase budget including fees is RM46000.')
    form_text, form_patch = trade_form(trade)
    cases = [(negotiation, initial, None, 'negotiation_initial'),
             (negotiation, 'The applicable fee total is now RM2000.', None, 'changed_fees'),
             (negotiation, 'All fees are complete.', None, 'reconfirmed_fees'),
             (trade, form_text, form_patch, 'trade_missing_time'),
             (trade, 'Trade-in estimated completion time is 2 days. Private-sale estimated completion time is 21 days.', None, 'trade_time_reply'),
             (trade, 'The current old vehicle has flood damage.', None, 'trade_reported_flood')]
    for agent, text, patch, name in cases:
        print('RUN ' + name, flush=True)
        started = time.monotonic()
        response = agent.handle(text, form_patch=patch)
        result = response.get('result') or {}
        if name == 'negotiation_initial':
            checks = {'complete': response['status'] == 'complete', 'counter': result.get('suggested_counter_price_myr') == 44500}
        elif name == 'changed_fees':
            checks = {'asks': response['status'] == 'needs_clarification',
                      'updated_fees': agent.state.negotiation.fees_myr == 2000,
                      'old_confirmation_cleared': agent.state.negotiation.fees_confirmed_complete is None}
        elif name == 'reconfirmed_fees':
            checks = {'complete': response['status'] == 'complete', 'counter': result.get('suggested_counter_price_myr') == 44000,
                      'confirmation': agent.state.negotiation.fees_confirmed_complete is True}
        elif name == 'trade_missing_time':
            checks = {'asks': response['status'] == 'needs_clarification',
                      'named_days': set(agent.state.pending_slots) == {'trade_in.trade_in_quote.estimated_completion_days', 'trade_in.private_sale_quote.estimated_completion_days'}}
        elif name == 'trade_time_reply':
            checks = {'complete': response['status'] == 'complete', 'fastest': result.get('suggested_path') == 'trade_in',
                      'trade_days': agent.state.trade_in.trade_in_quote.estimated_completion_days == 2,
                      'private_days': agent.state.trade_in.private_sale_quote.estimated_completion_days == 21}
        else:
            checks = {'complete': response['status'] == 'complete', 'inspection': result.get('status') == 'inspection_required',
                      'recorded_flood': agent.state.trade_in.flood_damage_reported is True,
                      'no_comparison_advice': result.get('suggested_path') is None}
        if response['status'] == 'complete':
            checks['tool_checks'] = bool(response['checks']) and all(c['passed'] for c in response['checks'])
        report['turns'].append({'case': name, 'input': text, 'structured_form': patch is not None,
                                'elapsed_seconds': round(time.monotonic()-started, 2), 'checks': checks,
                                'passed': all(checks.values()), 'response': response})
        report['passed'] = len(report['turns']) == len(cases) and all(r['passed'] for r in report['turns'])
        output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        print(('PASS ' if all(checks.values()) else 'FAIL ') + name + ': ' + response['message'], flush=True)
    print(output, flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
