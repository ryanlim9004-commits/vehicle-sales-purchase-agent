"""Per-turn evidence validation; omission never erases previously known facts."""
# Learning guide:
# Validate evidence for each proposed update before merging session facts.
# Use the current user message, not model claims, as the source of a correction.
# Labelled quote rules keep replacement prices, gross offers and fees separate.
import re
from decimal import Decimal
from pydantic import ValidationError
from agent_state import SLOTS, set_slot, switch_goal
from input_grounding import MONEY, NUMBER, number_value, money_number_value, budget_from_text, stated_buyer_budget, mileage_from_text, ground_seller, clause_before, clause_after
from seller_profile import SellerVehicleFrame
from input_grounding import ground_reference_priority, explicit_buyer_usages, explicit_priority_clear
from buyer_usage import ground_usage_update, usage_replacement_requested, ambiguous_buyer_travel


QUOTE_MONEY_SLOTS = {f'trade_in.{scope}.{field}' for scope in ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote') for field in ('price_myr', 'fees_myr')}


# Recover amounts only when current wording labels both the financial path and the
# replacement/disposal role.
def explicit_quote_amounts(message):
    """Recover only explicitly labelled cash quotes; never use a market reference.

    Sentence-local scope carries into 'with replacement fees ...', but a new
    trade-in/private-sale label takes precedence. Unlabelled amounts stay unknown.
    """
    recovered = {}
    for sentence in re.split(r'(?<=[.!?])\s+', message):
        for match in MONEY.finditer(sentence):
            prefix = sentence[:match.start()].casefold().replace('-', ' ')
            trade, private = prefix.rfind('trade in'), prefix.rfind('private sale')
            if max(trade, private) < 0:
                continue
            path = 'trade_in' if trade > private else 'private_sale'
            replacement = prefix.rfind('replacement')
            disposal = max(prefix.rfind('disposal'), prefix.rfind('gross'), prefix.rfind('offer'), prefix.rfind('proceeds'))
            # A loan/cash-limit phrase following a quote is a different amount.
            unrelated = max(prefix.rfind('loan settlement'), prefix.rfind('available cash'))
            if unrelated > max(replacement, disposal):
                continue
            if replacement >= 0 and replacement > disposal:
                scope = path + '_replacement'
            elif disposal >= 0 or re.search(r'private sale price\s*(?:is|of)?\s*$', prefix):
                scope = path + '_quote'
            else:
                continue
            clause = re.split(r'[,;]', prefix)[-1]
            field = 'fees_myr' if re.search(r'\bfees?\b[^0-9]*$', clause) else 'price_myr'
            slot = 'trade_in.' + scope + '.' + field
            currency = (match['currency'] or match['suffix_currency']).upper()
            invalid = currency not in ('RM', 'MYR', 'RINGGIT') or re.search(r'\b(monthly|per month|instalments?|installments?)\b|/\s*(?:mo|month)\b', sentence, re.I)
            amount = None if invalid else float(money_number_value(match['number'] or match['suffix_number']))
            recovered.setdefault(slot, []).append((amount, sentence))
    return recovered


# Accept one explicitly stated MYR amount or supported zero/debt-free wording; do not perform
# exchange conversion.
def money_from_evidence(text, slot):
    # Explicit zero is supported for fees/debt. Absence is never a zero.
    if slot.endswith('fees_myr') and re.search(r'\b(no fees|zero fees|fees are zero)\b', text, re.I):
        return 0.0
    if slot.endswith('loan_settlement_myr') and re.search(r'\b(debt[- ]free|no (?:outstanding )?loan|loan[- ]free)\b', text, re.I):
        return 0.0
    amounts = []
    for match in MONEY.finditer(text):
        currency = (match['currency'] or match['suffix_currency']).upper()
        if currency not in ('MYR', 'RM', 'RINGGIT'):
            raise ValueError('Please state this amount explicitly in MYR/RM; no currency conversion is performed.')
        amounts.append(money_number_value(match['number'] or match['suffix_number']))
    if not amounts or len(set(amounts)) != 1:
        raise ValueError('Please provide one explicit MYR/RM amount for this item; unknown or conflicting amounts are not assumed.')
    return float(amounts[0])


# Check the quoted substring and slot-specific unit/type/context rules before accepting a
# model-proposed value.
def grounded_value(update, message, state):
    evidence, value, slot = update.evidence.strip(), update.value, update.slot
    if evidence.casefold() not in message.casefold():
        raise ValueError('A proposed fact could not be traced to this message. Please restate it explicitly.')
    if isinstance(value, str):
        # Only lossless representation repairs are allowed here, such as
        # "2020" -> 2020 or "false" -> False; do not invent semantic facts.
        if slot.endswith(('_reported', 'fees_confirmed_complete', 'household_travels_together')) and value.casefold() in ('true', 'false'):
            value = value.casefold() == 'true'
        if slot.endswith('.year') and re.fullmatch(r'\d{4}', value):
            value = int(value)
        if slot.endswith(('fuel_priority', 'space_priority', 'safety_priority', 'comfort_priority', 'reliability_priority', '.condition', '.role', '.priority')):
            value = value.casefold()
    # A named absence of preference owns its meaning even when the model emits
    # an invalid enum such as "no preference" instead of JSON null.
    if explicit_priority_clear(evidence, slot):
        return None
    if value is None:
        if not re.search(r"\b(unknown|not sure|unsure|clear|remove|forget|don't know|do not know|no preference)\b", evidence, re.I) and not explicit_priority_clear(evidence, slot):
            raise ValueError('Missing values cannot erase a previous fact without an explicit correction or unknown statement.')
        return None
    position = message.casefold().find(evidence.casefold())
    scoped = clause_before(message, position) + evidence + clause_after(message, position + len(evidence))
    if slot in ('buyer.safety_priority', 'buyer.comfort_priority', 'buyer.reliability_priority'):
        return ground_reference_priority(evidence, slot.split('.')[1], value, pending=state.pending_slots == [slot])
    if slot.endswith('_myr') and re.search(r'\b(monthly|per month|instalments?|installments?)\b|/\s*(?:mo|month)\b', scoped, re.I):
        raise ValueError('Please provide the total applicable cash amount in MYR; a monthly instalment is not the required lump sum.')
    if slot == 'buyer.budget_myr':
        amount, _, issue = budget_from_text(evidence)
        if issue:
            raise ValueError(issue)
        return amount
    if slot.endswith('_myr'):
        return money_from_evidence(evidence, slot)
    if slot == 'seller.mileage_km':
        mileage, _, issue = mileage_from_text(scoped)
        if issue:
            raise ValueError(issue)
        return mileage
    if slot.endswith('.year'):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('Please state an integer manufacturing year.')
        checked = ground_seller(evidence, SellerVehicleFrame(year=value))
        if checked.year is None:
            raise ValueError('Please confirm the manufacturing year; registration year alone is insufficient.')
        return checked.year
    if slot == 'buyer.household_travels_together':
        if not isinstance(value, bool):
            raise ValueError('Please confirm whether all household members will travel together.')
        if value is False and re.search(r"\b(not everyone|not all|won't all|will not all)\b", evidence, re.I):
            return False
        if value is True and re.search(r'\b(everyone|all)\b.*\b(travel|ride|together)\b', evidence, re.I) and not re.search(r'\bnot\b', evidence, re.I):
            return True
        if state.pending_slots == [slot] and evidence.casefold().strip('. ') in ('yes', 'no'):
            return evidence.casefold().startswith('yes')
        raise ValueError('Please state whether everyone travels together; this cannot be inferred from household size alone.')
    if slot in ('seller.major_accident_reported', 'seller.flood_damage_reported'):
        if not isinstance(value, bool):
            raise ValueError('Damage history must be explicitly true, false or unknown.')
        field = slot.split('.')[-1]
        checked = ground_seller(evidence, SellerVehicleFrame.model_validate({field: value}))
        answer = getattr(checked, field)
        if answer is None:
            raise ValueError('Please clarify the stated accident/flood history; clean history cannot be inferred from condition.')
        return answer
    if slot.endswith('fees_confirmed_complete'):
        # A positive substring is insufficient when its sentence contains an
        # exception, e.g. "all fees complete, except insurance is unknown".
        if not isinstance(value, bool):
            raise ValueError('Please confirm whether the stated fee total is complete.')
        positive = re.search(r'\b(all|total|complete|confirmed|fully)\b', evidence, re.I)
        negative = re.search(r'\b(not|partial|unknown|unconfirmed|incomplete|no)\b', evidence, re.I)
        exception = re.search(r'\b(not|partial|unknown|unconfirmed|incomplete|except|excluding)\b', scoped, re.I)
        if value and positive and not exception:
            return True
        if not value and negative:
            return False
        if evidence.lower() in ('yes', 'yes.', 'no', 'no.') and state.pending_slots == [slot]:
            return evidence.lower().startswith('yes')
        raise ValueError('Please explicitly confirm that all applicable fees are included, or state that the amount is partial/unknown.')
    if slot.endswith(('family_size', 'required_seats', 'estimated_completion_days', 'estimated_effort_hours')):
        found = [number_value(m.group()) for m in re.finditer(rf'(?<!\w){NUMBER}(?!\w)', evidence, re.I)]
        if len(set(found)) != 1:
            raise ValueError('Please provide one explicit number for this passenger/time requirement.')
        actual = found[0]
        return int(actual) if slot.endswith(('family_size', 'required_seats')) and actual == int(actual) else float(actual)
    if slot.endswith('transmission'):
        if isinstance(value, str):
            value = {'automatic': 'Automatic', 'auto': 'Automatic', 'manual': 'Manual', 'd-cvt': 'D-CVT', 'dcvt': 'D-CVT'}.get(value.casefold(), value)
        terms = {'Automatic': r'\bauto(?:matic)?\b', 'Manual': r'\bmanual\b', 'D-CVT': r'\bd[- ]?cvt\b'}
        if value not in terms or not re.search(terms[value], evidence, re.I):
            raise ValueError('Please state Automatic, Manual or D-CVT explicitly.')
    if slot.endswith(('brand', 'model', 'variant')) and (not isinstance(value, str) or value.casefold() not in evidence.casefold()):
        raise ValueError('Vehicle identity must be grounded in the user message, not guessed from another model.')
    if slot.endswith(('preferred_brands', 'excluded_brands')):
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or any(v.casefold() not in evidence.casefold() for v in value):
            raise ValueError('Each brand must be explicitly stated.')
    if slot == 'buyer.usage':
        return ground_usage_update(value, evidence, update.operation, state.buyer.usage)
    return value


# Merge grounded current-turn updates, invalidate unsafe old facts, recover labelled quotes and
# record provenance/rules.
def apply_patch(state, patch, message):
    original_goal = state.goal
    # Record the old identity before patching so changed-vehicle corrections
    # can invalidate dependent quote/loan data after new facts are merged.
    original_identity = state.negotiation.vehicle.model_dump() if state.goal == 'negotiate' else state.trade_in.current_vehicle.model_dump() if state.goal == 'trade_in' else {}
    quote_amounts = explicit_quote_amounts(message)
    if patch.goal is not None and patch.goal != state.goal:
        if not patch.goal_evidence.strip() or patch.goal_evidence.casefold() not in message.casefold():
            state.issues['goal'] = 'Would you like to buy, sell, negotiate, or compare trade-in with private sale?'
        else:
            switch_goal(state, patch.goal)
            state.issues.pop('goal', None)
    elif state.goal is not None:
        state.issues.pop('goal', None)
    ambiguous_fuel = state.goal == 'buy' and re.search(r'\bsafe\s+fuel\b', message, re.I)
    accepted_priority_updates = set()
    prefixes = {'buy': ('buyer.',), 'sell': ('seller.',), 'negotiate': ('negotiation.',), 'trade_in': ('trade_in.',)}
    for update in patch.updates:
        slot = update.slot
        if ambiguous_fuel and slot in ('buyer.fuel_priority', 'buyer.safety_priority'):
            state.event('facts', action='defer_ambiguous_fuel_safety', slot=slot,
                        reason="'safe fuel' does not establish either preference; ask what the user means.")
            continue
        if update.value is None and not (update.evidence.casefold() in message.casefold() and (re.search(r"\b(unknown|not sure|unsure|clear|remove|forget|don't know|do not know|no preference)\b", update.evidence, re.I) or explicit_priority_clear(update.evidence, slot))):
            state.event('facts', action='ignored_unstated_null', slot=slot)
            continue
        if slot not in SLOTS or not slot.startswith(prefixes.get(state.goal, ())):
            state.issues['unsupported_fact'] = 'Please clarify the current consultation goal; a proposed field is unsupported for this task.'
            state.event('checks', name='allowed_fact_path', passed=False, slot=slot)
            continue
        if slot in QUOTE_MONEY_SLOTS and state.pending_slots != [slot]:
            # These roles are easy for a small LLM to swap. The explicit source
            # parser below owns them; an unlabelled value is not silently copied.
            state.event('facts', action='defer_quote_to_source_rule', slot=slot)
            if not quote_amounts and MONEY.search(message):
                set_slot(state, slot, None)
                state.issues[slot] = 'Please label the amount as trade-in/private-sale and replacement price/fee or gross disposal offer/fee.'
            continue
        if slot == 'buyer.required_seats' and re.search(r'\b(family|household)\b', update.evidence, re.I) and not re.search(r'\b(seats?|seaters?|passengers?)\b', update.evidence, re.I):
            state.event('facts', action='ignored_inferred_seats', reason='A household count is not an explicitly stated seat requirement; Python rules derive it.')
            continue
        try:
            value = grounded_value(update, message, state)
            if slot == 'buyer.usage' and value == [] and update.value != []:
                state.event('facts', action='ignored_prior_usage_context', slot=slot,
                            reason='Copied prior uses have no current source evidence; confirmed memory is kept.')
                continue
            operation = update.operation
            # An additional stated preference must not silently delete the
            # existing list. Full replacement requires an explicit cue.
            if isinstance(value, list) and operation == 'set' and not re.search(r'\b(only|replace|instead|clear|no .*preference)\b', update.evidence, re.I):
                operation = 'add'
            set_slot(state, slot, value, operation)
            state.issues.pop(slot, None)
            if slot in ('buyer.fuel_priority', 'buyer.safety_priority'):
                accepted_priority_updates.add(slot)
            if slot == 'buyer.usage':
                state.provenance.pop('buyer.usage_pending', None)
            state.issues.pop('unsupported_fact', None)
            state.provenance[slot] = {'turn': state.turn, 'evidence': update.evidence, 'source': 'current user message'}
            state.event('facts', action='update', slot=slot, value=value, operation=operation, evidence=update.evidence)
            if slot.startswith('buyer.'):
                state.ranked_vehicle_ids = []
                state.selected_vehicle_id = None
        except (ValueError, TypeError, ValidationError) as error:
            # A failed correction invalidates the old field instead of letting
            # an obsolete amount silently drive a new recommendation.
            try:
                # A bad model proposal is not an instruction to erase uses the
                # customer already confirmed. Current source words below can
                # resolve the question even when model extraction fails.
                if slot != 'buyer.usage':
                    set_slot(state, slot, [] if isinstance(SLOTS[slot], list) else None)
            except (ValueError, ValidationError):
                pass
            state.issues[slot] = str(error).split('\n')[0]
            state.event('checks', name='source_grounding', passed=False, slot=slot, proposed_value=update.value, detail=state.issues[slot])
            if slot.startswith('buyer.'):
                state.ranked_vehicle_ids = []
                state.selected_vehicle_id = None
    if state.goal == 'buy':
        # Recheck the full explicit budget clause, including a scale the model
        # may have omitted from its evidence (e.g. RM1 from RM1 million).
        stated_budget = stated_buyer_budget(message, pending=state.pending_slots == ['buyer.budget_myr'])
        if stated_budget:
            amount, notes, issue, evidence = stated_budget
            set_slot(state, 'buyer.budget_myr', None if issue else amount)
            if issue:
                state.issues['buyer.budget_myr'] = issue
            else:
                state.issues.pop('buyer.budget_myr', None)
            state.provenance['buyer.budget_myr'] = {'turn': state.turn, 'evidence': evidence, 'source': 'explicit budget source rule'}
            state.event('rules', rule_id='BUY_BUDGET_SOURCE', reason='Check the stated currency, scale and total budget before matching; saved listing prices do not cap the customer budget.',
                        evidence=evidence, derived_fact={'buyer.budget_myr': state.buyer.budget_myr}, notes=notes, issue=issue)
            state.ranked_vehicle_ids = []
            state.selected_vehicle_id = None
        # Explicit named clearing also works when the model omits the slot.
        # It cannot clear another priority: "no safety preference" names safety.
        for name in ('fuel', 'space', 'safety', 'comfort', 'reliability'):
            slot = 'buyer.' + name + '_priority'
            if explicit_priority_clear(message, slot):
                set_slot(state, slot, None)
                state.issues.pop(slot, None)
                if slot in ('buyer.fuel_priority', 'buyer.safety_priority'):
                    accepted_priority_updates.add(slot)
                state.provenance[slot] = {'turn': state.turn, 'evidence': message,
                                          'source': 'explicit named no-preference rule'}
                state.event('rules', rule_id='BUY_CLEAR_PRIORITY', reason='The current message explicitly states no preference for this named priority.',
                            evidence=message, derived_fact={slot: None})
                state.ranked_vehicle_ids = []
                state.selected_vehicle_id = None
        # Recover omitted additions even when another use is already remembered.
        # Explicit replacement wording still replaces rather than appending.
        uses = explicit_buyer_usages(message)
        replacement = usage_replacement_requested(message)
        recovered = [label for label, _ in uses]
        desired = recovered if replacement else list(dict.fromkeys(state.buyer.usage + recovered))
        unresolved = 'buyer.usage' in state.issues
        if uses and (desired != state.buyer.usage or unresolved):
            set_slot(state, 'buyer.usage', desired)
            state.issues.pop('buyer.usage', None)
            state.provenance.pop('buyer.usage_pending', None)
            phrase = message
            state.provenance['buyer.usage'] = {'turn': state.turn, 'evidence': phrase, 'source': 'current user message; explicit usage recovery'}
            state.event('rules', rule_id='BUY_USAGE_SOURCE', reason='Accept current source-supported uses and resolve prior usage questions; preserve other confirmed uses unless replacement is explicit.', evidence=phrase, derived_fact={'buyer.usage': desired})
            state.ranked_vehicle_ids = []
            state.selected_vehicle_id = None
        elif not uses and (phrase := ambiguous_buyer_travel(message)):
            state.issues['buyer.usage'] = 'You mentioned travel. Is this family travel, city commuting, or long-distance driving?'
            state.provenance['buyer.usage_pending'] = {'turn': state.turn, 'evidence': phrase,
                                                       'source': 'current user message; category awaiting clarification'}
        if uses:
            # Also remove pending wording when the model already installed
            # exactly these facts and there is no value change to recover.
            state.provenance.pop('buyer.usage_pending', None)
        if ambiguous_fuel:
            state.issues['buyer.fuel_safety_wording'] = "By 'safe fuel', do you mean fuel economy ('save fuel'), vehicle safety, or both? Please state the preference explicitly, or say it is unknown."
            state.provenance['buyer.fuel_safety_wording'] = {'turn': state.turn, 'evidence': ambiguous_fuel.group(),
                                                            'source': 'current user message; meaning awaiting clarification'}
        elif 'buyer.fuel_safety_wording' in state.issues:
            # Resolve this wording question only from a new explicit answer.
            # The usual source validation still owns the actual slot values.
            answer = message.strip().casefold().rstrip('.!')
            single_question = state.pending_slots == ['buyer.fuel_safety_wording']
            if single_question and answer in ('both', 'both please', 'both are important'):
                for slot in ('buyer.fuel_priority', 'buyer.safety_priority'):
                    set_slot(state, slot, 'high')
                    state.issues.pop(slot, None)
                    state.provenance[slot] = {'turn': state.turn, 'evidence': message,
                                              'source': 'direct answer to the sole pending fuel-economy / safety choice'}
                state.event('rules', rule_id='BUY_FUEL_SAFETY_ANSWER', reason='Both refers to the sole pending fuel-economy and safety choice.',
                            evidence=message, derived_fact={'buyer.fuel_priority': 'high', 'buyer.safety_priority': 'high'})
            if (single_question and answer in ('both', 'both please', 'both are important', 'unknown', 'not sure')
                    or accepted_priority_updates and re.search(r'\b(?:save fuel|fuel[- ]economy|fuel[- ]efficient|fuel priority|safety preference|safety priority|vehicle safety|safety[- ]equipment)\b', message, re.I)):
                state.issues.pop('buyer.fuel_safety_wording', None)
                state.provenance.pop('buyer.fuel_safety_wording', None)
    if state.goal == original_goal and state.goal in ('negotiate', 'trade_in'):
        # Old-vehicle quotes depend on identity. Preserve only amounts that
        # were explicitly refreshed in this same turn, plus user budget limits.
        current = state.negotiation.vehicle if state.goal == 'negotiate' else state.trade_in.current_vehicle
        changed_vehicle = any(previous is not None and str(previous).strip().casefold() != str(getattr(current, field)).strip().casefold() for field, previous in original_identity.items())
        if changed_vehicle:
            if state.goal == 'negotiate':
                affected = ['negotiation.' + field for field in ('asking_price_myr', 'current_offer_myr', 'fees_myr', 'fees_confirmed_complete', 'seller_minimum_net_myr', 'loan_settlement_myr')]
                state.negotiation_from_seller = False
            else:
                affected = [slot for slot in SLOTS if slot.startswith(('trade_in.trade_in_', 'trade_in.private_sale_'))] + ['trade_in.loan_settlement_myr']
                state.trade_in_from_seller = False
            for slot in affected:
                if state.provenance.get(slot, {}).get('turn') != state.turn:
                    set_slot(state, slot, None)
                    state.event('facts', action='invalidate_vehicle_dependent_fact', slot=slot, reason='The vehicle identity changed; no old quote or fee is silently reused.')
            state.selected_vehicle_id = None
    if state.goal == 'trade_in':
        for slot, observations in quote_amounts.items():
            values = {value for value, _ in observations}
            if None in values:
                set_slot(state, slot, None)
                state.issues[slot] = 'Please provide a total cash quote in MYR/RM; monthly payments and foreign currencies are not substituted.'
                continue
            if len(values) != 1:
                set_slot(state, slot, None)
                state.issues[slot] = 'Conflicting cash quotes were supplied for this path. Confirm one MYR amount.'
                continue
            value, evidence = observations[0]
            try:
                set_slot(state, slot, value)
                state.issues.pop(slot, None)
                state.provenance[slot] = {'turn': state.turn, 'evidence': evidence, 'source': 'explicit quote-role rule'}
                state.event('facts', action='update', slot=slot, value=value, evidence=evidence, source='explicit quote-role rule')
                state.event('rules', rule_id='INPUT_QUOTE_ROLE', reason='A labelled replacement price/fee is kept separate from a gross disposal offer/fee.', slot=slot)
            except (ValueError, ValidationError):
                state.issues[slot] = 'Please confirm a valid MYR price/fee for this quoted path.'
    # Explicit global confirmation is a production rule, not an inferred zero.
    # Missing amounts still remain missing even when completeness is confirmed.
    confirmation = re.search(r'\ball fees\b[^.!?\n]{0,180}\b(?:complete|confirmed)\b', message, re.I)
    confirmation_context = (clause_before(message, confirmation.start()) + re.split(r'(?<=[.!?])\s+|\n', message[confirmation.start():], maxsplit=1)[0]) if confirmation else ''
    if confirmation and not re.search(r'\b(not|partial|unknown|incomplete|except|excluding)\b', confirmation_context, re.I):
        paths = ['negotiation.fees_confirmed_complete'] if state.goal == 'negotiate' else [f'trade_in.{name}.fees_confirmed_complete' for name in ('trade_in_replacement', 'private_sale_replacement', 'trade_in_quote', 'private_sale_quote')] if state.goal == 'trade_in' else []
        for slot in paths:
            set_slot(state, slot, True)
            state.issues.pop(slot, None)
            state.provenance[slot] = {'turn': state.turn, 'evidence': confirmation.group(), 'source': 'explicit all-fees confirmation rule'}
        if paths:
            state.event('rules', rule_id='INPUT_ALL_FEES_COMPLETE', reason='The user explicitly confirmed all applicable fees; unknown fee amounts are not filled.', slots=paths)
    state.revision += 1
    return state
