"""Typed form inputs become evidence-backed updates for the existing Agent Loop.

There is no Streamlit dependency here. Forms skip language extraction because
their fields are explicit, but still use grounding, memory, planning and checks.
"""
from dataclasses import dataclass
from decimal import Decimal
import re
from pydantic import ValidationError
from agent_state import SessionState, SlotUpdate, TurnPatch, set_slot, switch_goal
from buyer_usage import USAGES, parse_usage_list
from input_grounding import money_number_value

GOALS = {'buy': 'Buy', 'sell': 'Sell', 'negotiate': 'Negotiation', 'trade_in': 'Trade-In'}
INTENTS = {'buy': 'I want to buy a car.', 'sell': 'I want to sell my car.',
           'negotiate': 'I want to negotiate.', 'trade_in': 'I want to compare trade-in with private sale.'}


@dataclass(frozen=True)
class FormField:
    # A small presentation definition; allowed types/ranges still come from Frames.
    path: str
    label: str
    kind: str = 'text'
    choices: tuple = ()
    group: str = 'Details'


# Build the editable fields for one task; navigation alone never changes state.
def fields_for(goal):
    if goal not in GOALS:
        raise ValueError('Choose a supported consultation area.')
    if goal == 'buy':
        return [FormField('buyer.budget_myr', 'Maximum vehicle-price budget (MYR)', 'money'),
                FormField('buyer.family_size', 'Household size (people)', 'integer'),
                FormField('buyer.household_travels_together', 'Will all household members travel together?', 'boolean'),
                FormField('buyer.required_seats', 'Minimum seats required', 'integer'),
                FormField('buyer.usage', 'Driving use', 'usage'),
                FormField('buyer.fuel_priority', 'Fuel-economy priority', 'choice', ('high', 'medium', 'low')),
                FormField('buyer.space_priority', 'Luggage-space priority', 'choice', ('high', 'medium', 'low')),
                FormField('buyer.safety_priority', 'Safety-equipment priority', 'choice', ('high', 'medium', 'low')),
                FormField('buyer.comfort_priority', 'Review-based comfort priority', 'choice', ('high', 'medium', 'low')),
                FormField('buyer.reliability_priority', 'Ownership-opinion reliability priority', 'choice', ('high', 'medium', 'low')),
                FormField('buyer.preferred_brands', 'Preferred brands (comma separated)', 'brands'),
                FormField('buyer.excluded_brands', 'Excluded brands (comma separated)', 'brands')]
    prefix = 'seller' if goal == 'sell' else 'negotiation.vehicle' if goal == 'negotiate' else 'trade_in.current_vehicle'
    identity = [FormField(prefix + '.' + name, label, kind, choices, 'Vehicle identity')
                for name, label, kind, choices in [
                    ('brand', 'Brand', 'text', ()), ('model', 'Model', 'text', ()),
                    ('variant', 'Exact variant', 'text', ()), ('year', 'Manufacturing year', 'integer', ()),
                    ('transmission', 'Transmission', 'choice', ('Automatic', 'Manual', 'D-CVT'))]]
    if goal == 'sell':
        return identity + [FormField('seller.mileage_km', 'Odometer reading', 'distance'),
                           FormField('seller.condition', 'Self-reported condition', 'choice', ('good', 'fair', 'poor')),
                           FormField('seller.major_accident_reported', 'Major accident reported?', 'boolean'),
                           FormField('seller.flood_damage_reported', 'Flood damage reported?', 'boolean')]
    if goal == 'negotiate':
        return identity + [FormField('negotiation.mileage_km', 'Odometer reading (for historical estimate)', 'distance'),
                           FormField('negotiation.major_accident_reported', 'Current vehicle major accident reported?', 'boolean'),
                           FormField('negotiation.flood_damage_reported', 'Current vehicle flood damage reported?', 'boolean'),
                           FormField('negotiation.role', 'Your negotiation role', 'choice', ('buyer', 'seller')),
                           FormField('negotiation.current_offer_myr', 'Other party vehicle quote / bid, excluding fees (MYR)', 'money'),
                           FormField('negotiation.asking_price_myr', 'Stated asking price, if known (MYR)', 'money'),
                           FormField('negotiation.fees_myr', 'Applicable fee total (MYR)', 'money'),
                           FormField('negotiation.fees_confirmed_complete', 'Are all applicable fees included?', 'boolean'),
                           FormField('negotiation.buyer_total_budget_myr', 'Buyer total budget including fees (MYR)', 'money'),
                           FormField('negotiation.seller_minimum_net_myr', 'Seller minimum NET proceeds (MYR)', 'money'),
                           FormField('negotiation.loan_settlement_myr', 'Seller old-loan settlement (MYR)', 'money')]
    fields = identity + [FormField('trade_in.mileage_km', 'Old-vehicle odometer reading (for historical estimate)', 'distance'),
                         FormField('trade_in.major_accident_reported', 'Old vehicle major accident reported?', 'boolean'),
                         FormField('trade_in.flood_damage_reported', 'Old vehicle flood damage reported?', 'boolean')]
    for path, title in [('trade_in_replacement', 'Trade-in replacement purchase'), ('trade_in_quote', 'Trade-in disposal offer'),
                        ('private_sale_replacement', 'Private-sale replacement purchase'), ('private_sale_quote', 'Private-sale disposal offer')]:
        prefix = 'trade_in.' + path
        fields.extend([FormField(prefix + '.price_myr', 'Replacement price (MYR)' if 'replacement' in path else 'Gross disposal offer (MYR)', 'money', group=title),
                       FormField(prefix + '.fees_myr', 'Full applicable fees (MYR)', 'money', group=title),
                       FormField(prefix + '.fees_confirmed_complete', 'Are these fees complete?', 'boolean', group=title)])
        if path.endswith('_quote'):
            fields.extend([FormField(prefix + '.estimated_completion_days', 'Estimated completion (days)', 'number', group=title),
                           FormField(prefix + '.estimated_effort_hours', 'Estimated effort (hours)', 'number', group=title)])
    return fields + [FormField('trade_in.loan_settlement_myr', 'Old-vehicle loan settlement (MYR)', 'money'),
                     FormField('trade_in.available_cash_myr', 'Available additional cash (MYR)', 'money'),
                     FormField('trade_in.priority', 'Your comparison priority', 'choice', ('net_cost', 'speed', 'effort'))]


# Read checked facts for display only; blank form fields never copy them back in.
def current_value(state, path):
    value = state
    for part in path.split('.'):
        value = getattr(value, part)
    return value


# Numeric forms accept an explicit decimal, not scientific notation or a currency guess.
def parse_number(raw, kind):
    text = str(raw).strip()
    if kind == 'money':
        try:
            # The visible MYR field label supplies the currency; a foreign
            # currency token is never stripped or converted.
            return float(money_number_value(text))
        except ValueError:
            raise ValueError('Enter a MYR amount such as 60000, 60k or 1 million; omit currency symbols. Use at most two decimal places.') from None
    if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?', text):
        raise ValueError('Enter a number without units or currency; the field label supplies them.')
    number = Decimal(text.replace(',', ''))
    if kind == 'integer':
        if number != int(number):
            raise ValueError('Enter a whole number.')
        return int(number)
    if kind == 'money' and number != number.quantize(Decimal('0.01')):
        raise ValueError('MYR amounts allow at most two decimal places.')
    return float(number)


# Canonical evidence contains only what the user entered or explicitly cleared.
def evidence_for(field, value, raw, unit):
    path, label = field.path, field.label
    if value is None or value == []:
        return 'Clear ' + label + '; this value is unknown.'
    if field.kind == 'distance':
        return f'The odometer reading is {raw} {unit}.'
    if path == 'buyer.household_travels_together':
        return 'All household members travel together.' if value else 'Not everyone travels together.'
    if path.endswith('major_accident_reported'):
        return 'A major accident was reported.' if value else 'No major accident.'
    if path.endswith('flood_damage_reported'):
        return 'Flood damage was reported.' if value else 'No flood damage.'
    if path.startswith('trade_in.') and path.endswith('fees_confirmed_complete'):
        scope = path.split('.')[1]
        route = 'trade-in' if scope.startswith('trade_in') else 'private-sale'
        role = 'replacement' if scope.endswith('replacement') else 'disposal'
        return f'The {route} {role} fees are ' + ('confirmed complete.' if value else 'incomplete.')
    if field.kind == 'boolean':
        return label.rstrip('?') + (' All applicable fees are confirmed complete.' if value else ' Fees are incomplete.')
    if path.endswith('family_size'):
        return f'My household size is {value} people.'
    if path.endswith('required_seats'):
        return f'I require {value} seats.'
    if field.kind in ('brands', 'usage'):
        text = ', '.join(value if field.kind == 'brands' else [name for name, key in USAGES.items() if key in value])
        return 'Replace ' + label.split(' (')[0] + ' with ' + text + '.'
    if field.kind == 'money':
        if path.startswith('trade_in.') and ('_quote.' in path or '_replacement.' in path):
            parts = path.split('.')
            scope = 'trade-in' if parts[1].startswith('trade_in') else 'private-sale'
            role = 'replacement' if 'replacement' in parts[1] else 'disposal'
            item = 'fees' if parts[2] == 'fees_myr' else 'price' if role == 'replacement' else 'gross offer'
            return f'The {scope} {role} {item} is RM{value:.2f}.'
        return label.split(' (')[0] + f' is RM{value:.2f}.'
    if path.endswith('.year'):
        return f'The manufacturing year is {value}.'
    if path.startswith('trade_in.') and path.endswith(('estimated_completion_days', 'estimated_effort_hours')):
        route = 'trade-in' if path.split('.')[1].startswith('trade_in') else 'private-sale'
        return (f'The {route} estimated completion time is {value} days.' if path.endswith('estimated_completion_days')
                else f'The {route} estimated hands-on effort is {value} hours.')
    return label + ' is ' + str(value) + '.'


# Validate the complete proposed frame on a copy, leaving the live session intact on error.
def prepare_form(goal, entries, state=None, *, mileage_unit='km'):
    definitions = {field.path: field for field in fields_for(goal)}
    if set(entries) - set(definitions):
        raise ValueError('A form contains an unsupported field for this consultation area.')
    if mileage_unit not in ('km', 'm', 'miles'):
        raise ValueError('Choose km, m or miles for the odometer unit.')
    working = (state or SessionState()).model_copy(deep=True)
    switch_goal(working, goal)
    updates = []
    for path, raw in entries.items():
        if raw is None or not str(raw).strip():
            continue  # Blank means keep, not unknown and not zero.
        field = definitions[path]
        text = str(raw).strip()
        try:
            if text.casefold() in ('unknown', 'clear'):
                value = [] if field.kind in ('brands', 'usage') else None
            elif field.kind == 'boolean':
                if text not in ('Yes', 'No'):
                    raise ValueError('Choose Yes, No or Unknown.')
                value = text == 'Yes'
            elif field.kind == 'choice':
                if text not in field.choices:
                    raise ValueError('Choose a listed value.')
                value = text
            elif field.kind in ('integer', 'number', 'money', 'distance'):
                value = parse_number(text, field.kind)
                if field.kind == 'distance':
                    value = float(Decimal(str(value)) * {'km': Decimal(1), 'm': Decimal('0.001'), 'miles': Decimal('1.609344')}[mileage_unit])
            elif field.kind in ('brands', 'usage'):
                value = list(dict.fromkeys(part.strip() for part in text.split(',') if part.strip()))
                if field.kind == 'usage':
                    value = parse_usage_list(text)
            else:
                if len(text) > 120 or any(c in text for c in '\n\r;'):
                    raise ValueError('Enter a short single-line identity value.')
                value = text
            set_slot(working, path, value)
            evidence = evidence_for(field, value, text, mileage_unit)
            updates.append(SlotUpdate(slot=path, value=value, evidence=evidence))
        except ValidationError as error:
            # Show the actual field problem, not a Python Frame class heading.
            detail = error.errors()[0]['msg']
            examples = ' Examples: 60000, 60k or 1 million.' if field.kind == 'money' else ''
            raise ValueError(f'{field.label}: {detail}.{examples}') from None
        except (ValueError, KeyError, ArithmeticError) as error:
            raise ValueError(f'{field.label}: {str(error).splitlines()[0]}') from error
    if not updates:
        raise ValueError('Enter at least one update. Blank fields keep confirmed facts; use Unknown to clear a field.')
    message = INTENTS[goal] + '\n' + '\n'.join(update.evidence for update in updates)
    patch = TurnPatch(goal=goal, goal_evidence=INTENTS[goal], updates=updates)
    return message, patch
