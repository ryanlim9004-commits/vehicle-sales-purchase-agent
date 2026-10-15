"""Stage 2: deterministic hard-constraint filtering, not preference ranking."""
from buyer_profile import BuyerProfileFrame, reason_about_profile
from vehicle_frame import PassengerCarFrame


def normalize_brand(brand: str) -> str:
    return brand.strip().casefold()


def filter_vehicles(profile: BuyerProfileFrame, vehicles: list[PassengerCarFrame]) -> dict:
    reasoning = reason_about_profile(profile)
    result = {
        'status': 'needs_clarification',
        'buyer_reasoning': reasoning,
        'dataset_notice': ('Synthetic records are teaching fixtures, not real listings or market prices.' if any(v.source_kind == 'synthetic_demo' for v in vehicles) else 'Observed listing snapshots, not live inventory or confirmed transaction prices. Verify availability, fees and specifications with the source.'),
        'observed_on': sorted({v.observed_on.isoformat() for v in vehicles}),
        'matching_method': 'Hard constraints only; price/ID display order is not lifestyle ranking.',
        'constraints': {}, 'matches': [], 'rejected': [],
        'checked_count': 0, 'matched_count': 0,
    }
    if not reasoning['ready_for_matching']:
        return result
    facts = reasoning['derived_facts']
    excluded = {normalize_brand(b) for b in profile.excluded_brands}
    preferred = {normalize_brand(b) for b in profile.preferred_brands}
    budget, seats = facts['budget_myr'], facts['minimum_vehicle_seats']
    result['constraints'] = {'maximum_price_myr': budget, 'minimum_seats': seats, 'excluded_brands': sorted(excluded)}
    for vehicle in vehicles:
        rejected = []
        if vehicle.source_kind != 'synthetic_demo' and (vehicle.source_kind != 'listing' or vehicle.price_type != 'asking'):
            rejected.append({'rule_id': 'FILTER_PRICE_BASIS', 'reason': 'A transaction record is historical evidence, not an asking-price listing available for purchase.'})
        if vehicle.source_kind != 'synthetic_demo' and vehicle.availability != 'listed_snapshot':
            rejected.append({'rule_id': 'FILTER_AVAILABILITY', 'reason': f'Source availability is {vehicle.availability}; this record is not an eligible listing snapshot.'})
        if vehicle.price_myr is None:
            rejected.append({'rule_id': 'FILTER_PRICE_UNKNOWN', 'reason': 'Price is unknown; budget eligibility cannot be verified.'})
        elif vehicle.price_myr > budget:
            rejected.append({'rule_id': 'FILTER_BUDGET', 'reason': f'Price MYR {vehicle.price_myr:g} exceeds budget MYR {budget:g}.'})
        if vehicle.seats is None:
            rejected.append({'rule_id': 'FILTER_SEATS_UNKNOWN', 'reason': 'Seat capacity is unknown; passenger eligibility cannot be verified.'})
        elif vehicle.seats < seats:
            rejected.append({'rule_id': 'FILTER_SEATS', 'reason': f'{vehicle.seats} seats is below the required {seats}.'})
        if normalize_brand(vehicle.brand) in excluded:
            rejected.append({'rule_id': 'FILTER_EXCLUDED_BRAND', 'reason': f'{vehicle.brand} is an excluded brand.'})
        if rejected:
            result['rejected'].append({'vehicle_id': vehicle.vehicle_id, 'brand': vehicle.brand, 'model': vehicle.model, 'reasons': rejected})
        else:
            result['matches'].append({
                'vehicle': vehicle.model_dump(mode='json'),
                'preferred_brand_match': normalize_brand(vehicle.brand) in preferred,
                'passed_rules': ['FILTER_BUDGET', 'FILTER_SEATS', 'FILTER_EXCLUDED_BRAND'] + ([] if vehicle.source_kind == 'synthetic_demo' else ['FILTER_AVAILABILITY', 'FILTER_PRICE_BASIS']),
            })
    result['matches'].sort(key=lambda item: (item['vehicle']['price_myr'], item['vehicle']['vehicle_id']))
    result['checked_count'] = len(vehicles)
    result['matched_count'] = len(result['matches'])
    result['status'] = 'matches_found' if result['matches'] else 'no_matches'
    if not result['matches']:
        result['message'] = 'No vehicle satisfies all hard constraints. Review the rejection reasons; constraints have not been relaxed.'
    return result
