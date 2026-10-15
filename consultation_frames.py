"""Explicit MYR quotes and limits for deterministic consultation tools."""
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MoneyFrame(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

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


class VehicleIdentityFrame(MoneyFrame):
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    transmission: Literal['Automatic', 'Manual', 'D-CVT'] | None = None

    @field_validator('brand', 'model', 'variant')
    @classmethod
    def strip_identity(cls, value):
        return value.strip() or None if value is not None else None


class NegotiationFrame(MoneyFrame):
    currency: Literal['MYR'] = 'MYR'
    role: Literal['buyer', 'seller'] | None = None
    vehicle: VehicleIdentityFrame = Field(default_factory=VehicleIdentityFrame)
    asking_price_myr: float | None = Field(default=None, gt=0)
    # Latest price proposed by the OTHER party: seller's quote for a buyer,
    # buyer's bid for a seller. Fees are separate from the vehicle price.
    current_offer_myr: float | None = Field(default=None, gt=0)
    fees_myr: float | None = Field(default=None, ge=0)
    fees_confirmed_complete: bool | None = None
    buyer_total_budget_myr: float | None = Field(default=None, gt=0)
    seller_minimum_net_myr: float | None = Field(default=None, ge=0)
    loan_settlement_myr: float | None = Field(default=None, ge=0)
    clarification_notes: list[str] = Field(default_factory=list)


class ReplacementQuoteFrame(MoneyFrame):
    price_myr: float | None = Field(default=None, gt=0)
    fees_myr: float | None = Field(default=None, ge=0)
    fees_confirmed_complete: bool | None = None


class DisposalQuoteFrame(ReplacementQuoteFrame):
    # price_myr is the gross trade-in offer / private-sale proceeds, not net cash.
    estimated_completion_days: float | None = Field(default=None, ge=0)
    estimated_effort_hours: float | None = Field(default=None, ge=0)


class TradeInFrame(MoneyFrame):
    currency: Literal['MYR'] = 'MYR'
    current_vehicle: VehicleIdentityFrame = Field(default_factory=VehicleIdentityFrame)
    trade_in_replacement: ReplacementQuoteFrame = Field(default_factory=ReplacementQuoteFrame)
    private_sale_replacement: ReplacementQuoteFrame = Field(default_factory=ReplacementQuoteFrame)
    trade_in_quote: DisposalQuoteFrame = Field(default_factory=DisposalQuoteFrame)
    private_sale_quote: DisposalQuoteFrame = Field(default_factory=DisposalQuoteFrame)
    loan_settlement_myr: float | None = Field(default=None, ge=0)
    available_cash_myr: float | None = Field(default=None, ge=0)
    priority: Literal['net_cost', 'speed', 'effort'] | None = None
    clarification_notes: list[str] = Field(default_factory=list)
