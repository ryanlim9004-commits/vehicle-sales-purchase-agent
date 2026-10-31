"""Readable vehicle information shared by chat and recommendation cards.

Internal record IDs and calculation traces stay in structured results/details.
This module formats known fields only; it never fills in missing specifications.
"""


def vehicle_title(vehicle):
    return ' '.join(str(value) for value in (vehicle['year'], vehicle['brand'], vehicle['model'], vehicle.get('variant')) if value)


def mileage_text(vehicle):
    exact = vehicle.get('mileage_km')
    if exact is not None:
        return f'{exact:,.0f} km'
    lower, upper = vehicle.get('mileage_min_km'), vehicle.get('mileage_max_km')
    if lower is not None and upper is not None:
        return f'{lower:,.0f}–{upper:,.0f} km'
    return None


def fuel_reference_text(vehicle):
    # Retain the supplied cycle so unit conversion never implies comparable tests.
    if vehicle.get('simulation'):
        spec = vehicle['simulation']
        return f"{spec['fuel_l_per_100km']:g} L/100 km ({spec['fuel_test_cycle'].replace('_', ' ')})"
    if vehicle.get('fuel_km_per_l') is not None:
        basis = (vehicle.get('fuel_basis') or '').replace('_', ' ')
        return f"{vehicle['fuel_km_per_l']:g} km/L ({basis})"
    return None


def vehicle_information_lines(vehicle):
    lines = [f"Reference price: MYR {vehicle['price_myr']:,.2f}"]
    capacity = [f"{vehicle['seats']} seats"] if vehicle.get('seats') is not None else []
    if vehicle.get('transmission'):
        capacity.append(vehicle['transmission'])
    if capacity:
        lines.append(' · '.join(capacity))
    mileage = mileage_text(vehicle)
    if mileage:
        lines.append('Mileage: ' + mileage)
    fuel = fuel_reference_text(vehicle)
    if fuel:
        lines.append('Fuel reference: ' + fuel)
    return lines
