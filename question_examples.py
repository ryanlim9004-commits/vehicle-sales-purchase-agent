"""Read-only, catalogue-backed examples for English consultation questions.

Examples explain how to answer. They never populate a Frame, a quote or a
fee. Vehicle identity values come from the Controller's actual catalogue;
money/condition/history examples are explicitly formats or user declarations.
"""
import re

GOALS = {'sell', 'negotiate', 'trade_in'}
IDENTITY_ORDER = ('brand', 'model', 'variant', 'year', 'transmission')


def normal(value):
    return ' '.join(str(value or '').casefold().split())


def identity_frame(state, goal):
    if goal == 'sell':
        return state.seller
    if goal == 'negotiate':
        return state.negotiation.vehicle
    return state.trade_in.current_vehicle


def catalogue_choices(field, state, cars, *, goal=None, format_fallback=False):
    """Use earlier confirmed identity slots; never substitute unrelated cars.

    Real saved advertisements are shown first, then the teaching extension.
    Without a confirmed brand/model, qualify examples with their parent names
    so a Toyota variant is not presented as a Perodua option.
    """
    goal = goal or state.goal
    profile = identity_frame(state, goal)
    before = IDENTITY_ORDER[:IDENTITY_ORDER.index(field)]
    pool = [car for car in cars if all(getattr(profile, name) is None or
            normal(getattr(car, name)) == normal(getattr(profile, name)) for name in before)]
    if format_fallback and not pool:
        # Broaden only the DISPLAY examples. The original Frame and actual
        # matching/valuation constraints are never modified by this search.
        for depth in range(len(before) - 1, -1, -1):
            pool = [car for car in cars if all(getattr(profile, name) is None or
                    normal(getattr(car, name)) == normal(getattr(profile, name)) for name in before[:depth])]
            if pool:
                break
    pool.sort(key=lambda car: car.simulation is not None)
    result, seen = [], set()
    # Initially prefer different parent brands/models to avoid listing many
    # trims of one car when the user has not identified their vehicle yet.
    if field in ('model', 'variant') and (profile.brand is None or format_fallback or field == 'variant' and profile.model is None):
        distinct_parents = set()
        diversified = []
        for car in pool:
            parent = (normal(car.brand), normal(car.model)) if profile.brand is not None else normal(car.brand)
            if parent not in distinct_parents:
                diversified.append(car)
                distinct_parents.add(parent)
        pool = diversified + pool
    for car in pool:
        value = getattr(car, field)
        if value is None:
            continue
        parents = []
        if field == 'model' and (profile.brand is None or format_fallback):
            parents = [car.brand]
        if field == 'variant' and (profile.brand is None or profile.model is None or format_fallback):
            parents = [car.brand, car.model]
        text = str(value) + (' [' + ' '.join(parents) + ']' if parents else '')
        if normal(text) not in seen:
            seen.add(normal(text))
            result.append(text)
        if len(result) == 2:
            break
    return result


def catalogue_notice(state, cars, *, goal=None):
    """Explain absent coverage once, rather than hide every answer example."""
    goal = goal or state.goal
    if goal not in GOALS:
        return ''
    profile = identity_frame(state, goal)
    if profile.brand is None:
        return ''
    pool = [car for car in cars if normal(car.brand) == normal(profile.brand)]
    name = str(profile.brand)
    if profile.model:
        pool = [car for car in pool if normal(car.model) == normal(profile.model)]
        name += ' ' + str(profile.model)
    if not pool:
        return (name + ' is not in the saved vehicle catalogue. Examples from other saved vehicles are input guidance only; '
                'they are not specifications or price evidence for your vehicle.')
    if profile.variant and not any(normal(car.variant) == normal(profile.variant) for car in pool):
        return (name + ' variant ' + str(profile.variant) + ' has no exact saved record. Other-vehicle examples are labelled as format guidance; '
                'keep your actual vehicle details.')
    return ''


def infer_field(slot, question):
    """Tool-validation questions may have a temporary slot; inspect their words."""
    leaf = slot.rsplit('.', 1)[-1]
    if not leaf.startswith(('tool_question_', 'conflict_')):
        return leaf
    patterns = [('variant', r'\bvariant\b'), ('year', r'\b(year|manufactur\w*)\b'),
                ('brand', r'\bbrand\b'), ('model', r'\bmodel\b'),
                ('transmission', r'\b(transmission|D-CVT|automatic|manual)\b'),
                ('mileage_km', r'\b(odometer|mileage|distance unit)\b'),
                ('fees_confirmed_complete', r'\bcomplete\b.*\bfees?\b|\bfees?\b.*\bcomplete\b'),
                ('loan_settlement_myr', r'\b(loan|settlement|debt)\b'),
                ('seller_minimum_net_myr', r'\b(net proceeds|minimum net)\b'),
                ('buyer_total_budget_myr', r'\bbudget\b'), ('fees_myr', r'\bfees?\b'),
                ('current_offer_myr', r'\b(price|offer|bid|quote)\b'),
                ('condition', r'\bcondition\b')]
    return next((field for field, pattern in patterns if re.search(pattern, question, re.I)), leaf)


def example_for(slot, state, cars, *, question='', goal=None):
    """Return answer guidance, without choosing an answer for the user."""
    goal = goal or state.goal
    if goal not in GOALS:
        return ''
    field = infer_field(slot, question)
    if field in IDENTITY_ORDER:
        choices = catalogue_choices(field, state, cars, goal=goal)
        if choices:
            return 'e.g. ' + ', '.join(choices)
        other_choices = catalogue_choices(field, state, cars, goal=goal, format_fallback=True)
        if other_choices:
            scope = 'from other saved models' if field in ('brand', 'model', 'variant') else 'from saved vehicles'
            return 'e.g. ' + ', '.join(other_choices) + '; format examples ' + scope + ', enter your actual vehicle value'
        return 'e.g. "Unknown" if unavailable; otherwise copy the requested value from your vehicle documents'
    examples = {
        'mileage_km': 'e.g. 65000 km; format only, enter the actual odometer reading',
        'condition': 'e.g. good, fair or poor; use your own assessment',
        'major_accident_reported': 'e.g. "No major accident", "A major accident was reported", or "Unknown"',
        'flood_damage_reported': 'e.g. "No flood damage", "Flood damage was reported", or "Unknown"',
        'role': 'e.g. "I am the buyer" or "I am the seller"',
        'fees_confirmed_complete': 'e.g. "All fees are complete" or "Fees are still unknown"',
        'fees_myr': 'e.g. RM1000; format only, enter your confirmed full fee total',
        'loan_settlement_myr': 'e.g. RM10000, or RM0 only if confirmed debt-free; format examples',
        'buyer_total_budget_myr': 'e.g. RM60000 including fees; format only, enter your own total limit',
        'seller_minimum_net_myr': 'e.g. "I need RM35000 left after fees and loan settlement"; format only',
        'available_cash_myr': 'e.g. RM50000 available to top up; format only, enter your own cash limit',
        'estimated_completion_days': 'e.g. 7 days; enter your own estimate',
        'estimated_effort_hours': 'e.g. 2 hours; enter your own estimate',
        'priority': 'e.g. net_cost for lowest top-up, speed for fastest completion, or effort for least work',
    }
    if field in examples:
        return examples[field]
    if field in ('price_myr', 'current_offer_myr', 'asking_price_myr'):
        if 'trade_in_replacement' in slot:
            meaning = 'replacement-car price when trading in'
        elif 'private_sale_replacement' in slot:
            meaning = 'replacement-car price after a private sale'
        elif 'trade_in_quote' in slot:
            meaning = 'dealer offer for your old car, before fees and loan settlement'
        elif 'private_sale_quote' in slot:
            meaning = 'old-car private-sale quote, before fees and loan settlement'
        elif field == 'current_offer_myr':
            meaning = 'other party vehicle quote, excluding fees'
        else:
            meaning = 'stated vehicle asking price, excluding fees'
        return f'e.g. RM45000 as the {meaning}; format only, use your actual quote'
    return 'e.g. "Unknown" if you cannot confirm the requested detail'


def form_guidance(field, state, cars, *, goal):
    """Return visible guidance and a placeholder that the form actually accepts.

    Chat odometers need units, but form odometers take digits + a unit dropdown.
    Money fields already specify MYR, so do not show an RM-prefixed input that
    their numeric parser would reject. No example is a widget default value.
    """
    guidance = example_for(field.path, state, cars, goal=goal)
    if not guidance:
        return '', 'e.g. 60000, 60k or 1 million' if field.kind == 'money' else ''
    if field.kind == 'distance':
        return 'e.g. 65000 with km selected below; enter digits only, choose the odometer unit, and use your actual reading', 'e.g. 65000'
    if field.kind == 'money':
        plain = re.sub(r'\bRM(?=\d)', '', guidance)
        number = re.search(r'\d+', plain)
        return plain + '. This field is MYR; omit the currency symbol.', 'e.g. ' + (number.group() if number else '1000')
    if field.path.endswith('estimated_completion_days'):
        return 'e.g. 7; enter a number of days only, using your own estimate', 'e.g. 7'
    if field.path.endswith('estimated_effort_hours'):
        return 'e.g. 2; enter a number of hours only, using your own estimate', 'e.g. 2'
    if field.kind == 'integer':
        match = re.search(r'\b\d{4}\b', guidance)
        return guidance, 'e.g. ' + match.group() if match else ''
    return guidance, guidance if field.kind == 'text' else ''


def guided_question(question, slot, state, cars):
    if state.goal not in GOALS:
        return question
    # Some tool messages already contain a small example. Add the catalogue
    # suffix once, without accumulating it across inspect/ask/rerender calls.
    example = example_for(slot, state, cars, question=question)
    suffix = ' (' + example + ')'
    return question if question.endswith(suffix) else question + suffix


def guided_questions(pending, state, cars):
    questions = list(dict.fromkeys(guided_question(q, slot, state, cars) for slot, q in pending.items()))[:3]
    notice = catalogue_notice(state, cars)
    return ([notice] + questions) if notice and questions else questions
