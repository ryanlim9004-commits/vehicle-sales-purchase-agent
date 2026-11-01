"""Bounded English rules for quote meaning, current memory and damage reports.

Inclusive/net amounts need clarification; changed quotes need fresh fee
confirmation. These rules never estimate unknown fees or settlement amounts.
"""
import re
from input_grounding import MONEY, money_number_value, clause_before, clause_after, ground_seller
from seller_profile import SellerVehicleFrame

HISTORY = ('major_accident_reported', 'flood_damage_reported')
QUOTES = ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote')


def snapshot(state):
    if state.goal not in ('negotiate', 'trade_in'):
        return None
    frame = state.negotiation if state.goal == 'negotiate' else state.trade_in
    return {'goal': state.goal, 'profile': frame.model_dump()}


def has_damage(profile):
    return any(getattr(profile, name, None) is True for name in HISTORY)


def quoted_scopes(text):
    """Return explicitly named Trade-In packages; empty means unlabelled."""
    paths = []
    if re.search(r'\btrade[- ]?in\b', text, re.I):
        paths.append('trade_in')
    if re.search(r'\bprivate[- ]sale\b', text, re.I):
        paths.append('private_sale')
    replacement = bool(re.search(r'\breplacement\b', text, re.I))
    disposal = bool(re.search(r'\b(disposal|gross|offer|proceeds)\b', text, re.I))
    suffixes = ['_replacement'] if replacement and not disposal else ['_quote'] if disposal and not replacement else ['_replacement', '_quote']
    return [path + suffix for path in paths for suffix in suffixes]


def confirmation_scopes(state, context):
    if state.goal == 'negotiate':
        return ['negotiation.fees_confirmed_complete']
    if state.goal != 'trade_in':
        return []
    scopes = quoted_scopes(context)
    if not scopes and re.search(r'\ball\s+(?:applicable\s+|four\s+)?fees\b', context, re.I):
        scopes = list(QUOTES)
    return ['trade_in.' + name + '.fees_confirmed_complete' for name in scopes]


def quote_basis_issue(evidence, slot, amount):
    """Inspect the amount's clause, rather than a different quote nearby."""
    for match in MONEY.finditer(evidence):
        try:
            value = float(money_number_value(match['number'] or match['suffix_number']))
        except ValueError:
            continue
        if amount is None or value != amount:
            continue
        context = clause_before(evidence, match.start()) + match.group() + clause_after(evidence, match.end())
        if re.search(r'\ball[- ]in\b|\bon[- ]the[- ]road\b|\bOTR\b|\b(?:including|includes|inclusive\s+of)\s+(?:all\s+)?(?:the\s+)?fees\b', context, re.I):
            return 'This amount includes fees. Provide the bare vehicle price/gross offer excluding fees, and confirm the fee total separately; an all-in amount cannot have fees added again.'
        if ('_quote.price_myr' in slot or slot == 'negotiation.current_offer_myr') and re.search(r'\bnet\s+(?:offer|proceeds|price)\b|\bafter\s+(?:all\s+)?(?:fees|loan|settlement)|\bminus\s+(?:fees|loan)', context, re.I):
            return 'This is a net amount after costs/settlement. Provide the gross vehicle offer before fees and loan settlement, so those costs are not deducted twice.'
    return None


def recover_history(state, message):
    """Keep explicit current/old-vehicle reports even if the LLM omitted them.

    Questions, hypothetical cases and statements about the replacement car do
    not establish the current vehicle's history.
    """
    if state.goal not in ('negotiate', 'trade_in'):
        return
    from agent_state import set_slot
    prefix = 'negotiation' if state.goal == 'negotiate' else 'trade_in'
    subjects = {'major_accident_reported': r'\b(?:major\s+)?accidents?\b',
                'flood_damage_reported': r'\bflood(?:ing|ed| damage)?\b'}
    observations = {}
    unclear_severity = False
    for sentence in re.split(r'(?<=[.!?])\s+|\n', message):
        if '?' in sentence or re.search(r'\b(if|hypothetically|example|assuming|replacement|new car|new vehicle|want|prefer)\b', sentence, re.I):
            continue
        for field, subject in subjects.items():
            if not re.search(subject, sentence, re.I):
                continue
            unknown = bool(re.search(r"\b(unknown|not sure|unsure|do not know|don't know)\b", sentence, re.I))
            checked = ground_seller(sentence, SellerVehicleFrame.model_validate({field: None if unknown else True}))
            value = getattr(checked, field)
            if value is None and not unknown:
                continue
            if field == 'major_accident_reported' and value is True and not re.search(r'\bmajor\s+accidents?\b', sentence, re.I):
                unclear_severity = True
                continue
            observations.setdefault(field, []).append((value, sentence))
    for field, reports in observations.items():
        values = {value for value, _ in reports}
        slot = prefix + '.' + field
        value = reports[0][0] if len(values) == 1 else None
        set_slot(state, slot, value)
        state.issues.pop(slot, None)
        if len(values) > 1:
            state.issues[slot] = 'The current message gives conflicting/uncertain accident or flood reports. Confirm the history of this vehicle.'
        state.provenance[slot] = {'turn': state.turn, 'evidence': ' '.join(text for _, text in reports), 'source': 'explicit current/old-vehicle history rule'}
        state.event('rules', rule_id='FIN_HISTORY_SOURCE', slot=slot, value=value,
                    reason='Keep explicit current-vehicle reports; conflicting histories need clarification, never a last-sentence overwrite.')
    if unclear_severity and 'major_accident_reported' not in observations:
        slot = prefix + '.major_accident_reported'
        set_slot(state, slot, None)
        state.issues[slot] = 'Was the reported accident a major accident? A minor or unspecified accident must not automatically be recorded as major.'


def apply_guards(state, previous, message):
    if state.goal not in ('negotiate', 'trade_in'):
        return
    from agent_state import set_slot
    root = 'negotiation' if state.goal == 'negotiate' else 'trade_in'
    profile = getattr(state, root)
    old = previous['profile'] if previous and previous['goal'] == state.goal else None

    def clear(slot, reason):
        set_slot(state, slot, None)
        state.provenance.pop(slot, None)
        state.issues.pop(slot, None)
        state.event('rules', rule_id='FIN_INVALIDATE', slot=slot, reason=reason)

    def refreshed(slot):
        return state.provenance.get(slot, {}).get('turn') == state.turn

    if root == 'negotiation' and old and old['role'] is not None and old['role'] != profile.role:
        for field in ('asking_price_myr', 'current_offer_myr', 'fees_myr', 'fees_confirmed_complete',
                      'buyer_total_budget_myr', 'seller_minimum_net_myr', 'loan_settlement_myr'):
            slot = root + '.' + field
            if not refreshed(slot):
                clear(slot, 'Buyer/seller role changed; opponent quote, fees and role limits need fresh confirmation.')
    profile = getattr(state, root)
    scopes = [root] if root == 'negotiation' else [root + '.' + name for name in QUOTES]
    for scope in scopes:
        quote = profile if root == 'negotiation' else getattr(profile, scope.split('.')[1])
        before = old if root == 'negotiation' else old[scope.split('.')[1]] if old else None
        price_field = 'current_offer_myr' if root == 'negotiation' else 'price_myr'
        changed = before is not None and any(before[field] != getattr(quote, field) for field in (price_field, 'fees_myr'))
        complete_slot = scope + '.fees_confirmed_complete'
        if changed and not refreshed(complete_slot):
            clear(complete_slot, 'Quote price or fee total changed; an old fee-completeness confirmation cannot apply automatically.')
        for field in ([price_field, 'asking_price_myr'] if root == 'negotiation' else [price_field]):
            slot = scope + '.' + field
            if refreshed(slot):
                evidence = state.provenance[slot].get('evidence', '')
                position = message.casefold().find(evidence.casefold())
                if position >= 0:
                    evidence = clause_before(message, position) + evidence + clause_after(message, position + len(evidence))
                issue = quote_basis_issue(evidence, slot, getattr(quote, field))
                if issue:
                    clear(slot, 'Quote basis is inclusive/net rather than the required bare/gross amount.')
                    state.issues[slot] = issue
    for sentence in re.split(r'(?<=[.!?])\s+|\n', message):
        negative = re.search(r'\bfees?\s+(?:(?:are|is|remain|still|now)\s+)*(?:unknown|partial|incomplete|not\s+(?:yet\s+)?(?:complete|confirmed|included))\b', sentence, re.I)
        exception = re.search(r'\bfees?\b[^.!?\n]{0,100}\b(?:except|excluding|not including)\b', sentence, re.I)
        if not negative and not exception:
            continue
        if root == 'negotiation' or re.search(r'\ball fees\b', sentence, re.I):
            affected = scopes
        else:
            path = 'trade_in' if re.search(r'\btrade[- ]?in\b', sentence, re.I) else 'private_sale' if re.search(r'\bprivate[- ]sale\b', sentence, re.I) else None
            if path is None:
                continue
            if re.search(r'\breplacement\b', sentence, re.I):
                affected = [root + '.' + path + '_replacement']
            elif re.search(r'\b(disposal|gross|offer|sale)\b', sentence, re.I):
                affected = [root + '.' + path + '_quote']
            else:
                affected = [root + '.' + path + suffix for suffix in ('_replacement', '_quote')]
        for scope in affected:
            slot = scope + '.fees_confirmed_complete'
            unknown = bool(re.search(r'\bunknown\b', negative.group() if negative else sentence, re.I))
            if unknown:
                clear(slot, 'The user states the fee total/completeness is unknown.')
                clear(scope + '.fees_myr', 'The user states the fee amount is unknown.')
            else:
                set_slot(state, slot, False)
                state.provenance[slot] = {'turn': state.turn, 'evidence': sentence, 'source': 'explicit incomplete-fees rule'}
    recover_history(state, message)
