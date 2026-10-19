"""Small, explicit zero-order Sugeno fuzzy system for supported vehicle features.

Memberships and rule consequences are design choices, not learned market facts.
No LLM participates in the numerical calculation. See V2_GUIDE_ZH.md.
"""
from math import isfinite

POLICY_VERSION = 'sugeno-lifestyle-v2.0'
LEVELS = {'low': 0.0, 'medium': 0.5, 'high': 1.0}


# Shoulder/triangle sets cover the whole normalized domain, including endpoints.
def memberships(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError('A fuzzy input must be a finite number.')
    value = min(1.0, max(0.0, value))
    return {'low': max(0.0, 1 - 2 * value),
            'medium': max(0.0, 1 - abs(2 * value - 1)),
            'high': max(0.0, 2 * value - 1)}


# Evaluate up to nine rules: product AND, constant consequents and weighted mean.
# The minimum term rewards balanced suitability rather than double-counting it
# as a separate fuel/boot score later. Single-input policies have three rules.
def infer_lifestyle(*, fuel=None, luggage=None, fuel_weight=0.0, luggage_weight=0.0):
    weights = {'fuel': fuel_weight, 'luggage': luggage_weight}
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or not isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError('Fuzzy importance weights must be finite and nonnegative.')
    active = {name: weight for name, weight in weights.items() if weight > 0}
    values = {'fuel': fuel, 'luggage': luggage}
    result = {'policy_version': POLICY_VERSION, 'method': 'zero-order Sugeno',
              'and_operator': 'product', 'aggregation': 'sum(strength * consequent) / sum(strength)',
              'consequent_policy': '0.8 * preference-weighted level + 0.2 * minimum active level',
              'normalized_value': None, 'inputs': {k: values[k] for k in active},
              'importance': active, 'memberships': {}, 'rules': [],
              'numerator': None, 'denominator': None, 'unknown_reason': None}
    if not active:
        result['unknown_reason'] = 'No fuel or luggage preference activates this component.'
        return result
    if any(values[name] is None for name in active):
        result['unknown_reason'] = 'An active fuzzy input is unknown; no medium value is imputed.'
        return result
    sets = {name: memberships(values[name]) for name in active}
    result['memberships'] = sets
    # Build the complete rule table, including zero-strength rules for inspection.
    combinations = [({}, 1.0)]
    for name, terms in sets.items():
        combinations = [(dict(terms_so_far, **{name: term}), strength * degree)
                        for terms_so_far, strength in combinations for term, degree in terms.items()]
    numerator = denominator = 0.0
    for i, (terms, strength) in enumerate(combinations, 1):
        average = sum(active[name] * LEVELS[term] for name, term in terms.items()) / sum(active.values())
        consequence = 0.8 * average + 0.2 * min(LEVELS[term] for term in terms.values())
        numerator += strength * consequence
        denominator += strength
        result['rules'].append({'rule_id': f'FUZ_{i:02d}', 'if': terms, 'strength': strength,
                                'then_constant': consequence, 'contribution': strength * consequence})
    if denominator <= 0:
        raise ValueError('Fuzzy policy has no firing rule for supported inputs.')
    result.update(normalized_value=numerator / denominator, numerator=numerator, denominator=denominator)
    return result
