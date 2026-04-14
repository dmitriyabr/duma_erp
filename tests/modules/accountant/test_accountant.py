"""Tests for Accountant API: audit trail and exports."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit.service import create_audit_log
from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.billing_accounts.models import BillingAccount, BillingAccountType
from src.modules.invoices.models import Invoice, InvoiceStatus
from src.modules.payments.models import CreditAllocation, Payment
from src.modules.students.models import Gender, Grade, Student, StudentStatus


async def _get_token(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> str:
    """Create user and return access token."""
    auth = AuthService(db_session)
    await auth.create_user(
        email="accountant_test@test.com",
        password="Pass123",
        full_name="Test User",
        role=role,
    )
    await db_session.commit()
    _, token, _ = await auth.authenticate("accountant_test@test.com", "Pass123")
    return token


class TestAccountantAuditTrail:
    """Tests for GET /accountant/audit-trail."""

    async def test_audit_trail_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get("/api/v1/accountant/audit-trail")
        assert response.status_code == 401

    async def test_audit_trail_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can list audit trail."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        await create_audit_log(
            db_session,
            action="CREATE",
            entity_type="Payment",
            entity_id=1,
            user_id=None,
            entity_identifier="PAY-2026-000001",
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["total"] >= 1
        assert len(data["data"]["items"]) >= 1
        item = data["data"]["items"][0]
        assert item["entity_type"] == "Payment"
        assert item["entity_identifier"] == "PAY-2026-000001"
        assert item["action"] == "CREATE"

    async def test_audit_trail_admin_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can list audit trail."""
        token = await _get_token(client, db_session, UserRole.ADMIN)
        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_audit_trail_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access accountant audit trail."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/accountant/audit-trail",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestAccountantExportStudentPayments:
    """Tests for GET /accountant/export/student-payments."""

    async def test_export_student_payments_requires_auth(self, client: AsyncClient):
        """Without token returns 401."""
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv"
        )
        assert response.status_code == 401

    async def test_export_student_payments_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can export student payments as CSV."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        text = response.text
        assert "Receipt Date" in text
        assert "Receipt#" in text
        assert "Student Name" in text
        assert "Reference" in text
        assert "Amount" in text

    async def test_export_student_payments_includes_billing_account_roster(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Family payments should export account number and all linked children."""
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="accountant_family_payments@test.com",
            password="Pass123",
            full_name="Accountant User",
            role=UserRole.ACCOUNTANT,
        )
        await db_session.flush()

        grade = Grade(code="AFP", name="Accountant Family", display_order=1, is_active=True)
        account = BillingAccount(
            account_number="FAM-2026-AFP001",
            display_name="Accountant Family Account",
            account_type=BillingAccountType.FAMILY.value,
            primary_guardian_name="Family Contact",
            primary_guardian_phone="+254700000040",
            created_by_id=user.id,
        )
        db_session.add_all([grade, account])
        await db_session.flush()

        first_child = Student(
            student_number="STU-2026-AFP001",
            first_name="Export",
            last_name="One",
            gender=Gender.MALE.value,
            billing_account_id=account.id,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Family Contact",
            guardian_phone="+254700000040",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        second_child = Student(
            student_number="STU-2026-AFP002",
            first_name="Export",
            last_name="Two",
            gender=Gender.FEMALE.value,
            billing_account_id=account.id,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Family Contact",
            guardian_phone="+254700000040",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add_all([first_child, second_child])
        await db_session.flush()

        payment = Payment(
            payment_number="PAY-2026-AFP001",
            receipt_number="RCP-2026-AFP001",
            student_id=first_child.id,
            billing_account_id=account.id,
            amount=Decimal("150.00"),
            payment_method="mpesa",
            payment_date=date(2026, 1, 10),
            reference="MPESA-AFP001",
            status="completed",
            received_by_id=user.id,
        )
        db_session.add(payment)
        await db_session.commit()

        _, token, _ = await auth.authenticate("accountant_family_payments@test.com", "Pass123")
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        text = response.text
        assert "Billing Account#" in text
        assert "FAM-2026-AFP001" in text
        assert "Accountant Family Account" in text
        assert "Export One" in text
        assert "Export Two" in text
        assert "STU-2026-AFP001" in text
        assert "STU-2026-AFP002" in text

    async def test_export_student_balance_changes_uses_allocations_for_family(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Shared family payment should affect a child ledger only when allocated."""
        auth = AuthService(db_session)
        user = await auth.create_user(
            email="accountant_family_balance@test.com",
            password="Pass123",
            full_name="Accountant User",
            role=UserRole.ACCOUNTANT,
        )
        await db_session.flush()

        grade = Grade(code="AFB", name="Accountant Balance", display_order=1, is_active=True)
        account = BillingAccount(
            account_number="FAM-2026-AFB001",
            display_name="Balance Family Account",
            account_type=BillingAccountType.FAMILY.value,
            primary_guardian_name="Family Contact",
            primary_guardian_phone="+254700000050",
            created_by_id=user.id,
        )
        db_session.add_all([grade, account])
        await db_session.flush()

        payer_child = Student(
            student_number="STU-2026-AFB001",
            first_name="Balance",
            last_name="Reference",
            gender=Gender.MALE.value,
            billing_account_id=account.id,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Family Contact",
            guardian_phone="+254700000050",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        debtor_child = Student(
            student_number="STU-2026-AFB002",
            first_name="Balance",
            last_name="Debtor",
            gender=Gender.FEMALE.value,
            billing_account_id=account.id,
            grade_id=grade.id,
            transport_zone_id=None,
            guardian_name="Family Contact",
            guardian_phone="+254700000050",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add_all([payer_child, debtor_child])
        await db_session.flush()

        invoice = Invoice(
            invoice_number="INV-2026-AFB001",
            student_id=debtor_child.id,
            billing_account_id=account.id,
            term_id=None,
            invoice_type="school_fee",
            status=InvoiceStatus.PARTIALLY_PAID.value,
            issue_date=date(2026, 1, 5),
            due_date=date(2026, 1, 31),
            subtotal=Decimal("100.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("100.00"),
            paid_total=Decimal("80.00"),
            amount_due=Decimal("20.00"),
            created_by_id=user.id,
        )
        payment = Payment(
            payment_number="PAY-2026-AFB001",
            receipt_number="RCP-2026-AFB001",
            student_id=payer_child.id,
            billing_account_id=account.id,
            amount=Decimal("80.00"),
            payment_method="mpesa",
            payment_date=date(2026, 1, 6),
            reference="MPESA-AFB001",
            status="completed",
            received_by_id=user.id,
        )
        db_session.add_all([invoice, payment])
        await db_session.flush()

        allocation = CreditAllocation(
            student_id=debtor_child.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            invoice_line_id=None,
            amount=Decimal("80.00"),
            allocated_by_id=user.id,
            created_at=datetime(2026, 1, 6, 12, 0, tzinfo=timezone.utc),
        )
        db_session.add(allocation)
        await db_session.commit()

        _, token, _ = await auth.authenticate("accountant_family_balance@test.com", "Pass123")
        response = await client.get(
            "/api/v1/accountant/export/student-balance-changes"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        text = response.text
        assert "Billing Account#" in text
        assert "Balance Debtor" in text
        assert "Allocation" in text
        assert "Payment allocated - School Fee" in text
        assert "STU-2026-AFB002" in text
        assert "STU-2026-AFB001" not in text

    async def test_export_student_payments_user_forbidden(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """User role cannot access export."""
        token = await _get_token(client, db_session, UserRole.USER)
        response = await client.get(
            "/api/v1/accountant/export/student-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_export_procurement_payments_accountant_ok(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can export procurement payments as CSV."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/accountant/export/procurement-payments"
            "?start_date=2026-01-01&end_date=2026-01-31&format=csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        text = response.text
        assert "Payment Date" in text
        assert "Payment#" in text
        assert "Supplier" in text
        assert "PO#" in text


class TestAccountantReadOnlyAccess:
    """Accountant can read all document lists/details; cannot create/update."""

    async def test_accountant_can_list_students(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can GET /students."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/students?page=1&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_accountant_can_list_purchase_orders(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can GET /procurement/purchase-orders."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/procurement/purchase-orders?page=1&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_accountant_can_list_grns(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can GET /procurement/grns."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/procurement/grns?page=1&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_accountant_can_list_payouts(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant can GET /compensations/payouts."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.get(
            "/api/v1/compensations/payouts?page=1&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_accountant_cannot_create_payment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Accountant gets 403 on POST /payments (read-only)."""
        token = await _get_token(client, db_session, UserRole.ACCOUNTANT)
        response = await client.post(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": 1,
                "amount": 100,
                "payment_method": "mpesa",
                "payment_date": "2026-01-15",
                "reference": "test-ref",
            },
        )
        assert response.status_code == 403
