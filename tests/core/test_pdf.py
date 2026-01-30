"""Tests for PDF endpoints (invoice and receipt). Uses mock for WeasyPrint to avoid system deps."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.school_settings.models import SchoolSettings
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from src.modules.students.models import Grade, Student, StudentStatus, Gender
from src.modules.terms.models import Term, TermStatus


FAKE_PDF = b"%PDF-1.4 fake pdf content"


async def _setup_invoice_pdf_data(db_session: AsyncSession) -> dict:
    """Create minimal data: user, grade, student, term, invoice with line. Returns ids and token."""
    auth = AuthService(db_session)
    user = await auth.create_user(
        email="pdf_test@school.com",
        password="Test123!",
        full_name="PDF Test",
        role=UserRole.ADMIN,
    )
    await db_session.flush()

    grade = Grade(code="G1", name="Grade 1", display_order=1, is_active=True)
    db_session.add(grade)
    await db_session.flush()

    student = Student(
        student_number="STU-2026-000001",
        first_name="John",
        last_name="Doe",
        gender=Gender.MALE.value,
        grade_id=grade.id,
        guardian_name="Jane Doe",
        guardian_phone="+254712000000",
        status=StudentStatus.ACTIVE.value,
        created_by_id=user.id,
    )
    db_session.add(student)
    await db_session.flush()

    category = Category(name="Cat", is_active=True)
    db_session.add(category)
    await db_session.flush()

    kit = Kit(
        category_id=category.id,
        sku_code="KIT1",
        name="School Fee",
        item_type=ItemType.SERVICE.value,
        price_type=PriceType.STANDARD.value,
        price=Decimal("10000"),
        requires_full_payment=False,
        is_active=True,
    )
    db_session.add(kit)
    await db_session.flush()

    term = Term(
        year=2026,
        term_number=1,
        display_name="2026-T1",
        status=TermStatus.ACTIVE.value,
        created_by_id=user.id,
    )
    db_session.add(term)
    await db_session.flush()

    invoice = Invoice(
        invoice_number="INV-2026-000001",
        student_id=student.id,
        term_id=term.id,
        invoice_type=InvoiceType.SCHOOL_FEE.value,
        status=InvoiceStatus.ISSUED.value,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        subtotal=Decimal("10000"),
        discount_total=Decimal("0"),
        total=Decimal("10000"),
        paid_total=Decimal("0"),
        amount_due=Decimal("10000"),
        created_by_id=user.id,
    )
    db_session.add(invoice)
    await db_session.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        kit_id=kit.id,
        description="School Fee",
        quantity=1,
        unit_price=Decimal("10000"),
        line_total=Decimal("10000"),
        discount_amount=Decimal("0"),
        net_amount=Decimal("10000"),
        paid_amount=Decimal("0"),
        remaining_amount=Decimal("10000"),
    )
    db_session.add(line)
    await db_session.flush()

    school_settings = SchoolSettings(
        school_name="Test School",
        use_paybill=True,
        use_bank_transfer=False,
    )
    db_session.add(school_settings)
    await db_session.flush()

    _, token, _ = await auth.authenticate("pdf_test@school.com", "Test123!")
    return {"invoice_id": invoice.id, "student_id": student.id, "user_id": user.id, "token": token}


async def _setup_receipt_pdf_data(db_session: AsyncSession) -> dict:
    """Create payment (completed) and school_settings. Returns payment_id and token."""
    data = await _setup_invoice_pdf_data(db_session)
    auth = AuthService(db_session)
    payment = Payment(
        payment_number="PAY-2026-000001",
        receipt_number="RCP-2026-000001",
        student_id=data["student_id"],
        amount=Decimal("5000"),
        payment_method=PaymentMethod.MPESA.value,
        payment_date=date.today(),
        reference="REF123",
        status=PaymentStatus.COMPLETED.value,
        received_by_id=data["user_id"],
    )
    db_session.add(payment)
    await db_session.flush()
    # Load student and received_by for receipt (normally done by get_payment_by_id)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from src.modules.payments.models import Payment as P
    result = await db_session.execute(
        select(P).where(P.id == payment.id).options(
            selectinload(P.student).selectinload(Student.grade),
            selectinload(P.received_by),
        )
    )
    payment = result.scalar_one()
    data["payment"] = payment
    data["payment_id"] = payment.id
    return data


class TestInvoicePdfEndpoint:
    """Tests for GET /invoices/{id}/pdf."""

    @pytest.mark.asyncio
    async def test_invoice_pdf_returns_pdf(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /invoices/{id}/pdf returns 200 and application/pdf with mocked generator."""
        data = await _setup_invoice_pdf_data(db_session)
        await db_session.commit()

        with patch("src.modules.invoices.router.pdf_service") as mock_svc:
            mock_svc.generate_invoice_pdf.return_value = FAKE_PDF
            response = await client.get(
                f"/api/v1/invoices/{data['invoice_id']}/pdf",
                headers={"Authorization": f"Bearer {data['token']}"},
            )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content.startswith(b"%PDF")
        assert response.content == FAKE_PDF

    @pytest.mark.asyncio
    async def test_invoice_pdf_requires_auth(self, client: AsyncClient, db_session: AsyncSession):
        """GET /invoices/{id}/pdf without token returns 401."""
        data = await _setup_invoice_pdf_data(db_session)
        await db_session.commit()
        response = await client.get(f"/api/v1/invoices/{data['invoice_id']}/pdf")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invoice_pdf_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /invoices/99999/pdf returns 404."""
        data = await _setup_invoice_pdf_data(db_session)
        await db_session.commit()
        response = await client.get(
            "/api/v1/invoices/99999/pdf",
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        assert response.status_code == 404


class TestReceiptPdfEndpoint:
    """Tests for GET /payments/{id}/receipt/pdf."""

    @pytest.mark.asyncio
    async def test_receipt_pdf_completed_returns_pdf(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /payments/{id}/receipt/pdf for completed payment returns 200 and PDF."""
        data = await _setup_receipt_pdf_data(db_session)
        await db_session.commit()

        with patch("src.modules.payments.router.pdf_service") as mock_svc:
            mock_svc.generate_receipt_pdf.return_value = FAKE_PDF
            response = await client.get(
                f"/api/v1/payments/{data['payment_id']}/receipt/pdf",
                headers={"Authorization": f"Bearer {data['token']}"},
            )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_receipt_pdf_pending_returns_400(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /payments/{id}/receipt/pdf for pending payment returns 400."""
        data = await _setup_invoice_pdf_data(db_session)
        from src.modules.payments.models import Payment as P, PaymentStatus as PS
        payment = P(
            payment_number="PAY-PEND-001",
            student_id=data["student_id"],
            amount=Decimal("1000"),
            payment_method=PaymentMethod.MPESA.value,
            payment_date=date.today(),
            status=PS.PENDING.value,
            received_by_id=data["user_id"],
        )
        db_session.add(payment)
        await db_session.flush()
        await db_session.commit()

        response = await client.get(
            f"/api/v1/payments/{payment.id}/receipt/pdf",
            headers={"Authorization": f"Bearer {data['token']}"},
        )
        assert response.status_code == 400
