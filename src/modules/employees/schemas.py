from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime

from pydantic import EmailStr, field_validator

from src.shared.schemas import BaseSchema
from src.modules.employees.models import EmployeeStatus


class EmployeeBase(BaseSchema):
    """Shared fields for create/update."""

    surname: str
    first_name: str
    second_name: str | None = None

    gender: str | None = None
    marital_status: str | None = None
    nationality: str | None = None
    date_of_birth: date | None = None

    mobile_phone: str | None = None
    email: EmailStr | None = None
    physical_address: str | None = None
    town: str | None = None
    postal_address: str | None = None
    postal_code: str | None = None

    job_title: str | None = None
    employee_start_date: date | None = None
    salary: Decimal | None = None

    national_id_number: str | None = None
    kra_pin_number: str | None = None
    nssf_number: str | None = None
    nhif_number: str | None = None

    national_id_attachment_id: int | None = None
    kra_pin_attachment_id: int | None = None
    nssf_attachment_id: int | None = None
    nhif_attachment_id: int | None = None
    bank_doc_attachment_id: int | None = None

    bank_name: str | None = None
    bank_branch_name: str | None = None
    bank_code: str | None = None
    branch_code: str | None = None
    bank_account_number: str | None = None
    bank_account_holder_name: str | None = None

    next_of_kin_name: str | None = None
    next_of_kin_relationship: str | None = None
    next_of_kin_phone: str | None = None
    next_of_kin_address: str | None = None

    has_mortgage_relief: bool = False
    has_insurance_relief: bool = False

    notes: str | None = None

    @field_validator("surname", "first_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class EmployeeCreate(EmployeeBase):
    """Payload for creating employee."""

    user_id: int | None = None
    status: EmployeeStatus | None = None


class EmployeeUpdate(BaseSchema):
    """Payload for updating employee."""

    user_id: int | None = None

    surname: str | None = None
    first_name: str | None = None
    second_name: str | None = None

    gender: str | None = None
    marital_status: str | None = None
    nationality: str | None = None
    date_of_birth: date | None = None

    mobile_phone: str | None = None
    email: EmailStr | None = None
    physical_address: str | None = None
    town: str | None = None
    postal_address: str | None = None
    postal_code: str | None = None

    job_title: str | None = None
    employee_start_date: date | None = None

    national_id_number: str | None = None
    kra_pin_number: str | None = None
    nssf_number: str | None = None
    nhif_number: str | None = None

    national_id_attachment_id: int | None = None
    kra_pin_attachment_id: int | None = None
    nssf_attachment_id: int | None = None
    nhif_attachment_id: int | None = None
    bank_doc_attachment_id: int | None = None

    bank_name: str | None = None
    bank_branch_name: str | None = None
    bank_code: str | None = None
    branch_code: str | None = None
    bank_account_number: str | None = None
    bank_account_holder_name: str | None = None

    next_of_kin_name: str | None = None
    next_of_kin_relationship: str | None = None
    next_of_kin_phone: str | None = None
    next_of_kin_address: str | None = None

    has_mortgage_relief: bool | None = None
    has_insurance_relief: bool | None = None

    status: EmployeeStatus | None = None
    notes: str | None = None


class EmployeeResponse(BaseSchema):
    """Employee in API responses."""

    id: int
    employee_number: str
    user_id: int | None

    surname: str
    first_name: str
    second_name: str | None
    gender: str | None
    marital_status: str | None
    nationality: str | None
    date_of_birth: date | None

    mobile_phone: str | None
    email: str | None
    physical_address: str | None
    town: str | None
    postal_address: str | None
    postal_code: str | None

    job_title: str | None
    employee_start_date: date | None
    salary: Decimal | None

    national_id_number: str | None
    kra_pin_number: str | None
    nssf_number: str | None
    nhif_number: str | None

    national_id_attachment_id: int | None
    kra_pin_attachment_id: int | None
    nssf_attachment_id: int | None
    nhif_attachment_id: int | None
    bank_doc_attachment_id: int | None

    bank_name: str | None
    bank_branch_name: str | None
    bank_code: str | None
    branch_code: str | None
    bank_account_number: str | None
    bank_account_holder_name: str | None

    next_of_kin_name: str | None
    next_of_kin_relationship: str | None
    next_of_kin_phone: str | None
    next_of_kin_address: str | None

    has_mortgage_relief: bool
    has_insurance_relief: bool

    status: str
    notes: str | None

    created_at: datetime
    updated_at: datetime


class EmployeeListFilters(BaseSchema):
    """Filters for employee list."""

    status: EmployeeStatus | None = None
    search: str | None = None  # name, email, phone, national_id_number
    page: int = 1
    limit: int = 20


class EmployeeCsvImportResult(BaseSchema):
    """Result of CSV import."""

    rows_processed: int
    employees_created: int
    employees_updated: int
    errors: list[dict]
