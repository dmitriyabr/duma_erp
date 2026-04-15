"""ORM hooks that keep billing account references populated for legacy inserts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from src.core.documents.models import DocumentSequence
from src.modules.billing_accounts.models import BillingAccount, BillingAccountType
from src.modules.invoices.models import Invoice
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.students.models import Student


def _next_account_number(session: Session) -> str:
    year = datetime.now().year
    sequence = next(
        (
            item
            for item in session.new
            if isinstance(item, DocumentSequence)
            and item.prefix == "FAM"
            and item.year == year
        ),
        None,
    )
    if sequence is None:
        sequence = session.execute(
            select(DocumentSequence).where(
                DocumentSequence.prefix == "FAM",
                DocumentSequence.year == year,
            )
        ).scalar_one_or_none()
    if sequence is None:
        sequence = DocumentSequence(prefix="FAM", year=year, last_number=0)
        session.add(sequence)
    sequence.last_number += 1
    return f"FAM-{year}-{sequence.last_number:06d}"


def _ensure_student_account(session: Session, student: Student) -> BillingAccount:
    if student.billing_account is not None:
        return student.billing_account
    if student.billing_account_id is not None:
        account = session.get(BillingAccount, student.billing_account_id)
        if account is not None:
            student.billing_account = account
            return account

    account = BillingAccount(
        account_number=_next_account_number(session),
        display_name=f"{student.first_name} {student.last_name}".strip() or student.student_number,
        account_type=BillingAccountType.INDIVIDUAL.value,
        primary_guardian_name=student.guardian_name,
        primary_guardian_phone=student.guardian_phone,
        primary_guardian_email=student.guardian_email,
        cached_credit_balance=Decimal("0.00"),
        created_by_id=student.created_by_id,
    )
    session.add(account)
    student.billing_account = account
    student.cached_credit_balance = Decimal("0.00")
    return account


@event.listens_for(Session, "before_flush")
def populate_billing_account_references(
    session: Session,
    flush_context,
    instances,
) -> None:
    """Populate billing account links for legacy direct ORM inserts."""
    for obj in list(session.new):
        if isinstance(obj, Student) and obj.billing_account_id is None:
            _ensure_student_account(session, obj)

    for obj in list(session.new):
        if isinstance(obj, Invoice) and obj.billing_account_id is None and obj.student_id is not None:
            student = obj.student or session.get(Student, obj.student_id)
            if student is not None:
                obj.billing_account = _ensure_student_account(session, student)

        if isinstance(obj, Payment) and obj.billing_account_id is None and obj.student_id is not None:
            student = obj.student or session.get(Student, obj.student_id)
            if student is not None:
                obj.billing_account = _ensure_student_account(session, student)

        if isinstance(obj, CreditAllocation) and obj.billing_account_id is None:
            invoice = obj.invoice or (session.get(Invoice, obj.invoice_id) if obj.invoice_id is not None else None)
            if invoice is not None:
                obj.billing_account = invoice.billing_account
                if obj.student_id is None:
                    obj.student_id = invoice.student_id
