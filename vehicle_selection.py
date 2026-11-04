"""Resolve explicit option numbers against the session's checked buying order.

This is conversation memory lookup, not a price prediction or an LLM guess.
Unsupported/ambiguous references ask the customer to choose a numbered option.
"""
from dataclasses import dataclass
import re

from matching import filter_vehicles

WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
         'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5}
TOKEN = r'(?:\d+(?:st|nd|rd|th)?|first|second|third|fourth|fifth|one|two|three|four|five)'
NOUN = r'(?:options?|cars?|vehicles?|candidates?|recommendations?)'
NUMBERED = re.compile(rf'\b{NOUN}\s*(?:number\s*|no\.?\s*|#\s*)?({TOKEN})\b', re.I)
ORDINAL = re.compile(rf'\b(first|second|third|fourth|fifth)\s+(?:one|{NOUN})\b', re.I)
CHOOSE = re.compile(rf'\b(?:choose|select|pick)\s+(?:the\s+)?({TOKEN})\b', re.I)


@dataclass(frozen=True)
class Selection:
    requested: bool = False
    vehicle_id: str | None = None
    position: int | None = None
    question: str | None = None


def resolve_selection(state, cars, message):
    """Require one current, eligible, checked candidate; never pick an arbitrary ID."""
    if state.goal not in ('buy', 'negotiate'):
        return Selection()
    # A rejected option is not a positive choice. Keep a later explicit choice,
    # such as "not option 1; choose option 2".
    text = re.sub(rf"\b(?:not|don't\s+(?:choose|select|pick)|do not\s+(?:choose|select|pick))\s+(?:the\s+)?{NOUN}\s*(?:#\s*)?{TOKEN}\b", '', message, flags=re.I)
    found = sorted([match for pattern in (NUMBERED, ORDINAL, CHOOSE) for match in pattern.finditer(text)], key=lambda m: m.start())
    generic = re.search(r'\b(?:choose|select|pick)\b|\b(?:that|this)\s+(?:one|car|vehicle)\b', text, re.I)
    if not found and not generic:
        return Selection()
    values = []
    for match in found:
        token = match[1].casefold()
        values.append(WORDS[token] if token in WORDS else int(re.sub(r'(st|nd|rd|th)$', '', token)))
        # "option 1 or 2" is two choices, not permission to silently choose 1.
        following = re.match(rf'\s*(?:or|and|/)\s*(?:the\s+)?({TOKEN})\b', text[match.end():], re.I)
        if following:
            token = following[1].casefold()
            values.append(WORDS[token] if token in WORDS else int(re.sub(r'(st|nd|rd|th)$', '', token)))
    positions = set(values)
    if len(positions) != 1:
        return Selection(True, question='Which single recommended vehicle do you mean? Reply with an option number, for example "option 1".')
    position = positions.pop()
    if not state.ranked_vehicle_ids:
        return Selection(True, position=position, question='There is no checked recommendation list in this session. Run a Buy consultation first, then choose an option from its results.')
    if position < 1 or position > len(state.ranked_vehicle_ids):
        return Selection(True, position=position, question=f'Option {position} is outside the saved recommendation list. Choose an option from 1 to {len(state.ranked_vehicle_ids)}.')
    vehicle_id = state.ranked_vehicle_ids[position - 1]
    eligible = {r['vehicle']['vehicle_id'] for r in filter_vehicles(state.buyer, cars)['matches']}
    if vehicle_id not in eligible:
        return Selection(True, position=position, question='That recommendation is no longer available under the saved buyer requirements. Run the Buy search again before choosing a vehicle.')
    car = next(c for c in cars if c.vehicle_id == vehicle_id)
    # Explicitly naming another model/variant in this turn conflicts with the
    # option reference. Ask rather than overwrite a genuine user correction.
    if state.goal == 'negotiate':
        for field in ('brand', 'model', 'variant', 'year', 'transmission'):
            source = state.provenance.get('negotiation.vehicle.' + field, {})
            value = getattr(state.negotiation.vehicle, field)
            if source.get('turn') == state.turn and source.get('source') == 'current user message' and value is not None:
                if str(value).casefold() != str(getattr(car, field)).casefold():
                    return Selection(True, position=position, question=f'Option {position} does not match the {field} you just stated. Confirm the option number or the vehicle details before negotiating.')
    return Selection(True, vehicle_id, position)
