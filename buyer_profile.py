"""Stage 1: natural-language requirements -> validated facts -> derived facts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class BuyerProfileFrame(BaseModel):
    # Unknown slots stay None; defaults must not invent customer preferences.
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    budget_myr: float | None = Field(default=None, gt=0)
    family_size: int | None = Field(default=None, ge=1, le=20)
    household_travels_together: bool | None = None
    required_seats: int | None = Field(default=None, ge=1, le=20)
    usage: list[Literal['city_commute', 'family_travel', 'long_distance']] = Field(default_factory=list)
    fuel_priority: Literal['high', 'medium', 'low'] | None = None
    space_priority: Literal['high', 'medium', 'low'] | None = None
    preferred_brands: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    clarification_notes: list[str] = Field(default_factory=list)
    input_validation_notes: list[str] = Field(default_factory=list)


def reason_about_profile(profile: BuyerProfileFrame) -> dict:
    """Two forward-chaining steps, with an explicit explanation trace."""
    facts = profile.model_dump()
    trace = []
    conflicts = list(profile.clarification_notes)
    if profile.family_size is not None:
        if profile.required_seats is None and profile.household_travels_together is not False:
            facts['required_seats'] = profile.family_size
            trace.append({'rule_id': 'BUY_01', 'reason': 'All stated household members are assumed to travel together; confirm if different.', 'derived_fact': {'required_seats': profile.family_size}})
        elif profile.required_seats is not None and profile.required_seats < profile.family_size and profile.household_travels_together is not False:
            conflicts.append('Your household size exceeds the requested seats. Will everyone travel together?')
        if profile.household_travels_together is False:
            trace.append({'rule_id': 'BUY_04', 'reason': 'The user explicitly stated that not all household members travel together; household size does not impose a seat minimum.', 'derived_fact': {'household_travels_together': False}})
    if facts['required_seats'] is not None:
        facts['minimum_vehicle_seats'] = facts['required_seats']
        trace.append({'rule_id': 'BUY_02', 'reason': 'Vehicle capacity must satisfy the passenger requirement.', 'derived_fact': {'minimum_vehicle_seats': facts['required_seats']}})
    if 'city_commute' in profile.usage and profile.fuel_priority == 'high':
        facts['lifestyle_profile'] = 'economical_city_commuter'
        trace.append({'rule_id': 'BUY_03', 'reason': 'City commuting plus a high fuel-economy preference activates the economical city profile.', 'derived_fact': {'lifestyle_profile': 'economical_city_commuter'}})
    overlap = {x.strip().casefold() for x in profile.preferred_brands} & {x.strip().casefold() for x in profile.excluded_brands}
    if overlap:
        conflicts.append('A brand is both preferred and excluded. Please clarify: ' + ', '.join(sorted(overlap)))
    missing = []
    questions = []
    for slot, question in [('budget_myr', 'What is your maximum total purchase budget in MYR?'), ('required_seats', 'How many seats do you need at minimum?')]:
        if facts[slot] is None:
            missing.append(slot)
            questions.append(question)
    if not profile.usage:
        missing.append('usage')
        questions.append('Will you mainly use the car for city commuting, family travel, or long-distance driving?')
    return {'extracted_profile': profile.model_dump(), 'derived_facts': facts, 'fired_rules': trace,
            'missing_slots': missing, 'clarification_questions': conflicts + questions,
            'ready_for_matching': not missing and not conflicts}
