"""Formal fuzzy matching plus scoped evidence, after existing hard constraints.

This is an explicit course policy, not a learned measure of customer relevance.
The v1 baseline remains in scoring.py for reproducible comparisons.
"""
from copy import deepcopy
from datetime import date
from fuzzy_lifestyle import infer_lifestyle, POLICY_VERSION
from scoring import clip
from vehicle_evidence import evidence_for_vehicle, load_catalogue
from vehicle_frame import fuel_comparison_basis


def component_sources(name, vehicle, evidence, fuel_weight, luggage_weight):
    # Keep numerical sources readable; a source is never invented by the LLM.
    if name == 'safety':
        report = evidence['safety']['report']
        return [report['source']['url']] if report else []
    if name in ('comfort', 'reliability'):
        return evidence[name]['sources']
    if name == 'fuzzy_lifestyle':
        sources = []
        if fuel_weight and vehicle['fuel_source_reference']:
            sources.append(vehicle['fuel_source_reference'])
        if luggage_weight and vehicle['specs_source_reference']:
            sources.append(vehicle['specs_source_reference'])
        return list(dict.fromkeys(sources))
    source = vehicle['specs_source_reference'] if name == 'city_compactness' else vehicle['source_reference']
    return [source] if source else []


def rank_vehicles_v2(profile, filtered, *, as_of=date(2026, 10, 15), catalogue=None):
    # One shared weight vector prevents missing records gaining extra weight.
    result = deepcopy(filtered)
    catalogue = catalogue or load_catalogue()
    fuel_weight = {None: 0, 'low': .5, 'medium': 2, 'high': 4}[profile.fuel_priority]
    luggage_weight = {None: (2 if 'family_travel' in profile.usage else 0), 'low': .5, 'medium': 2, 'high': 3}[profile.space_priority]
    notes = [
        'Memberships, anchors, rule consequents and weights are public design choices, not market-calibrated relevance.',
        'Fuzzy lifestyle replaces separate fuel/luggage points; these features are not counted twice.',
        'Unknown contributes no supported lower-bound points and widens the upper bound; this is not a quality judgement or statistical confidence interval.',
        'Fuel figures are compatible manufacturer claims, not observed city consumption. Luggage means boot volume with all seats up.',
        'Safety equipment is a reference, not crash probability. NCAP results retain their test protocol and are not averaged.',
        'Comfort and reliability coding is attributed opinion, not a failure rate. Exact year, variant and transmission applicability is required.',
    ]
    rows = result['matches']
    bases = {fuel_comparison_basis(r['vehicle']) for r in rows if r['vehicle']['fuel_km_per_l'] is not None}
    if fuel_weight and (len(bases) > 1 or None in bases):
        fuel_weight = 0
        notes.append('Fuel scoring disabled: incompatible claim/test bases; no cross-cycle comparison.')
    elif fuel_weight and not bases:
        fuel_weight = 0
        notes.append('No fuel-economy recommendation is supported: all eligible fuel features are unknown.')
    if result.get('simulation_record_count'):
        notes.append('Historical simulation candidates use assumed years/seats and unverified catalogue fuel references. Any compatible-cycle fuzzy comparison is a simulation only, not a real-world fuel-saving claim.')
    importance = {None: 0, 'low': .5, 'medium': 2, 'high': 3}
    raw = {'budget': 1, 'fuzzy_lifestyle': fuel_weight + luggage_weight,
           'brand': 2 if profile.preferred_brands else 0,
           'city_compactness': 1 if 'city_commute' in profile.usage else 0,
           'safety': importance[profile.safety_priority],
           'comfort': (2 if 'long_distance' in profile.usage else 0) if profile.comfort_priority is None else importance[profile.comfort_priority],
           'reliability': importance[profile.reliability_priority]}
    weights = {k: v / sum(raw.values()) for k, v in raw.items() if v > 0}
    result.update(ranking_policy=POLICY_VERSION, matching_method='Hard filtering, zero-order Sugeno fuzzy inference, then evidence-supported weighted scoring v2.',
                  scoring_notes=notes, scoring_weights=weights, raw_scoring_weights=raw,
                  evidence_as_of=as_of.isoformat(), evidence_reviewed_on=catalogue.reviewed_on.isoformat(),
                  scoring_anchors={'budget': 'clip(1 - asking_price / buyer_budget)',
                      'fuzzy_lifestyle': 'Fuel clip((km/L - 10)/15); boot clip(litres/600). Triangle/shoulder low/medium/high sets; product AND; 0.8 * weighted level + 0.2 * minimum level; weighted mean of rule constants.',
                      'brand': '1 for preferred brand; otherwise 0', 'city_compactness': 'clip((5000-length_mm)/1500)',
                      'safety': 'Confirmed true ESC/AEB/curtain-airbag items / 3; unknown increases bound.',
                      'comfort': 'Source-family means of negative=0, mixed=0.5, positive=1, divided by four aspects; two families and two aspects required.',
                      'reliability': 'At least two independent ownership-opinion families with ownership period; never failure probability.'})
    for row in rows:
        v = row['vehicle']
        fuel = clip((v['fuel_km_per_l'] - 10) / 15) if v['fuel_km_per_l'] is not None else None
        boot = clip(v['boot_litres'] / 600) if v['boot_litres'] is not None and v['boot_configuration'] == 'all_seats_up' else None
        fuzzy = infer_lifestyle(fuel=fuel, luggage=boot, fuel_weight=fuel_weight, luggage_weight=luggage_weight)
        evidence = evidence_for_vehicle(v, as_of=as_of, catalogue=catalogue)
        values = {'budget': clip(1 - v['price_myr'] / profile.budget_myr),
                  'fuzzy_lifestyle': fuzzy['normalized_value'], 'brand': float(row['preferred_brand_match']),
                  'city_compactness': clip((5000 - v['length_mm']) / 1500) if v['length_mm'] is not None else None,
                  **{name: evidence[name]['normalized_value'] for name in ('safety', 'comfort', 'reliability')}}
        components = {}
        for name, weight in weights.items():
            coverage = evidence[name]['data_coverage'] if name in ('safety', 'comfort', 'reliability') else float(values[name] is not None)
            sources = component_sources(name, v, evidence, fuel_weight, luggage_weight)
            components[name] = {'normalized_value': values[name], 'weight': weight, 'data_coverage': coverage,
                                'weighted_points': 100 * weight * (values[name] if values[name] is not None else 0),
                                'source_reference': sources}
        score = sum(c['weighted_points'] for c in components.values())
        coverage = sum(c['weight'] * c['data_coverage'] for c in components.values())
        row.update(score_breakdown=components, score=round(score, 3), score_upper_bound=round(score + 100 * (1 - coverage), 3),
                   weighted_data_coverage_percent=round(100 * coverage, 3),
                   missing_scoring_features=[name for name, c in components.items() if c['data_coverage'] < 1],
                   ranking_explanation='Evidence-supported lower bound, then coverage, asking price and ID. Upper bound covers unknown components, not statistical uncertainty.',
                   fuzzy_trace=fuzzy, vehicle_evidence=evidence)
    rows.sort(key=lambda r: (-r['score'], -r['weighted_data_coverage_percent'], r['vehicle']['price_myr'], r['vehicle']['vehicle_id']))
    for i, row in enumerate(rows, 1):
        row['rank'] = i
    result['top_vehicle_ids'] = [r['vehicle']['vehicle_id'] for r in rows[:3]]
    return result
