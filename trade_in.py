"""Compare explicit cash purchase quotes with signed net proceeds and outlay."""
# Learning guide:
# Compare trade-in and private-sale paths using their own replacement packages.
# Signed cash difference = replacement price + fees - net disposal proceeds.
# Convenience uses user-estimated days/hours; a path name is not evidence of speed.
from consultation_frames import TradeInFrame, NegotiationFrame
from negotiation import decimal, asking_evidence
from valuation import money


# Compare known values only; return None for missing evidence and tie for equal alternatives.
def winner(values, smaller=True):
    if any(value is None for value in values.values()):
        return None
    if len(set(values.values())) == 1:
        return 'tie'
    return (min if smaller else max)(values, key=values.get)


# Compute each complete cash path, compare full outlays and make a conditional choice within the
# stated cash limit.
def compare_trade_in(profile: TradeInFrame, *, valuation_result=None, as_of=None):
    result = {'status': 'needs_clarification', 'profile': profile.model_dump(), 'paths': {},
              'comparison': None, 'suggested_path': None, 'fired_rules': [],
              'clarification_questions': list(profile.clarification_notes),
              'policy': {'version': 'trade-in-v1', 'method': 'Deterministic calculator plus hand-authored preference rules.',
                         'net_proceeds_formula': 'Gross offer - disposal fees - current loan settlement',
                         'cash_difference_formula': 'Replacement price + replacement fees - net proceeds',
                         'sign_convention': 'Positive cash difference requires additional cash; negative means a cash surplus.',
                         'fee_scope': 'Each quoted fee must include the full applicable fee total and be explicitly confirmed complete. Do not double count a fee or loan settlement.'},
              'limitations': ['All prices are user-provided quotes/scenarios; private-sale proceeds are not guaranteed.',
                             'Completion days and effort hours are user-provided estimates, not measured dealer service guarantees.',
                             'No time-to-money conversion, purchase-loan interest or future running costs are assumed.']}
    trace, questions = result['fired_rules'], result['clarification_questions']
    if valuation_result is not None and as_of is None:
        raise ValueError('A consultation date is required when linking a valuation observation.')
    evidence, evidence_questions = asking_evidence(NegotiationFrame(vehicle=profile.current_vehicle), valuation_result, as_of)
    result['asking_price_context'] = evidence
    result['limitations'].append('A linked asking-price reference is context only, never an inferred dealer trade-in cash offer or guaranteed private-sale proceeds.')
    questions.extend(evidence_questions)
    if evidence_questions:
        trace.append({'rule_id': 'TRADE_REFERENCE_LINK', 'reason': 'Vehicle identity/date or evidence arithmetic must be clarified before linking the reference.'})
        return result
    if evidence['status'] == 'inspection_required':
        result['status'] = 'inspection_required'
        trace.append({'rule_id': 'TRADE_INSPECTION', 'reason': 'The linked vehicle history requires inspection before ordinary replacement/disposal advice.'})
        return result
    if profile.loan_settlement_myr is None:
        questions.append('What is the current vehicle loan settlement amount? Enter zero only if confirmed debt-free.')
    for name in ('trade_in', 'private_sale'):
        # Each path owns a replacement quote AND a disposal quote. Dealer
        # package discounts may differ, so never copy one path's purchase price.
        replacement = getattr(profile, name + '_replacement')
        disposal = getattr(profile, name + '_quote')
        missing = []
        for prefix, quote in [(name + '_replacement', replacement), (name + '_quote', disposal)]:
            for field in ('price_myr', 'fees_myr', 'fees_confirmed_complete'):
                if getattr(quote, field) is None or (field == 'fees_confirmed_complete' and getattr(quote, field) is not True):
                    missing.append(prefix + '.' + field)
        if profile.loan_settlement_myr is None:
            missing.append('loan_settlement_myr')
        row = {'status': 'needs_clarification' if missing else 'calculated', 'missing_fields': missing,
               'replacement_price_myr': replacement.price_myr, 'replacement_fees_myr': replacement.fees_myr,
               'gross_offer_myr': disposal.price_myr, 'disposal_fees_myr': disposal.fees_myr,
               'loan_settlement_myr': profile.loan_settlement_myr,
               'net_proceeds_myr': None, 'cash_difference_myr': None, 'cash_required_myr': None,
               'cash_surplus_myr': None, 'within_available_cash': None,
               'estimated_completion_days': disposal.estimated_completion_days,
               'estimated_effort_hours': disposal.estimated_effort_hours}
        if missing:
            questions.append(f'Confirm the missing or incomplete values for {name}: ' + ', '.join(missing) + '. Zero fees must be stated explicitly.')
        else:
            # First settle the old loan once from gross disposal proceeds.
            # Then subtract those net proceeds from the replacement package.
            # Keep negative values: a shortfall or surplus is meaningful.
            net = decimal(disposal.price_myr) - decimal(disposal.fees_myr) - decimal(profile.loan_settlement_myr)
            outlay = decimal(replacement.price_myr) + decimal(replacement.fees_myr) - net
            row.update(net_proceeds_myr=money(net), cash_difference_myr=money(outlay),
                       cash_required_myr=money(max(decimal(0), outlay)), cash_surplus_myr=money(max(decimal(0), -outlay)),
                       within_available_cash=(outlay <= decimal(profile.available_cash_myr)) if profile.available_cash_myr is not None else None)
            trace.append({'rule_id': 'TRADE_CALCULATE', 'path': name, 'reason': 'All cash components and fee totals are explicit; the current loan is settled once.'})
        result['paths'][name] = row
    # Time/effort are compared only where both estimates exist; never inferred
    # from path names or converted to MYR without an explicit user valuation.
    rows = result['paths']
    result['time_comparison'] = {'faster_path': winner({n: r['estimated_completion_days'] for n, r in rows.items()}),
                                 'lower_effort_path': winner({n: r['estimated_effort_hours'] for n, r in rows.items()}),
                                 'basis': 'User-provided estimates; unknown estimates remain unassessed.'}
    if questions or any(r['status'] != 'calculated' for r in rows.values()):
        trace.append({'rule_id': 'TRADE_REQUIRED', 'reason': 'A complete financial comparison is withheld until missing or partial amounts are resolved.'})
        return result
    amounts = {name: decimal(row['cash_difference_myr']) for name, row in rows.items()}
    cheaper = winner(amounts)
    result.update(status='comparison_ready', comparison={
        'lower_cash_difference_path': cheaper,
        'private_sale_cash_advantage_myr': money(amounts['trade_in'] - amounts['private_sale']),
        'advantage_sign': 'Positive favours private sale; negative favours trade-in. Path-specific replacement prices and fees are included.'})
    trace.append({'rule_id': 'TRADE_COMPARE', 'reason': 'Compare full cash differences rather than gross offers alone.'})
    eligible = [name for name, row in rows.items() if row['within_available_cash'] is not False]
    # Financial feasibility precedes the preferred speed/effort/cost criterion.
    # An unknown cash limit permits only a conditional affordability statement.
    if not eligible:
        result['message'] = 'Neither path fits the stated available cash. Review replacement prices or the cash limit.'
        trace.append({'rule_id': 'TRADE_CASH_LIMIT', 'reason': 'No path may be suggested above the stated cash limit.'})
        return result
    if profile.priority is None:
        result['message'] = 'No overall priority was stated. Compare money, time and effort; no overall winner is selected.'
        return result
    metric = 'cash_difference_myr' if profile.priority == 'net_cost' else 'estimated_completion_days' if profile.priority == 'speed' else 'estimated_effort_hours'
    if any(rows[name][metric] is None for name in eligible):
        result['message'] = f'Cannot assess the requested {profile.priority} priority without estimates for every financially eligible path.'
        return result
    selected = min(eligible, key=lambda name: rows[name][metric])
    if len(eligible) == 2 and rows[eligible[0]][metric] == rows[eligible[1]][metric]:
        result['message'] = 'The eligible paths tie on the requested priority; no overall winner is selected.'
        return result
    result['suggested_path'] = selected
    result['message'] = 'A conditional suggestion based on the stated priority and known quotes; verify terms before deciding.'
    if profile.available_cash_myr is None:
        result['limitations'].append('Available cash is unknown; the conditional suggestion does not establish affordability.')
    trace.append({'rule_id': 'TRADE_PRIORITY', 'reason': f'Choose the lower {metric} among paths not known to exceed the cash limit; priority is user-stated.'})
    return result
