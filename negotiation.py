"""Hand-authored decision tree; price anchors are not learned or optimal offers."""
# Learning guide:
# Run a handwritten buyer/seller decision tree on explicit quotes and limits.
# A linked valuation must be an actual tool observation with matching identity/date.
# Suggestions respect cash limits; the program never accepts or executes a deal.
from datetime import date
from decimal import Decimal
from statistics import median
from consultation_frames import NegotiationFrame
from valuation import key, money


# Construct Decimal from text to avoid importing the binary representation of a float into money
# arithmetic.
def decimal(value):
    return Decimal(str(value))


# Validate the supplied tool observation identity, date, unique sources and reference arithmetic
# before using its anchor.
def asking_evidence(profile, valuation_result, as_of):
    """Check a valuation TOOL result before linking it to this consultation.

    The controller must supply the tool observation, never an LLM-invented range.
    These checks detect mismatches; they do not independently authenticate ads.
    """
    if valuation_result is None:
        return {'status': 'not_provided', 'reference': None}, []
    questions = []
    identity = valuation_result.get('seller_profile', {})
    for name in ('brand', 'model', 'variant', 'year', 'transmission'):
        value = getattr(profile.vehicle, name)
        if value is None or (value != identity.get(name) if name == 'year' else key(value) != key(identity.get(name))):
            questions.append(f'The valuation is not linked to a confirmed matching {name}. Confirm the vehicle identity.')
    if valuation_result.get('as_of') != as_of.isoformat():
        questions.append('Recalculate the valuation for this consultation date before using its price reference.')
    status = valuation_result.get('status')
    evidence = {'status': status, 'reference': None, 'as_of': valuation_result.get('as_of')}
    if questions or status not in ('reference_only', 'illustrative_scenario'):
        return evidence, questions
    reference = valuation_result.get('reference') or {}
    comps = valuation_result.get('comparables', [])
    try:
        prices = [decimal(c['asking_price_myr']) for c in comps]
        sources = [c['source_reference'] for c in comps]
        ids = [c['vehicle_id'] for c in comps]
        valid = (len(comps) >= 3 and len(set(sources)) == len(comps) and len(set(ids)) == len(comps)
                 and all(p.is_finite() and p > 0 for p in prices)
                 and reference['price_basis'] == 'asking'
                 and reference['comparable_count'] == len(comps)
                 and reference['median_asking_price_myr'] == money(median(prices))
                 and reference['observed_asking_range_myr'] == [money(min(prices)), money(max(prices))])
    except (KeyError, TypeError, ValueError, ArithmeticError):
        valid = False
    if not valid:
        return evidence, ['The valuation observation has inconsistent reference evidence. Re-run the valuation tool.']
    evidence.update(status='asking_reference', reference=reference,
                    sources=[{'vehicle_id': c['vehicle_id'], 'source_reference': c['source_reference']} for c in comps],
                    note='Only the unadjusted asking-price reference is used. An illustrative adjustment is never treated as validated market evidence.')
    return evidence, []


# Apply ordered buyer/seller rules using complete fees and stated limits; without evidence,
# assess only those limits.
def advise_negotiation(profile: NegotiationFrame, *, as_of: date, valuation_result=None):
    result = {'status': 'needs_clarification', 'profile': profile.model_dump(), 'as_of': as_of.isoformat(),
              'action': None, 'suggested_counter_price_myr': None, 'calculations': {},
              'price_position': 'not_assessed', 'fired_rules': [],
              'clarification_questions': list(profile.clarification_notes),
              'policy': {'version': 'negotiation-v1', 'method': 'Hand-authored decision tree; no trained model.',
                         'buyer_limit': 'Total cash price including all stated buyer fees.',
                         'seller_limit': 'Minimum net proceeds after all stated fees and current-loan settlement.',
                         'counter_anchor': 'Unadjusted asking median when available, bounded by the user limit and stated asking price; otherwise the user limit or stated asking price.'},
              'limitations': ['Suggestions do not execute, accept or guarantee any deal.',
                             'Asking-price evidence does not establish a fair transaction price or an optimal counter-offer.',
                             'Purchase financing, interest and future ownership costs are not modelled.']}
    questions, trace = result['clarification_questions'], result['fired_rules']
    evidence, evidence_questions = asking_evidence(profile, valuation_result, as_of)
    result['valuation_evidence'] = evidence
    questions.extend(evidence_questions)
    if evidence_questions:
        trace.append({'rule_id': 'NEG_EVIDENCE_LINK', 'reason': 'Valuation identity, date or arithmetic must be resolved before advice.'})
        return result
    if evidence['status'] == 'inspection_required':
        result['status'] = 'inspection_required'
        trace.append({'rule_id': 'NEG_DAMAGE', 'reason': 'The linked valuation requires inspection; ordinary price negotiation is withheld.'})
        return result
    required = {'role': 'Are you the buyer or seller?', 'current_offer_myr': 'What vehicle price has the other party currently offered, excluding separately stated fees?',
                'fees_myr': 'What is the total applicable fee amount in MYR? Enter zero only if confirmed.',
                'fees_confirmed_complete': 'Have all applicable fees been confirmed? A known subtotal is not a complete total.'}
    if profile.role == 'buyer':
        required['buyer_total_budget_myr'] = 'What is your maximum total purchase budget including fees?'
    elif profile.role == 'seller':
        required.update(seller_minimum_net_myr='What minimum net amount must remain after fees and loan settlement?',
                        loan_settlement_myr='What is the current loan settlement amount? Enter zero only if confirmed debt-free.')
    for field, question in required.items():
        if getattr(profile, field) is None or (field == 'fees_confirmed_complete' and getattr(profile, field) is not True):
            questions.append(question)
    if questions:
        trace.append({'rule_id': 'NEG_REQUIRED', 'reason': 'Unknown or partial fees and missing limits are clarified, never assumed to be zero.'})
        return result
    offer, fees = decimal(profile.current_offer_myr), decimal(profile.fees_myr)
    ref = evidence['reference']
    anchor = decimal(ref['median_asking_price_myr']) if ref else None
    if ref:
        low, high = map(decimal, ref['observed_asking_range_myr'])
        result['price_position'] = 'below_observed_asking_range' if offer < low else 'above_observed_asking_range' if offer > high else 'within_observed_asking_range'
    result['status'] = 'advice_ready' if ref else 'limited_advice'
    if not ref:
        result['limitations'].append('No usable linked valuation reference: advice concerns the stated budget/reserve only; price fairness is not assessed.')

    # Write one chosen action/counter and its rule explanation into the result, consistently
    # across tree branches.
    def decision(rule, action, reason, counter=None):
        result['action'] = action
        result['suggested_counter_price_myr'] = money(counter) if counter is not None else None
        trace.append({'rule_id': rule, 'reason': reason})

    if profile.role == 'buyer':
        budget = decimal(profile.buyer_total_budget_myr)
        # Buyer hard limit: vehicle counter + fees <= total purchase budget.
        # A website asking anchor can lower the counter, never raise this cap.
        cap = budget - fees
        result['calculations'] = {'offered_total_cost_myr': money(offer + fees), 'total_budget_myr': money(budget),
                                  'maximum_vehicle_price_myr': money(max(Decimal(0), cap)),
                                  'formula': 'Total cost = offered vehicle price + fees; vehicle-price cap = total budget - fees.'}
        if cap <= 0:
            decision('NEG_BUY_FEES', 'review_budget_or_fees', 'Fees consume the total budget; no positive vehicle-price counter is feasible.')
        elif offer > cap:
            counter = min(cap, anchor) if anchor is not None else cap
            if profile.asking_price_myr is not None:
                counter = min(counter, decimal(profile.asking_price_myr))
            decision('NEG_BUY_BUDGET', 'counter_offer', 'The current total exceeds the budget. The proposed vehicle price plus fees stays within the budget.', counter)
        elif ref and offer > high:
            counter = min(cap, anchor)
            if profile.asking_price_myr is not None:
                counter = min(counter, decimal(profile.asking_price_myr))
            decision('NEG_BUY_REFERENCE', 'counter_offer', 'The quote fits the budget but exceeds the observed asking range. The asking median is a discussion anchor, not a proven fair price.', counter)
        elif ref and offer < low:
            decision('NEG_BUY_LOW_REFERENCE', 'verify_listing_details', 'The quote is below the observed asking range. Check condition, specification and fee differences before judging it.')
        else:
            decision('NEG_BUY_WITHIN_LIMIT', 'review_offer', 'The quote fits the stated budget. Review the vehicle and terms; no deal is automatically accepted.')
    else:
        settlement = decimal(profile.loan_settlement_myr)
        # Seller hard limit: counter - fees - loan settlement >= minimum net.
        # The required gross vehicle-price floor therefore adds both costs.
        minimum = decimal(profile.seller_minimum_net_myr)
        floor = minimum + fees + settlement
        net = offer - fees - settlement
        result['calculations'] = {'offered_net_proceeds_myr': money(net), 'minimum_net_proceeds_myr': money(minimum),
                                  'minimum_vehicle_price_myr': money(floor),
                                  'formula': 'Net proceeds = offered vehicle price - fees - loan settlement; minimum vehicle price = minimum net + fees + loan settlement.'}
        if profile.asking_price_myr is not None and decimal(profile.asking_price_myr) < floor:
            result.update(status='needs_clarification', action=None)
            questions.append('Your asking price cannot meet the minimum net proceeds after fees and loan settlement. Confirm the asking price or minimum net.')
            trace.append({'rule_id': 'NEG_SELL_CONFLICT', 'reason': 'The stated asking price contradicts the net-proceeds floor.'})
            return result
        target = anchor if anchor is not None else decimal(profile.asking_price_myr) if profile.asking_price_myr is not None else floor
        if profile.asking_price_myr is not None:
            target = min(target, decimal(profile.asking_price_myr))
        target = max(floor, target)
        if net < minimum:
            decision('NEG_SELL_RESERVE', 'counter_offer', 'The bid leaves less than the required net proceeds. The counter covers the stated reserve, fees and settlement.', target)
        elif ref and offer < low and target > offer:
            decision('NEG_SELL_REFERENCE', 'counter_offer', 'The bid meets the reserve but is below the observed asking range. A bounded asking-reference anchor can be discussed.', target)
        else:
            decision('NEG_SELL_WITHIN_LIMIT', 'review_offer', 'The bid meets the stated minimum net proceeds. Review the remaining terms; no sale is automatically accepted.')
    return result
