"""Vehicle knowledge representation: inherited slots, ranges, and provenance."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class VehicleFrame(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    vehicle_id: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year: int = Field(ge=1900)
    currency: Literal['MYR'] = 'MYR'
    price_myr: float | None = Field(default=None, gt=0)
    seats: int | None = Field(default=None, ge=1, le=20)
    source_kind: Literal['synthetic_demo', 'listing', 'transaction']
    source_reference: str = Field(min_length=1)
    observed_on: date
    variant: str | None = None
    transmission: str | None = None
    price_type: Literal['asking', 'transaction', 'illustrative'] | None = None
    availability: Literal['listed_snapshot', 'sold', 'reserved', 'unknown'] = 'unknown'
    source_updated_on: date | None = None
    mileage_km: int | None = Field(default=None, ge=0)
    mileage_min_km: int | None = Field(default=None, ge=0)
    mileage_max_km: int | None = Field(default=None, ge=0)
    condition: str | None = None
    fuel_km_per_l: float | None = Field(default=None, gt=0, le=100)
    fuel_basis: Literal['eco_driving_claim', 'MDC_claim', 'synthetic_demo'] | None = None
    fuel_source_reference: str | None = None
    boot_litres: float | None = Field(default=None, ge=0, le=5000)
    boot_configuration: Literal['all_seats_up', 'third_row_folded'] | None = None
    length_mm: int | None = Field(default=None, ge=2000, le=8000)
    specs_source_reference: str | None = None
    evidence_notes: list[str] = Field(default_factory=list)

    @field_validator('vehicle_id', 'brand', 'model', 'source_reference')
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Text slots cannot contain only whitespace.')
        return value

    @model_validator(mode='after')
    def check_dates(self):
        if self.year > self.observed_on.year:
            raise ValueError('Vehicle year is inconsistent with the observation date.')
        if self.source_updated_on and self.source_updated_on > self.observed_on:
            raise ValueError('Source update date cannot be after the observation date.')
        if self.mileage_min_km is not None and self.mileage_max_km is not None and self.mileage_min_km > self.mileage_max_km:
            raise ValueError('Mileage lower bound cannot exceed the upper bound.')
        if self.mileage_km is not None and ((self.mileage_min_km is not None and self.mileage_km < self.mileage_min_km) or (self.mileage_max_km is not None and self.mileage_km > self.mileage_max_km)):
            raise ValueError('Exact mileage must agree with any supplied mileage bounds.')
        if self.source_kind != 'synthetic_demo':
            if not self.variant or not self.variant.strip():
                raise ValueError('Real records require a stated variant.')
            if self.price_type != ('asking' if self.source_kind == 'listing' else 'transaction'):
                raise ValueError('Price type must agree with the source kind; sold listings remain asking prices.')
            from urllib.parse import urlsplit
            parsed = urlsplit(self.source_reference)
            if parsed.scheme != 'https' or not parsed.netloc:
                raise ValueError('Real records require an HTTPS source URL.')
            if self.fuel_km_per_l is not None and self.fuel_basis == 'synthetic_demo':
                raise ValueError('Real records cannot use a synthetic fuel claim basis.')
            for reference, used in [(self.fuel_source_reference, self.fuel_km_per_l is not None), (self.specs_source_reference, self.length_mm is not None or self.boot_litres is not None)]:
                parsed = urlsplit(reference or '')
                if used and (parsed.scheme != 'https' or not parsed.netloc):
                    raise ValueError('Real fuel and size features require HTTPS source references.')
        if self.fuel_km_per_l is not None and (not self.fuel_basis or not self.fuel_source_reference):
            raise ValueError('Fuel values require a test/claim basis and source.')
        if (self.length_mm is not None or self.boot_litres is not None) and not self.specs_source_reference:
            raise ValueError('Size features require a specification source.')
        if self.boot_litres is not None and not self.boot_configuration:
            raise ValueError('Boot volume requires a seat configuration.')
        return self


class PassengerCarFrame(VehicleFrame):
    # Class frame: passenger cars inherit common vehicle slots and this default.
    vehicle_category: Literal['passenger_car'] = 'passenger_car'
    wheels: Literal[4] = 4


def load_vehicles(path) -> list[PassengerCarFrame]:
    from pathlib import Path
    vehicles = TypeAdapter(list[PassengerCarFrame]).validate_json(Path(path).read_text(encoding='utf-8'))
    ids = [v.vehicle_id for v in vehicles]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate vehicle IDs found. Each record must have a unique ID.')
    return vehicles
