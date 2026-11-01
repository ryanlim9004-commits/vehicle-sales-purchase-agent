"""Explicit MYR quotes and limits for deterministic consultation tools."""
# Learning guide:
# Separate negotiation limits from replacement and disposal quote amounts.
# Money slots use MYR; unknown amounts remain None rather than becoming zero.
# Strict frames reject extra fields and misleading coercions before calculations.
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Shared strict configuration and cents-precision validation for consultation money fields.
class MoneyFrame(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

    # Check monetary fields can be represented with at most two decimal places; do not silently
    # round user input.
    @field_validator('*')
    @classmethod
    def currency_precision(cls, value, info):
        if info.field_name.endswith('_myr') and value is not None:
            number = Decimal(str(value))
            try:
                rounded = number.quantize(Decimal('0.01'))
            except ArithmeticError as error:
                raise ValueError('MYR amount is outside the supported numeric precision.') from error
            if number != rounded:
                raise ValueError('MYR amounts must use at most two decimal places.')
        return value


# Five identity slots link a reference to a specific variant/year/transmission, without
# requiring personal condition facts.
class VehicleIdentityFrame(MoneyFrame):
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    transmission: Literal['Automatic', 'Manual', 'D-CVT'] | None = None

    # Treat blank identity text as unknown, preserving a missing-field question.
    @field_validator('brand', 'model', 'variant')
    @classmethod
    def strip_identity(cls, value):
        return value.strip() or None if value is not None else None


# Keep the other party offer, separate fees, buyer total cap and seller net reserve in
# explicitly named slots.
class NegotiationFrame(MoneyFrame):
    currency: Literal['MYR'] = 'MYR'
    role: Literal['buyer', 'seller'] | None = None
    vehicle: VehicleIdentityFrame = Field(default_factory=VehicleIdentityFrame)
    # Optional for exact-ad context; needed for a historical Ridge fallback.
    mileage_km: float | None = Field(default=None, ge=0, le=2000000)
    asking_price_myr: float | None = Field(default=None, gt=0)
    # Latest price proposed by the OTHER party: seller's quote for a buyer,
    # buyer's bid for a seller. Fees are separate from the vehicle price.
    current_offer_myr: float | None = Field(default=None, gt=0)
    fees_myr: float | None = Field(default=None, ge=0)
    fees_confirmed_complete: bool | None = None
    # These limits use different bases: buyer is a total cash ceiling;
    # seller is the minimum money left AFTER fees and old-loan settlement.
    buyer_total_budget_myr: float | None = Field(default=None, gt=0)
    seller_minimum_net_myr: float | None = Field(default=None, ge=0)
    loan_settlement_myr: float | None = Field(default=None, ge=0)
    clarification_notes: list[str] = Field(default_factory=list)


# Describe the replacement purchase price and its separately confirmed complete fee total.
class ReplacementQuoteFrame(MoneyFrame):
    price_myr: float | None = Field(default=None, gt=0)
    fees_myr: float | None = Field(default=None, ge=0)
    fees_confirmed_complete: bool | None = None


# Reuse quote fields for a gross disposal offer; add optional user-estimated completion days and
# effort hours.
class DisposalQuoteFrame(ReplacementQuoteFrame):
    # price_myr is the gross trade-in offer / private-sale proceeds, not net cash.
    estimated_completion_days: float | None = Field(default=None, ge=0)
    estimated_effort_hours: float | None = Field(default=None, ge=0)


# Keep four independent quotes, old-loan settlement, cash limit and priority; never assume the
# two packages match.
class TradeInFrame(MoneyFrame):
    currency: Literal['MYR'] = 'MYR'
    # current_vehicle is the old vehicle. The four quote objects below refer
    # to two purchase packages and two disposal alternatives, not four cars.
    current_vehicle: VehicleIdentityFrame = Field(default_factory=VehicleIdentityFrame)
    mileage_km: float | None = Field(default=None, ge=0, le=2000000)
    trade_in_replacement: ReplacementQuoteFrame = Field(default_factory=ReplacementQuoteFrame)
    private_sale_replacement: ReplacementQuoteFrame = Field(default_factory=ReplacementQuoteFrame)
    trade_in_quote: DisposalQuoteFrame = Field(default_factory=DisposalQuoteFrame)
    private_sale_quote: DisposalQuoteFrame = Field(default_factory=DisposalQuoteFrame)
    loan_settlement_myr: float | None = Field(default=None, ge=0)
    available_cash_myr: float | None = Field(default=None, ge=0)
    priority: Literal['net_cost', 'speed', 'effort'] | None = None
    clarification_notes: list[str] = Field(default_factory=list)
