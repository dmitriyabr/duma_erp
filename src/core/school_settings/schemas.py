"""Schemas for school settings (PDF branding and payment details)."""

from pydantic import BaseModel, Field


class SchoolSettingsUpdate(BaseModel):
    """Update school settings (all optional)."""

    school_name: str | None = None
    school_address: str | None = None
    school_phone: str | None = None
    school_email: str | None = None
    use_paybill: bool | None = None
    mpesa_business_number: str | None = None
    use_bank_transfer: bool | None = None
    bank_name: str | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_branch: str | None = None
    bank_swift_code: str | None = None
    logo_attachment_id: int | None = None
    stamp_attachment_id: int | None = None


class SchoolSettingsResponse(BaseModel):
    """School settings for API response."""

    id: int
    school_name: str = ""
    school_address: str = ""
    school_phone: str = ""
    school_email: str = ""
    use_paybill: bool = True
    mpesa_business_number: str = ""
    use_bank_transfer: bool = False
    bank_name: str = ""
    bank_account_name: str = ""
    bank_account_number: str = ""
    bank_branch: str = ""
    bank_swift_code: str = ""
    logo_attachment_id: int | None = None
    stamp_attachment_id: int | None = None

    model_config = {"from_attributes": True}
