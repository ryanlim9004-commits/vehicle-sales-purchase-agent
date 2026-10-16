"""Transparent heuristic ranking after hard filtering; no learned model."""
# Learning guide:
# Rank only vehicles that already passed matching.filter_vehicles.
# Compute score = sum(100 * normalized weight * supported feature value).
# Weights and anchors are hand-authored heuristics; missing data is disclosed.
from copy import deepcopy
from buyer_profile import BuyerProfileFrame


# Bound a feature to [0, 1] so an extreme raw value cannot exceed its allocated score weight.
def clip(value):
    return max(0.0, min(1.0, value))


# Copy the filtered result, normalize shared weights, score supported features and apply
# deterministic tie-breakers.
def rank_vehicles(profile: BuyerProfileFrame, filtered: dict) -> dict:
    result = deepcopy(filtered)
    result['matching_method'] = 'Hard filtering followed by conservative weighted heuristic scoring v1.'
    result['scoring_notes'] = [
        'Weights and anchors are design assumptions, not learned coefficients or market facts.',
        'Unknown components contribute zero to the lower bound, not a claim of poor vehicle quality.',
        'Fuel values are manufacturer claims, not measured used-car or city-driving consumption.',
        'Boot volume is a luggage proxy, not passenger legroom or an overall space rating.',
    ]
    if 'long_distance' in profile.usage:
        result['scoring_notes'].append('No independently verified long-distance comfort, reliability or safety rating is scored; only the explicitly supported criteria contribute.')
    # First select raw importance weights from the user's stated preferences.
    # These are public design choices; changing them changes the ranking policy.
    weights = {'budget': 1.0, 'fuel': {None: 0.0, 'low': 0.5, 'medium': 2.0, 'high': 4.0}[profile.fuel_priority],
               'luggage': {None: (2.0 if 'family_travel' in profile.usage else 0.0), 'low': 0.5, 'medium': 2.0, 'high': 3.0}[profile.space_priority],
               'brand': 2.0 if profile.preferred_brands else 0.0,
               'city_compactness': 1.0 if 'city_commute' in profile.usage else 0.0}
    rows = result['matches']
    bases = {row['vehicle']['fuel_basis'] for row in rows if row['vehicle']['fuel_km_per_l'] is not None}
    # Disable an unsupported fuel comparison for the whole candidate set,
    # rather than comparing numbers obtained under different claim conditions.
    if weights['fuel'] and len(bases) > 1:
        weights['fuel'] = 0.0
        result['scoring_notes'].append('Fuel scoring disabled for this candidate set: incompatible claim/test bases. No cross-cycle fuel comparison is made.')
    elif weights['fuel'] and not bases:
        weights['fuel'] = 0.0
        result['scoring_notes'].append('Fuel scoring unavailable for all eligible candidates; no fuel-economy recommendation can be supported.')
    total = sum(weights.values())
    # Normalize once for all cars: weight_i = raw_i / sum(raw_weights).
    # Example: fuel 4 / total 9 = 0.4444; a 0.8 feature earns 35.5556 points.
    weights = {k: v / total for k, v in weights.items() if v > 0}
    result['scoring_weights'] = weights
    result['scoring_anchors'] = {'budget': '1 - asking_price / buyer_budget', 'fuel': 'clip((km_per_l - 10) / 15, 0, 1); same claim basis only',
                                 'luggage': 'clip(boot_litres / 600, 0, 1); all seats up only',
                                 'brand': '1 for a preferred brand, otherwise 0', 'city_compactness': 'clip((5000 - length_mm) / 1500, 0, 1)'}
    for row in rows:
        v = row['vehicle']
        # Put different units on a common [0, 1] scale using fixed anchors.
        # Larger fuel/boot values help; lower price/length helps these proxies.
        values = {'budget': clip(1 - v['price_myr'] / profile.budget_myr),
                  'fuel': clip((v['fuel_km_per_l'] - 10) / 15) if v['fuel_km_per_l'] is not None else None,
                  'luggage': clip(v['boot_litres'] / 600) if v['boot_litres'] is not None and v['boot_configuration'] == 'all_seats_up' else None,
                  'brand': float(row['preferred_brand_match']),
                  'city_compactness': clip((5000 - v['length_mm']) / 1500) if v['length_mm'] is not None else None}
        components = {name: {'normalized_value': values[name], 'weight': weight,
                             'weighted_points': 100 * weight * (values[name] if values[name] is not None else 0),
                             'source_reference': (v['fuel_source_reference'] if name == 'fuel' else v['specs_source_reference'] if name in ('luggage', 'city_compactness') else v['source_reference'])}
                      for name, weight in weights.items()}
        # Missing data contributes zero supported points, not proof of poor
        # quality. Do not redistribute that missing weight to this car's known
        # features: that would reward incomplete records.
        coverage = sum(weight for name, weight in weights.items() if values[name] is not None)
        score = sum(c['weighted_points'] for c in components.values())
        row['score_breakdown'] = components
        row['score'] = round(score, 3)
        row['score_upper_bound'] = round(score + 100 * (1 - coverage), 3)
        row['weighted_data_coverage_percent'] = round(100 * coverage, 3)
        row['missing_scoring_features'] = [name for name in weights if values[name] is None]
        row['ranking_explanation'] = 'Sorted by evidence-supported lower-bound score; the upper bound reflects unknown components, not statistical confidence.'
    # Negative keys sort higher scores/coverage first. Price and ID settle ties
    # deterministically; the upper bound is not a statistical confidence range.
    rows.sort(key=lambda row: (-row['score'], -row['weighted_data_coverage_percent'], row['vehicle']['price_myr'], row['vehicle']['vehicle_id']))
    for i, row in enumerate(rows, 1):
        row['rank'] = i
    result['top_vehicle_ids'] = [r['vehicle']['vehicle_id'] for r in rows[:3]]
    return result
