from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator

from src.modules.terms.models import TermStatus
from src.shared.schemas import BaseSchema


# --- Term Schemas ---

class TermCreate(BaseSchema):
    """Schema for creating a new term."""

    year: int
    term_number: int  # 1, 2, or 3
    display_name: str | None = None  # Auto-generated if not provided
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("term_number")
    @classmethod
    def validate_term_number(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("Term number must be 1, 2, or 3")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 2020 or v > 2100:
            raise ValueError("Year must be between 2020 and 2100")
        return v


class TermUpdate(BaseSchema):
    """Schema for updating a term."""

    display_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class PriceSettingResponse(BaseSchema):
    """Schema for price setting response."""

    id: int
    term_id: int
    grade: str
    school_fee_amount: Decimal


class TransportPricingResponse(BaseSchema):
    """Schema for transport pricing response."""

    id: int
    term_id: int
    zone_id: int
    zone_name: str
    zone_code: str
    transport_fee_amount: Decimal


class TermResponse(BaseSchema):
    """Schema for term response."""

    id: int
    year: int
    term_number: int
    display_name: str
    status: str
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime


class TermDetailResponse(TermResponse):
    """Schema for detailed term response with pricing."""

    price_settings: list[PriceSettingResponse]
    transport_pricings: list[TransportPricingResponse]


# --- Price Setting Schemas ---

class PriceSettingCreate(BaseSchema):
    """Schema for creating/updating a price setting."""

    grade: str
    school_fee_amount: Decimal

    @field_validator("school_fee_amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class PriceSettingBulkUpdate(BaseSchema):
    """Schema for bulk updating price settings."""

    price_settings: list[PriceSettingCreate]


# --- Transport Zone Schemas ---

class TransportZoneCreate(BaseSchema):
    """Schema for creating a transport zone."""

    zone_name: str
    zone_code: str


class TransportZoneUpdate(BaseSchema):
    """Schema for updating a transport zone."""

    zone_name: str | None = None
    zone_code: str | None = None
    is_active: bool | None = None


class TransportZoneResponse(BaseSchema):
    """Schema for transport zone response."""

    id: int
    zone_name: str
    zone_code: str
    is_active: bool


# --- Transport Pricing Schemas ---

class TransportPricingCreate(BaseSchema):
    """Schema for creating/updating transport pricing."""

    zone_id: int
    transport_fee_amount: Decimal

    @field_validator("transport_fee_amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class TransportPricingBulkUpdate(BaseSchema):
    """Schema for bulk updating transport pricing."""

    transport_pricings: list[TransportPricingCreate]


# --- Fixed Fee Schemas ---

class FixedFeeCreate(BaseSchema):
    """Schema for creating a fixed fee."""

    fee_type: str
    display_name: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class FixedFeeUpdate(BaseSchema):
    """Schema for updating a fixed fee."""

    display_name: str | None = None
    amount: Decimal | None = None
    is_active: bool | None = None


class FixedFeeResponse(BaseSchema):
    """Schema for fixed fee response."""

    id: int
    fee_type: str
    display_name: str
    amount: Decimal
    is_active: bool
