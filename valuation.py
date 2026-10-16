"""Traceable rule-based listing reference, plus opt-in educational scenarios."""
# Learning guide:
# Calculate a reproducible asking-price reference from comparable listings.
# Default mode uses an unadjusted median and observed range, not a learned model.
# Optional mileage/condition factors are uncalibrated teaching assumptions.
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from pydantic import BaseModel, ConfigDict, Field
from seller_profile import SellerVehicleFrame
from vehicle_frame import PassengerCarFrame


# Expose reproducible sample/freshness rules and optional teaching factors; these defaults are
# not learned coefficients.
class ValuationPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    version: str = 'valuation-v1-educational'
    minimum_comparables: int = Field(default=3, ge=3)
    maximum_source_age_days: int = Field(default=90, ge=0)
    mileage_rate_per_10000_km: float = Field(default=0.01, ge=0, le=0.05)
    maximum_mileage_adjustment: float = Field(default=0.10, ge=0, le=0.25)
    good_factor: float = Field(default=1.0, gt=0, le=1)
    fair_factor: float = Field(default=0.95, gt=0, le=1)
    poor_factor: float = Field(default=0.85, gt=0, le=1)


# Round to MYR cents with Decimal and ROUND_HALF_UP; return a JSON-compatible number.
def money(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


# Normalize identity text for exact case/whitespace-insensitive comparisons, without fuzzy model
# merging.
def key(text):
    return ' '.join((text or '').casefold().split())


# Require supported seller facts, select recent exact-identity ads, and return a reference or an
# explicit refusal state.
def estimate_vehicle_value(seller: SellerVehicleFrame, vehicles: list[PassengerCarFrame], *, as_of: date, illustrative_adjustments=False, policy=None, identity_reference_only=False):
    policy = policy or ValuationPolicy()
    result = {'status':'needs_clarification', 'seller_profile':seller.model_dump(), 'as_of':as_of.isoformat(),
              'policy':policy.model_dump(), 'comparables':[], 'excluded_records':[], 'fired_rules':[],
              'clarification_questions':list(seller.clarification_notes), 'reference':None, 'adjusted_scenario':None,
              'limitations':['Listing asking-price reference, not a confirmed transaction price, guaranteed sale price or professional appraisal.',
                             'References are advertisement snapshots; distinct IDs do not prove VIN-distinct cars.',
                             'Independent comparable condition labels and calibrated adjustment coefficients are unavailable.',
                             'Price ranges are observed/assumption-based ranges, not statistical confidence intervals.']}
    trace = result['fired_rules']
    if seller.major_accident_reported is True or seller.flood_damage_reported is True:
        # Damage is a stop/inspection rule, not a made-up percentage penalty.
        result['status'] = 'inspection_required'
        trace.append({'rule_id':'VAL_DAMAGE','reason':'Major accident or flood damage reported; generic price estimation is withheld.'})
        result['clarification_questions'].append('Obtain an independent inspection before relying on a valuation.')
        return result
    required = {'brand':'What is the vehicle brand?', 'model':'What is the vehicle model?', 'variant':'What is the exact variant, for example 1.5 SE?',
                'year':'What is the manufacturing year?', 'transmission':'Is the transmission Automatic, Manual or D-CVT?',
                'mileage_km':'What is the mileage in kilometres?', 'condition':'Is the reported condition good, fair or poor?'}
    if identity_reference_only and not illustrative_adjustments:
        # Negotiation/Trade-In can ask for background prices using identity
        # alone. Personal mileage/condition is not needed for an unadjusted
        # identity-group median, so these facts must not be invented.
        required.pop('mileage_km')
        required.pop('condition')
        result['reference_scope'] = 'Identity-only unadjusted asking-price reference; no seller mileage or condition is inferred.'
    for slot, question in required.items():
        if getattr(seller, slot) is None or (slot == 'condition' and seller.condition == 'unknown'):
            result['clarification_questions'].append(question)
    if seller.year and seller.year > as_of.year:
        result['clarification_questions'].append('The manufacturing year is beyond this valuation date; please clarify.')
    if result['clarification_questions']:
        trace.append({'rule_id':'VAL_REQUIRED','reason':'Required or conflicting seller facts must be clarified before calculation.'})
        return result
    seen_ids, seen_sources = set(), set()
    # Exact comparability deliberately avoids mixing variants or applying a
    # second unsupported age-depreciation deduction to same-year used prices.
    for v in vehicles:
        reasons = []
        if v.vehicle_id in seen_ids or v.source_reference in seen_sources:
            reasons.append('Duplicate ID/source; not counted twice.')
        seen_ids.add(v.vehicle_id)
        seen_sources.add(v.source_reference)
        if v.source_kind != 'listing' or v.price_type != 'asking':
            reasons.append('Not a real-source asking-price listing; evidence types are not pooled.')
        if v.availability != 'listed_snapshot':
            reasons.append('Not an eligible listed snapshot (sold, reserved or unknown).')
        for name in ('brand','model','variant','transmission'):
            if key(getattr(v, name)) != key(getattr(seller, name)):
                reasons.append(f'{name} does not exactly match.')
        if v.year != seller.year:
            reasons.append('Manufacturing year differs; no unsupported depreciation adjustment is applied.')
        if v.price_myr is None:
            reasons.append('Asking price is unknown.')
        if v.observed_on > as_of:
            reasons.append('Observation is after the valuation date.')
        if v.source_updated_on is None:
            reasons.append('Source update date is unknown; freshness cannot be checked for valuation.')
        elif v.source_updated_on > as_of or (as_of-v.source_updated_on).days > policy.maximum_source_age_days:
            reasons.append('Source update is outside the permitted valuation window.')
        if reasons:
            result['excluded_records'].append({'vehicle_id':v.vehicle_id,'reasons':reasons})
        else:
            result['comparables'].append({'vehicle_id':v.vehicle_id,'asking_price_myr':v.price_myr,
                                         'source_reference':v.source_reference,'source_updated_on':v.source_updated_on.isoformat(),
                                         'mileage_km':v.mileage_km,'mileage_min_km':v.mileage_min_km,'mileage_max_km':v.mileage_max_km,
                                         'condition':v.condition})
    comps = result['comparables']
    trace.append({'rule_id':'VAL_COMPARABLES','reason':'Same brand/model/variant/year/transmission, eligible real listings, known recent source dates, unique source/ID.', 'accepted_count':len(comps)})
    if len(comps) < policy.minimum_comparables:
        # Three is a teaching-policy minimum, not a statistical guarantee.
        result['status'] = 'insufficient_evidence'
        result['message'] = f'Need at least {policy.minimum_comparables} comparable listings; found {len(comps)}. No price estimate is returned.'
        return result
    prices = [c['asking_price_myr'] for c in comps]
    # Median is the middle price (or mean of the two middle prices); min/max
    # describes the observed adverts, not a guaranteed sale or confidence band.
    base = median(prices)
    result['reference'] = {'price_basis':'asking', 'comparable_count':len(comps), 'median_asking_price_myr':money(base),
                           'observed_asking_range_myr':[money(min(prices)),money(max(prices))],
                           'personalized_for_mileage_or_condition':False}
    result['status'] = 'reference_only'
    trace.append({'rule_id':'VAL_MEDIAN','reason':'Median asking price and observed min/max are calculated from the selected listings; no second age-depreciation deduction.', 'median_myr':money(base)})
    if (max(prices)-min(prices))/base > 0.20:
        result['limitations'].append('Comparable price spread exceeds 20% of the median; investigate differences rather than treating the median as precise.')
    if seller.major_accident_reported is None or seller.flood_damage_reported is None:
        result['limitations'].append('Damage history is unknown; good/fair/poor is self-reported and does not establish accident/flood history.')
    if not illustrative_adjustments:
        # This is the normal exit. Everything below is an explicit opt-in
        # educational scenario with uncalibrated mileage/condition assumptions.
        trace.append({'rule_id':'VAL_NO_CALIBRATION','reason':'No verified market mileage/condition factors. Default mode returns the unadjusted listing reference only.'})
        return result
    intervals = []
    for c in comps:
        if c['mileage_km'] is not None:
            intervals.append((c['mileage_km'],c['mileage_km']))
        elif c['mileage_min_km'] is not None and c['mileage_max_km'] is not None:
            intervals.append((c['mileage_min_km'],c['mileage_max_km']))
    if len(intervals) != len(comps):
        result['limitations'].append('Illustrative adjustment withheld: some comparable mileages are unknown.')
        return result
    if not min(a for a,b in intervals) <= seller.mileage_km <= max(b for a,b in intervals):
        result['limitations'].append('Illustrative adjustment withheld: seller mileage is outside the observed envelope; extrapolation is not supported.')
        return result
    lo, hi = median(a for a,b in intervals), median(b for a,b in intervals)
    # Retain the two ends of the reference-mileage interval rather than claim
    # that every advertised range supplied an exact odometer reading.
    # For the optional scenario, convert a reference-mileage difference to a capped multiplier
    # around 1.
    def factor(reference):
        delta = (reference-seller.mileage_km)/10000 * policy.mileage_rate_per_10000_km
        return 1 + max(-policy.maximum_mileage_adjustment,min(policy.maximum_mileage_adjustment,delta))
    factors = [factor(lo),factor(hi)]
    condition_factor = getattr(policy, f'{seller.condition}_factor')
    # Midpoint is an explicit scenario assumption, not an observed mileage.
    center = base * sum(factors)/2 * condition_factor
    result['adjusted_scenario'] = {'label':'ILLUSTRATIVE_UNCALIBRATED_SCENARIO', 'market_validated':False,
                                  'reference_mileage_interval_km':[lo,hi], 'mileage_factor_interval':factors,
                                  'self_reported_condition':seller.condition, 'condition_factor':condition_factor,
                                  'scenario_midpoint_myr':money(center),
                                  'scenario_range_myr':[money(min(prices)*min(factors)*condition_factor),money(max(prices)*max(factors)*condition_factor)],
                                  'formula':'median asking price * midpoint of mileage factor interval * assumed condition factor',
                                  'assumptions':'Mileage rate/cap and condition factors are teaching parameters, not learned or verified market adjustments.'}
    result['status'] = 'illustrative_scenario'
    trace.append({'rule_id':'VAL_ILLUSTRATIVE','reason':'User enabled the educational scenario. Mileage ranges retained; midpoint used only for this explicit scenario.'})
    return result
