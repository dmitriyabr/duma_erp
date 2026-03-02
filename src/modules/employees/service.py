from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import User
from src.core.documents import get_document_number
from src.core.exceptions import ValidationError
from src.modules.employees.models import Employee, EmployeeStatus
from src.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeCsvImportResult,
    EmployeeListFilters,
    EmployeeUpdate,
)


class EmployeeService:
    """Service for employee master data."""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session

    async def list_employees(
        self,
        filters: EmployeeListFilters,
    ) -> tuple[list[Employee], int]:
        stmt = select(Employee)
        count_stmt = select(func.count(Employee.id))

        if filters.status:
            stmt = stmt.where(Employee.status == filters.status.value)
            count_stmt = count_stmt.where(
                Employee.status == filters.status.value
            )

        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            search_filter = or_(
                Employee.first_name.ilike(pattern),
                Employee.surname.ilike(pattern),
                Employee.email.ilike(pattern),
                Employee.mobile_phone.ilike(pattern),
                Employee.national_id_number.ilike(pattern),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        count_result = await self.db.execute(count_stmt)
        total = int(count_result.scalar_one() or 0)

        offset = (filters.page - 1) * filters.limit
        stmt = (
            stmt.order_by(Employee.surname, Employee.first_name)
            .offset(offset)
            .limit(filters.limit)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().unique().all())
        return items, total

    async def get_employee(self, employee_id: int) -> Employee | None:
        result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        return result.scalar_one_or_none()

    async def create_employee(
        self, data: EmployeeCreate, *, created_by_id: int
    ) -> Employee:
        if data.user_id is not None:
            await self._validate_user_link(user_id=data.user_id)

        employee_number = await get_document_number(self.db, prefix="EMP")
        employee = Employee(
            employee_number=employee_number,
            user_id=data.user_id,
            surname=data.surname.strip(),
            first_name=data.first_name.strip(),
            second_name=(data.second_name or "").strip() or None,
            gender=(data.gender or "").strip() or None,
            marital_status=(data.marital_status or "").strip() or None,
            nationality=(data.nationality or "").strip() or None,
            date_of_birth=data.date_of_birth,
            mobile_phone=(data.mobile_phone or "").strip() or None,
            email=(data.email or "").strip() or None if data.email else None,
            physical_address=(data.physical_address or "").strip() or None,
            town=(data.town or "").strip() or None,
            postal_address=(data.postal_address or "").strip() or None,
            postal_code=(data.postal_code or "").strip() or None,
            job_title=(data.job_title or "").strip() or None,
            employee_start_date=data.employee_start_date,
            salary=data.salary,
            national_id_number=(data.national_id_number or "").strip() or None,
            kra_pin_number=(data.kra_pin_number or "").strip() or None,
            nssf_number=(data.nssf_number or "").strip() or None,
            nhif_number=(data.nhif_number or "").strip() or None,
            national_id_attachment_id=data.national_id_attachment_id,
            kra_pin_attachment_id=data.kra_pin_attachment_id,
            nssf_attachment_id=data.nssf_attachment_id,
            nhif_attachment_id=data.nhif_attachment_id,
            bank_doc_attachment_id=data.bank_doc_attachment_id,
            bank_name=(data.bank_name or "").strip() or None,
            bank_branch_name=(data.bank_branch_name or "").strip() or None,
            bank_code=(data.bank_code or "").strip() or None,
            branch_code=(data.branch_code or "").strip() or None,
            bank_account_number=(
                data.bank_account_number or ""
            ).strip()
            or None,
            bank_account_holder_name=(
                data.bank_account_holder_name or ""
            ).strip() or None,
            next_of_kin_name=(data.next_of_kin_name or "").strip() or None,
            next_of_kin_relationship=(
                data.next_of_kin_relationship or ""
            ).strip()
            or None,
            next_of_kin_phone=(data.next_of_kin_phone or "").strip() or None,
            next_of_kin_address=(
                data.next_of_kin_address or ""
            ).strip()
            or None,
            has_mortgage_relief=data.has_mortgage_relief,
            has_insurance_relief=data.has_insurance_relief,
            status=(
                data.status.value
                if data.status is not None
                else EmployeeStatus.ACTIVE.value
            ),
            notes=(data.notes or "").strip() or None,
            created_by_id=created_by_id,
        )
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def update_employee(
        self, employee: Employee, data: EmployeeUpdate
    ) -> Employee:
        # Respect explicit nulls: only update fields provided in payload.
        provided_fields = data.model_fields_set

        if "user_id" in provided_fields:
            if data.user_id is None:
                employee.user_id = None
            else:
                await self._validate_user_link(
                    user_id=data.user_id,
                    current_employee_id=employee.id,
                )
                employee.user_id = data.user_id

        for field in (
            "surname",
            "first_name",
            "second_name",
            "gender",
            "marital_status",
            "nationality",
            "mobile_phone",
            "email",
            "physical_address",
            "town",
            "postal_address",
            "postal_code",
            "job_title",
            "national_id_number",
            "kra_pin_number",
            "nssf_number",
            "nhif_number",
            "national_id_attachment_id",
            "kra_pin_attachment_id",
            "nssf_attachment_id",
            "nhif_attachment_id",
            "bank_doc_attachment_id",
            "bank_name",
            "bank_branch_name",
            "bank_code",
            "branch_code",
            "bank_account_number",
            "bank_account_holder_name",
            "next_of_kin_name",
            "next_of_kin_relationship",
            "next_of_kin_phone",
            "next_of_kin_address",
            "notes",
            "salary",
        ):
            if field not in provided_fields:
                continue
            value = getattr(data, field)
            if isinstance(value, str):
                value = value.strip()
            setattr(employee, field, value)

        if "date_of_birth" in provided_fields:
            employee.date_of_birth = data.date_of_birth
        if "employee_start_date" in provided_fields:
            employee.employee_start_date = data.employee_start_date
        if "has_mortgage_relief" in provided_fields:
            employee.has_mortgage_relief = data.has_mortgage_relief
        if "has_insurance_relief" in provided_fields:
            employee.has_insurance_relief = data.has_insurance_relief
        if "status" in provided_fields:
            if data.status is None:
                raise ValidationError("status cannot be null")
            employee.status = data.status.value

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def _validate_user_link(
        self,
        *,
        user_id: int,
        current_employee_id: int | None = None,
    ) -> None:
        user = await self.db.get(User, user_id)
        if not user:
            raise ValidationError("Selected user does not exist")

        stmt = select(Employee).where(Employee.user_id == user_id)
        if current_employee_id is not None:
            stmt = stmt.where(Employee.id != current_employee_id)
        existing_result = await self.db.execute(stmt)
        existing_employee = existing_result.scalar_one_or_none()
        if existing_employee:
            raise ValidationError("Selected user is already linked to another employee")

    async def delete_employee(self, employee: Employee) -> None:
        await self.db.delete(employee)
        await self.db.commit()

    async def export_csv(self, *, include_internal_number: bool = True) -> str:
        result = await self.db.execute(
            select(Employee).order_by(Employee.surname, Employee.first_name)
        )
        employees = list(result.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output)
        columns = [
            "Full Name",
            "Mobile Phone",
            "Date of Birth",
            "National ID Number",
            "KRA PIN Number",
            "NSSF Number",
            "NHIF Number",
            "Job Title",
            "Employee Start Date",
            "Salary",
            "Bank Name",
            "Bank Branch Name",
            "Bank Code",
            "Branch Code",
            "Bank Account Number",
            "Bank Account Holder Name",
        ]
        if include_internal_number:
            columns = ["Employee Number", *columns]
        writer.writerow(columns)
        for employee in employees:
            row = [
                employee.full_name,
                employee.mobile_phone or "",
                (
                    employee.date_of_birth.isoformat()
                    if employee.date_of_birth
                    else ""
                ),
                employee.national_id_number or "",
                employee.kra_pin_number or "",
                employee.nssf_number or "",
                employee.nhif_number or "",
                employee.job_title or "",
                (
                    employee.employee_start_date.isoformat()
                    if employee.employee_start_date
                    else ""
                ),
                str(employee.salary) if employee.salary is not None else "",
                employee.bank_name or "",
                employee.bank_branch_name or "",
                employee.bank_code or "",
                employee.branch_code or "",
                employee.bank_account_number or "",
                employee.bank_account_holder_name or "",
            ]
            if include_internal_number:
                row = [employee.employee_number, *row]
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def _parse_import_date(value: str) -> date | None:
        raw = value.strip()
        if not raw:
            return None
        # Accept Google-form-like dates with or without time.
        for fmt in (
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%d/%m/%Y",
            "%d/%m/%y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M:%S %p",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %I:%M:%S %p",
        ):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        # Fallback for strings where date token is first.
        first_token = raw.split(" ")[0]
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(first_token, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_import_salary(value: str) -> Decimal | None:
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace(",", "")
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return None

    async def import_from_csv(
        self, content: bytes | str, *, created_by_id: int
    ) -> EmployeeCsvImportResult:
        """Import employees from CSV exported from Google Form."""
        if isinstance(content, bytes):
            text = content.decode("utf-8-sig")
        else:
            text = content

        reader = csv.DictReader(io.StringIO(text))
        required = {"Surname / Last Name", "First Name"}
        if not reader.fieldnames:
            raise ValidationError("CSV has no headers")
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"CSV missing columns: {sorted(missing)}")

        rows = list(reader)
        nat_ids = {
            (row.get("National ID Number") or "").strip()
            for row in rows
            if (row.get("National ID Number") or "").strip()
        }
        emails_lower = {
            (row.get("Email Address") or "").strip().lower()
            for row in rows
            if (row.get("Email Address") or "").strip()
        }
        existing_by_nat_id: dict[str, Employee] = {}
        existing_by_email: dict[str, Employee] = {}
        if nat_ids:
            result = await self.db.execute(
                select(Employee).where(
                    Employee.national_id_number.in_(nat_ids)
                )
            )
            for employee in result.scalars().all():
                if employee.national_id_number:
                    existing_by_nat_id[employee.national_id_number] = employee
        if emails_lower:
            result = await self.db.execute(
                select(Employee).where(
                    func.lower(Employee.email).in_(emails_lower)
                )
            )
            for employee in result.scalars().all():
                if employee.email:
                    existing_by_email[employee.email.lower()] = employee

        rows_processed = 0
        created = 0
        updated = 0
        errors: list[dict] = []

        for row_num, row in enumerate(rows, start=2):
            surname = (row.get("Surname / Last Name") or "").strip()
            first_name = (row.get("First Name") or "").strip()
            if not surname or not first_name:
                errors.append(
                    {
                        "row": row_num,
                        "message": (
                            "Surname / Last Name and First Name are required"
                        ),
                    }
                )
                continue

            nat_id = (row.get("National ID Number") or "").strip()
            email_raw = (row.get("Email Address") or "").strip() or None
            email_key = email_raw.lower() if email_raw else None

            existing: Employee | None = None
            if nat_id:
                existing = existing_by_nat_id.get(nat_id)
            if not existing and email_key:
                existing = existing_by_email.get(email_key)

            try:
                dob = self._parse_import_date(row.get("Date of Birth") or "")
                start_date = self._parse_import_date(
                    row.get("Employee Start Date") or ""
                )

                base_kwargs = dict(
                    surname=surname,
                    first_name=first_name,
                    second_name=(row.get("Second Name") or "").strip() or None,
                    gender=(row.get("Gender") or "").strip() or None,
                    marital_status=(
                        row.get("Marital Status") or ""
                    ).strip()
                    or None,
                    nationality=(
                        row.get("Nationality") or ""
                    ).strip()
                    or None,
                    date_of_birth=dob,
                    mobile_phone=(
                        row.get("Mobile Phone Number") or ""
                    ).strip()
                    or None,
                    email=email_raw,
                    physical_address=(
                        row.get("Physical Address") or ""
                    ).strip()
                    or None,
                    town=(row.get("Town") or "").strip() or None,
                    postal_address=(
                        row.get("Postal Address") or ""
                    ).strip()
                    or None,
                    postal_code=(
                        row.get("Postal Code") or ""
                    ).strip()
                    or None,
                    job_title=(
                        row.get("Job Title / Role") or ""
                    ).strip()
                    or None,
                    employee_start_date=start_date,
                    salary=self._parse_import_salary(row.get("Salary") or ""),
                    national_id_number=nat_id or None,
                    kra_pin_number=(
                        row.get("KRA PIN Number") or ""
                    ).strip()
                    or None,
                    nssf_number=(
                        row.get("NSSF Number") or ""
                    ).strip()
                    or None,
                    nhif_number=(
                        row.get("NHIF / SHA Number") or ""
                    ).strip()
                    or None,
                    bank_name=(row.get("Bank Name") or "").strip() or None,
                    bank_branch_name=(
                        row.get("Bank Branch Name") or ""
                    ).strip()
                    or None,
                    bank_code=(row.get("Bank Code") or "").strip() or None,
                    branch_code=(row.get("Branch Code") or "").strip() or None,
                    bank_account_number=(
                        row.get("Account Number") or ""
                    ).strip()
                    or None,
                    bank_account_holder_name=(
                        row.get("Account Holder Name") or ""
                    ).strip()
                    or None,
                    next_of_kin_name=(
                        row.get("Next of Kin – Full Name") or ""
                    ).strip()
                    or None,
                    next_of_kin_relationship=(
                        row.get("Relationship to Employee") or ""
                    ).strip()
                    or None,
                    next_of_kin_phone=(
                        row.get("Next of Kin – Mobile Phone Number") or ""
                    ).strip()
                    or None,
                    next_of_kin_address=(
                        row.get("Next of Kin – Physical Address") or ""
                    ).strip()
                    or None,
                    has_mortgage_relief=(
                        (row.get("Do you have Mortgage Relief?") or "")
                        .strip()
                        .lower()
                        in ("yes", "y", "true", "1")
                    ),
                    has_insurance_relief=(
                        (row.get("Do you have Insurance Reliefs?") or "")
                        .strip()
                        .lower()
                        in ("yes", "y", "true", "1")
                    ),
                )

                if existing:
                    for key, value in base_kwargs.items():
                        if value is not None:
                            setattr(existing, key, value)
                    target_employee = existing
                    updated += 1
                else:
                    employee_number = await get_document_number(
                        self.db,
                        prefix="EMP",
                    )
                    employee = Employee(
                        employee_number=employee_number,
                        created_by_id=created_by_id,
                        **base_kwargs,
                        status=EmployeeStatus.ACTIVE.value,
                    )
                    self.db.add(employee)
                    target_employee = employee
                    created += 1

                if nat_id:
                    existing_by_nat_id[nat_id] = target_employee
                if email_key:
                    existing_by_email[email_key] = target_employee

                rows_processed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"row": row_num, "message": str(exc)})
                continue

        await self.db.commit()
        return EmployeeCsvImportResult(
            rows_processed=rows_processed,
            employees_created=created,
            employees_updated=updated,
            errors=errors,
        )
