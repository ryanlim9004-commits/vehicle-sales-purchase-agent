"""Allowlisted tools built from validated session facts and actual observations."""
import json
import re
from decimal import Decimal
from statistics import median
from pydantic import Field
from agent_state import StrictFrame
from buyer_profile import reason_about_profile
from seller_profile import SellerVehicleFrame
from consultation_frames import NegotiationFrame
from matching import filter_vehicles
from scoring import rank_vehicles
from valuation import estimate_vehicle_value, key, money
from negotiation import advise_negotiation
from trade_in import compare_trade_in


class ToolError(ValueError):
    pass


class EmptyArgs(StrictFrame):
    pass


class SelectArgs(StrictFrame):
    vehicle_id: str = Field(min_length=1, max_length=100)


DESCRIPTIONS = {
    'inspect_requirements': 'Check active goal facts and missing requirements; always do this before a business tool.',
    'rank_vehicles': 'For buy: hard-filter saved vehicle snapshots, then compute explainable lifestyle ranking from current buyer facts.',
    'estimate_vehicle_value': 'For sell: use current seller facts and saved comparable asking-price listings; no invented market prices.',
    'get_price_reference': 'For negotiate or trade_in with complete current-vehicle identity: obtain actual unadjusted asking-price context before advice. This is never a trade-in cash offer.',
    'advise_negotiation': 'For negotiate: run the buyer/seller decision tree using known quotes/fees/limits and the obtained reference. If no vehicle identity exists, only limited budget/reserve advice is possible.',
    'compare_trade_in': 'For trade_in: compare explicit user quotes, complete fees, old-loan settlement, estimated time/effort and cash limits.',
    'select_vehicle': 'Select a vehicle ID only from the current verified buying candidates; use it as the identity for subsequent negotiation.',
    'check_result': 'Independently verify the last business observation against facts, dataset and arithmetic. Must pass before finish.',
    'ask_user': 'Return the canonical pending clarification questions and stop to wait for a user reply. Do not invent questions or facts.',
    'finish': 'Finish only after the active goal business tool ran and check_result passed. The controller renders verified numbers.'}


def tool_specs():
    return [{'type': 'function', 'function': {'name': name, 'description': description,
             'parameters': (SelectArgs if name == 'select_vehicle' else EmptyArgs).model_json_schema()}}
            for name, description in DESCRIPTIONS.items()]


def identity_complete(frame):
    return all(getattr(frame, name) is not None for name in ('brand', 'model', 'variant', 'year', 'transmission'))


def requirements(state, as_of):
    missing = dict(state.issues)
    if state.goal is None:
        missing['goal'] = 'Would you like to buy, sell, negotiate, or compare trade-in with private sale?'
    elif state.goal == 'buy':
        reason = reason_about_profile(state.buyer)
        for slot, question in zip(reason['missing_slots'], reason['clarification_questions'][-len(reason['missing_slots']):] if reason['missing_slots'] else []):
            missing['buyer.' + slot] = question
        for i, question in enumerate(reason['clarification_questions'][:len(reason['clarification_questions']) - len(reason['missing_slots'])]):
            slot = 'buyer.household_travels_together' if 'household size' in question else f'buyer.conflict_{i}'
            missing[slot] = question
    elif state.goal == 'sell':
        seller = state.seller
        if seller.major_accident_reported is not True and seller.flood_damage_reported is not True:
            for field, question in [('brand', 'What is the vehicle brand?'), ('model', 'What is the vehicle model?'),
                                    ('variant', 'What is the exact vehicle variant?'), ('year', 'What is the manufacturing year?'),
                                    ('transmission', 'Is the transmission Automatic, Manual or D-CVT?'),
                                    ('mileage_km', 'What is the odometer reading, with an explicit distance unit?'),
                                    ('condition', 'Is the self-reported condition good, fair or poor?')]:
                if getattr(seller, field) is None or (field == 'condition' and seller.condition == 'unknown'):
                    missing['seller.' + field] = question
            if seller.year and seller.year > as_of.year:
                missing['seller.year'] = 'The manufacturing year is after the consultation date. Please confirm it.'
    elif state.goal == 'negotiate':
        p = state.negotiation
        damaged = state.negotiation_from_seller and (state.seller.major_accident_reported is True or state.seller.flood_damage_reported is True)
        required = [('role', 'Are you the buyer or seller?'), ('current_offer_myr', 'What vehicle price has the other party currently offered, excluding fees? State MYR/RM.'),
                    ('fees_myr', 'What is the applicable total fee amount in MYR? State RM0 only if confirmed.'),
                    ('fees_confirmed_complete', 'Are all applicable fees included? Confirm that all fees are complete, or say they are partial/unknown.')]
        if p.role == 'buyer':
            required.append(('buyer_total_budget_myr', 'What is your maximum total cash purchase budget including fees, in MYR?'))
        if p.role == 'seller':
            required.extend([('seller_minimum_net_myr', 'What minimum net proceeds must remain after fees and old-loan settlement, in MYR?'),
                             ('loan_settlement_myr', 'What is the old-loan settlement amount in MYR? State RM0 only if confirmed debt-free.')])
        if not damaged:
            for field, question in required:
                if getattr(p, field) is None or (field == 'fees_confirmed_complete' and getattr(p, field) is not True):
                    missing['negotiation.' + field] = question
    elif state.goal == 'trade_in':
        p = state.trade_in
        if state.trade_in_from_seller and (state.seller.major_accident_reported is True or state.seller.flood_damage_reported is True):
            return missing
        if p.loan_settlement_myr is None:
            missing['trade_in.loan_settlement_myr'] = 'What is the current vehicle loan settlement amount in MYR? State RM0 only if confirmed debt-free.'
        for field in ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote'):
            quote = getattr(p, field)
            label = field.replace('_', ' ')
            for name, question in [('price_myr', f'What is the {label} vehicle price/gross offer, in MYR?'),
                                   ('fees_myr', f'What are the {label} fees in MYR? State RM0 only if confirmed.'),
                                   ('fees_confirmed_complete', f'Confirm whether all {label} fees are complete; partial or unknown fees cannot be assumed.')]:
                if getattr(quote, name) is None or (name == 'fees_confirmed_complete' and getattr(quote, name) is not True):
                    missing['trade_in.' + field + '.' + name] = question
    return missing


def verify_observation(tool, result, state, cars, as_of):
    checks = []

    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})

    try:
        json.dumps(result, allow_nan=False)
        check('finite_json_result', True)
        status = result['status']
        if status == 'needs_clarification':
            check('clarification_has_questions', bool(result.get('clarification_questions') or result.get('buyer_reasoning', {}).get('clarification_questions')))
            return checks
        if tool == 'rank_vehicles':
            facts = reason_about_profile(state.buyer)['derived_facts']
            expected = {r['vehicle']['vehicle_id'] for r in filter_vehicles(state.buyer, cars)['matches']}
            actual = [r['vehicle']['vehicle_id'] for r in result['matches']]
            check('all_eligible_ids_once', len(actual) == len(set(actual)) and set(actual) == expected)
            check('status_agrees_with_matches', status == ('matches_found' if expected else 'no_matches'))
            check('weights_sum_to_one', abs(sum(result['scoring_weights'].values()) - 1) < 1e-8)
            source_rows = {v.vehicle_id: v.model_dump(mode='json') for v in cars}
            for row in result['matches']:
                v = row['vehicle']
                check('dataset_identity_' + v['vehicle_id'], source_rows[v['vehicle_id']] == v)
                check('hard_constraints_' + v['vehicle_id'], v['price_myr'] <= facts['budget_myr'] and v['seats'] >= facts['minimum_vehicle_seats'] and v['brand'].strip().casefold() not in {b.strip().casefold() for b in state.buyer.excluded_brands})
                check('score_reconciles_' + v['vehicle_id'], abs(row['score'] - sum(c['weighted_points'] for c in row['score_breakdown'].values())) <= 0.00051)
            check('score_order', result['matches'] == sorted(result['matches'], key=lambda r: (-r['score'], -r['weighted_data_coverage_percent'], r['vehicle']['price_myr'], r['vehicle']['vehicle_id'])))
        elif tool == 'estimate_vehicle_value':
            if status == 'inspection_required':
                check('damage_report_exists', state.seller.major_accident_reported is True or state.seller.flood_damage_reported is True)
            elif status == 'insufficient_evidence':
                check('no_invented_price', result['reference'] is None and len(result['comparables']) < result['policy']['minimum_comparables'])
            else:
                comps = result['comparables']
                by_id = {v.vehicle_id: v for v in cars}
                check('default_is_unadjusted', status == 'reference_only' and result['adjusted_scenario'] is None)
                check('minimum_comparables', len(comps) >= result['policy']['minimum_comparables'])
                check('unique_comparables', len({c['vehicle_id'] for c in comps}) == len(comps) == len({c['source_reference'] for c in comps}))
                for c in comps:
                    v = by_id[c['vehicle_id']]
                    check('comparable_source_' + v.vehicle_id, c['asking_price_myr'] == v.price_myr and c['source_reference'] == v.source_reference and v.price_type == 'asking' and v.source_kind == 'listing' and v.availability == 'listed_snapshot' and v.year == state.seller.year and all(key(getattr(v, k)) == key(getattr(state.seller, k)) for k in ('brand', 'model', 'variant', 'transmission')) and v.source_updated_on is not None and 0 <= (as_of - v.source_updated_on).days <= result['policy']['maximum_source_age_days'])
                prices = [Decimal(str(c['asking_price_myr'])) for c in comps]
                check('median_and_range', result['reference']['median_asking_price_myr'] == money(median(prices)) and result['reference']['observed_asking_range_myr'] == [money(min(prices)), money(max(prices))])
        elif tool == 'advise_negotiation':
            p = state.negotiation
            if status == 'inspection_required':
                check('inspection_reference', result['valuation_evidence']['status'] == 'inspection_required')
            else:
                check('fees_explicit', p.fees_myr is not None and p.fees_confirmed_complete is True)
                counter = result['suggested_counter_price_myr']
                check('no_unexplained_counter', (result['action'] == 'counter_offer') == (counter is not None))
                if p.role == 'buyer':
                    check('buyer_total_arithmetic', result['calculations']['offered_total_cost_myr'] == money(Decimal(str(p.current_offer_myr)) + Decimal(str(p.fees_myr))))
                    if counter is not None:
                        check('counter_within_total_budget', Decimal(str(counter)) + Decimal(str(p.fees_myr)) <= Decimal(str(p.buyer_total_budget_myr)))
                else:
                    expected = Decimal(str(p.current_offer_myr)) - Decimal(str(p.fees_myr)) - Decimal(str(p.loan_settlement_myr))
                    check('seller_net_arithmetic', result['calculations']['offered_net_proceeds_myr'] == money(expected))
                    if counter is not None:
                        check('counter_meets_net_floor', Decimal(str(counter)) - Decimal(str(p.fees_myr)) - Decimal(str(p.loan_settlement_myr)) >= Decimal(str(p.seller_minimum_net_myr)))
                if result['valuation_evidence']['reference'] is None:
                    check('no_fabricated_market_assessment', status == 'limited_advice' and result['price_position'] == 'not_assessed')
        elif tool == 'compare_trade_in':
            p = state.trade_in
            if status == 'inspection_required':
                check('inspection_reference', result['asking_price_context']['status'] == 'inspection_required')
                return checks
            for name, row in result['paths'].items():
                disposal, replacement = getattr(p, name + '_quote'), getattr(p, name + '_replacement')
                if row['status'] != 'calculated':
                    check('unknown_amount_not_zero_' + name, row['cash_difference_myr'] is None)
                    continue
                net = Decimal(str(disposal.price_myr)) - Decimal(str(disposal.fees_myr)) - Decimal(str(p.loan_settlement_myr))
                difference = Decimal(str(replacement.price_myr)) + Decimal(str(replacement.fees_myr)) - net
                check('cash_arithmetic_' + name, row['net_proceeds_myr'] == money(net) and row['cash_difference_myr'] == money(difference) and row['cash_required_myr'] == money(max(Decimal(0), difference)) and row['cash_surplus_myr'] == money(max(Decimal(0), -difference)))
            if result['suggested_path'] and p.available_cash_myr is not None:
                check('suggested_path_affordable', result['paths'][result['suggested_path']]['cash_required_myr'] <= p.available_cash_myr)
            if result['comparison']:
                check('path_difference_reconciles', result['comparison']['private_sale_cash_advantage_myr'] == money(Decimal(str(result['paths']['trade_in']['cash_difference_myr'])) - Decimal(str(result['paths']['private_sale']['cash_difference_myr']))))
        else:
            check('registered_business_tool', False)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
        check('result_shape_and_arithmetic', False)
    return checks


class ToolRuntime:
    def __init__(self, state, cars, as_of):
        self.state, self.cars, self.as_of = state, cars, as_of
        self.reference = None
        self.last_tool = None
        self.last_result = None
        self.checked = False
        self.inspected = False
        self.pending = {}
        self.done = None
        self.selection_done = False

    def available_tools(self, message):
        """Expose only state-valid actions, rather than unrelated task tools."""
        if not self.inspected:
            return ['inspect_requirements']
        if self.pending or requirements(self.state, self.as_of):
            return ['ask_user']
        requested_selection = re.search(r'\b(first|second|third|select|choose|that one|this one)\b', message, re.I)
        if requested_selection and self.state.ranked_vehicle_ids and not self.selection_done and self.state.goal in ('buy', 'negotiate'):
            return ['select_vehicle']
        if self.last_result is not None:
            if not self.checked:
                return ['check_result']
            return ['finish']
        # The model chooses among registered business tools; the call guard
        # independently rejects a tool incompatible with the active goal.
        choices = ['rank_vehicles', 'estimate_vehicle_value', 'advise_negotiation', 'compare_trade_in']
        identity = self.state.negotiation.vehicle if self.state.goal == 'negotiate' else self.state.trade_in.current_vehicle
        if self.state.goal in ('negotiate', 'trade_in') and identity_complete(identity) and self.reference is None:
            choices.append('get_price_reference')
        return choices

    def call(self, name, arguments):
        if name not in DESCRIPTIONS:
            raise ToolError('Unknown tool. Only the provided read-only consultation tools are permitted.')
        args = (SelectArgs if name == 'select_vehicle' else EmptyArgs).model_validate(arguments)
        if name == 'inspect_requirements':
            self.inspected = True
            self.pending = requirements(self.state, self.as_of)
            self.state.pending_slots = list(self.pending)
            return {'status': 'needs_clarification' if self.pending else 'ready', 'missing_slots': list(self.pending), 'questions': list(self.pending.values())[:3]}
        if name == 'ask_user':
            self.pending = self.pending or requirements(self.state, self.as_of)
            if not self.pending:
                raise ToolError('No missing requirements are pending. Execute the active goal tool rather than asking invented questions.')
            self.state.pending_slots = list(self.pending)
            self.done = 'needs_clarification'
            return {'questions': list(dict.fromkeys(self.pending.values()))[:3]}
        if name == 'select_vehicle':
            if self.state.goal not in ('buy', 'negotiate') or args.vehicle_id not in self.state.ranked_vehicle_ids:
                raise ToolError('Select only a vehicle from the current verified buying candidates.')
            eligible = {r['vehicle']['vehicle_id'] for r in filter_vehicles(self.state.buyer, self.cars)['matches']}
            if args.vehicle_id not in eligible:
                raise ToolError('The vehicle no longer satisfies the current buyer facts. Rank again.')
            car = next(v for v in self.cars if v.vehicle_id == args.vehicle_id)
            self.state.selected_vehicle_id = car.vehicle_id
            self.selection_done = True
            self.reference = None
            self.state.negotiation_from_seller = False
            data = self.state.negotiation.model_dump()
            data['vehicle'] = {k: getattr(car, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}
            self.state.negotiation = NegotiationFrame.model_validate(data)
            self.checked = False
            return {'selected_vehicle_id': car.vehicle_id, 'vehicle_identity': data['vehicle'], 'asking_price_myr': car.price_myr, 'notice': 'Saved asking price is not automatically a current seller offer.'}
        if name == 'check_result':
            if self.last_result is None:
                raise ToolError('No business observation exists to check.')
            checks = verify_observation(self.last_tool, self.last_result, self.state, self.cars, self.as_of)
            self.checked = bool(checks) and all(c['passed'] for c in checks)
            for item in checks:
                self.state.event('checks', tool=self.last_tool, **item)
            return {'passed': self.checked, 'checks': checks}
        if name == 'finish':
            expected = {'buy': 'rank_vehicles', 'sell': 'estimate_vehicle_value', 'negotiate': 'advise_negotiation', 'trade_in': 'compare_trade_in'}.get(self.state.goal)
            if not self.checked or self.last_tool != expected or self.last_result is None:
                raise ToolError('Finish requires the active goal business observation and a passing check_result.')
            if self.last_result['status'] == 'needs_clarification':
                raise ToolError('The business tool needs clarification. Ask the canonical questions and wait.')
            self.done = 'complete'
            return {'status': 'complete', 'outcome': self.last_result['status']}
        if not self.inspected:
            raise ToolError('Call inspect_requirements before running a business tool.')
        if requirements(self.state, self.as_of):
            raise ToolError('Required facts are missing or conflicting. Use ask_user and wait for the reply.')
        expected = {'buy': 'rank_vehicles', 'sell': 'estimate_vehicle_value', 'negotiate': 'advise_negotiation', 'trade_in': 'compare_trade_in'}.get(self.state.goal)
        if name == 'get_price_reference':
            current = self.state.negotiation.vehicle if self.state.goal == 'negotiate' else self.state.trade_in.current_vehicle
            if self.state.goal not in ('negotiate', 'trade_in') or not identity_complete(current):
                raise ToolError('A price reference requires complete negotiation vehicle identity. Without it, only limited limit-based advice is possible.')
            identity = current.model_dump()
            from_seller = self.state.negotiation_from_seller if self.state.goal == 'negotiate' else self.state.trade_in_from_seller
            linked = from_seller and all(key(str(identity[k])) == key(str(getattr(self.state.seller, k))) for k in identity)
            if linked:
                identity.update(major_accident_reported=self.state.seller.major_accident_reported, flood_damage_reported=self.state.seller.flood_damage_reported)
            vehicle = SellerVehicleFrame.model_validate(identity)
            self.reference = estimate_vehicle_value(vehicle, self.cars, as_of=self.as_of, identity_reference_only=True)
            return self.reference
        if name != expected:
            raise ToolError('The selected business tool does not match the active consultation goal.')
        if name == 'rank_vehicles':
            result = rank_vehicles(self.state.buyer, filter_vehicles(self.state.buyer, self.cars))
        elif name == 'estimate_vehicle_value':
            result = estimate_vehicle_value(self.state.seller, self.cars, as_of=self.as_of)
        elif name == 'advise_negotiation':
            if identity_complete(self.state.negotiation.vehicle) and self.reference is None:
                raise ToolError('Obtain get_price_reference for the known vehicle identity before advising. Do not invent or silently omit available reference evidence.')
            result = advise_negotiation(self.state.negotiation, as_of=self.as_of, valuation_result=self.reference)
        else:
            if identity_complete(self.state.trade_in.current_vehicle) and self.reference is None:
                raise ToolError('Obtain get_price_reference for the stated current vehicle before comparing quotes. It is context, not an inferred trade-in offer.')
            result = compare_trade_in(self.state.trade_in, valuation_result=self.reference, as_of=self.as_of)
        self.last_tool, self.last_result, self.checked = name, result, False
        if name == 'rank_vehicles':
            self.state.ranked_vehicle_ids = [r['vehicle']['vehicle_id'] for r in result['matches']]
        if result['status'] == 'needs_clarification':
            questions = result.get('clarification_questions', result.get('buyer_reasoning', {}).get('clarification_questions', []))
            self.pending = {f'tool_question_{i}': q for i, q in enumerate(questions)}
        return result
