"""Bounded English rules for quote meaning, current memory and damage reports.

Inclusive/net amounts need clarification; changed quotes need fresh fee
confirmation. These rules never estimate unknown fees or settlement amounts.
"""
import re
from input_grounding import MONEY, money_number_value, clause_before, clause_after, ground_seller
from seller_profile import SellerVehicleFrame

HISTORY = ('major_accident_reported', 'flood_damage_reported')
QUOTES = ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote')

# A counterpart quote is different from a listing's asking price or our own
# proposed counter. Keep the party label, rather than trusting an LLM's slot.
OFFER_LABEL = re.compile(
    r"\b(?P<party>seller|buyer|other\s+party|my|our)(?:['’]s)?\s+"
    r'(?:(?:current|latest|new|vehicle|gross|bare|cash|net)\s+)*'
    r'(?:offer|bid|quote)\b', re.I)


def explicit_current_offers(message, role=None):
    """Read bounded, explicitly attributed quotes from this message only.

    None role is used only to detect an asking-price misclassification. For
    recovery, buyer requires a seller quote and seller requires a buyer bid.
    Unlabelled amounts, our counters, budgets and hypothetical quotes stay out.
    """
    records = []
    for match in MONEY.finditer(message):
        # The bounded clause helpers remove punctuation; inspect the original
        # sentence tail as well so a question cannot become a reported quote.
        sentence_tail = re.split(r'(?<=[.!?])\s+|\n', message[match.end():], maxsplit=1)[0]
        if '?' in sentence_tail:
            continue
        before, after = clause_before(message, match.start()), clause_after(message, match.end())
        labels = list(OFFER_LABEL.finditer(before))
        if not labels:
            continue
        label = labels[-1]
        party = label['party'].casefold()
        if party in ('my', 'our') or (role == 'buyer' and party == 'buyer') or (role == 'seller' and party == 'seller'):
            continue
        if role not in (None, 'buyer', 'seller'):
            continue
        # A later money label changes the subject of the amount. Do not carry
        # "seller offer" into "fees RM1000" or "budget RM300000".
        tail = before[label.end():]
        if re.search(r'\b(fees?|budget|settlement|asking|listed|minimum|reserve|deposit|instalments?|installments?)\b', tail, re.I):
            continue
        context = before + match.group() + after
        if ('?' in context or re.search(r'\b(if|hypothetically|example|assuming|suppose|might|could|would)\b', before, re.I)
                or re.search(r'\b(not|no|never|withdrawn|previous|old|former|rejected|around|about|approximately|between)\b', before, re.I)):
            continue
        currency = (match['currency'] or match['suffix_currency']).upper()
        amount = float(money_number_value(match['number'] or match['suffix_number']))
        records.append((amount if currency in ('RM', 'MYR', 'RINGGIT') else None, context))
    return records


def recover_current_offer(state, message):
    """Repair omitted/misfiled counterpart quotes without a market estimate."""
    if state.goal != 'negotiate' or state.negotiation.role is None:
        return
    from agent_state import set_slot
    records = explicit_current_offers(message, state.negotiation.role)
    if not records:
        return
    slot = 'negotiation.current_offer_myr'
    amounts = {amount for amount, _ in records}
    value = records[0][0] if len(amounts) == 1 else None
    if value is not None and value <= 0:
        value = None
    set_slot(state, slot, value)
    state.issues.pop(slot, None)
    if value is None:
        state.issues[slot] = 'State one positive current quote from the other party in RM/MYR; conflicting or unsupported-currency quotes cannot be used.'
    state.provenance[slot] = {'turn': state.turn, 'evidence': ' '.join(text for _, text in records),
                              'source': 'explicit counterpart-quote rule; not an asking-price or model estimate'}
    state.event('rules', rule_id='NEG_CURRENT_OFFER_SOURCE', slot=slot, value=value,
                reason='An explicitly attributed counterpart quote owns the current-offer slot; preserve the source amount, not an LLM slot guess.')


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
    recover_current_offer(state, message)
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
