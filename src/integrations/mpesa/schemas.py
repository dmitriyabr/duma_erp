from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MpesaC2BConfirmationPayload(BaseModel):
    """
    Safaricom C2B confirmation payload (commonly used fields).

    We keep fields optional because payloads differ between environments/banks.
    """

    TransactionType: str | None = None
    TransID: str = Field(..., min_length=1, max_length=50)
    TransTime: str | None = None  # YYYYMMDDHHMMSS
    TransAmount: Decimal = Field(..., gt=0)
    BusinessShortCode: str | None = None
    BillRefNumber: str | None = None

    InvoiceNumber: str | None = None
    OrgAccountBalance: str | None = None
    ThirdPartyTransID: str | None = None
    MSISDN: str | None = None
    FirstName: str | None = None
    MiddleName: str | None = None
    LastName: str | None = None


class MpesaC2BValidationPayload(BaseModel):
    TransactionType: str | None = None
    BillRefNumber: str | None = None
    TransAmount: Decimal | None = Field(None, gt=0)
    BusinessShortCode: str | None = None
    MSISDN: str | None = None


class MpesaC2BResponse(BaseModel):
    ResultCode: int
    ResultDesc: str


class MpesaC2BEventResponse(BaseModel):
    id: int
    trans_id: str
    business_short_code: str | None
    bill_ref_number: str | None
    derived_student_number: str | None
    amount: Decimal
    status: str
    error_message: str | None
    payment_id: int | None
    received_at: datetime

    model_config = {"from_attributes": True}


class MpesaLinkEventRequest(BaseModel):
    student_id: int


def parse_trans_time_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if len(raw) != 14 or not raw.isdigit():
        return None
    # NOTE: treat as local wall clock provided by M-Pesa; store as naive datetime.
    # We only need the date component for internal Payment.payment_date.
    try:
        return datetime(
            int(raw[0:4]),
            int(raw[4:6]),
            int(raw[6:8]),
            int(raw[8:10]),
            int(raw[10:12]),
            int(raw[12:14]),
        )
    except Exception:
        return None

