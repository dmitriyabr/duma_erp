from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.auth.models import User
from src.core.config import settings
from src.modules.bank_statements.models import BankTransactionMatch
from src.modules.bank_statements.service import parse_stanbic_csv
from src.modules.compensations.models import CompensationPayout
from src.modules.procurement.models import PaymentPurpose, ProcurementPayment, ProcurementPaymentMethod
from src.modules.procurement.models import ProcurementPaymentStatus


@pytest.fixture
def storage_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


async def _get_admin_token(db_session: AsyncSession) -> str:
    auth = AuthService(db_session)
    await auth.create_user(
        email="bank_stmt_admin@test.com",
        password="Pass123!",
        full_name="Bank Stmt Admin",
        role=UserRole.SUPER_ADMIN,
    )
    await db_session.commit()
    _, token, _ = await auth.authenticate("bank_stmt_admin@test.com", "Pass123!")
    return token


def _sample_csv() -> bytes:
    return (
        "Transactions Report\n"
        "Account Name:,IGNISHA EDUCATION LIMITED\n"
        "Account No:,0100017036593 - SBICKENX\n"
        "Currency:,KES - Kenyan Shilling\n"
        "Range From:,30/01/2026\n"
        "Range To:,06/02/2026\n"
        "Date,Description,Value Date,Debit,Credit,Account owner reference,Type\n"
        "10/01/2026,BOL MOBILE PAYMENTS MARKETING TEAM TPS SUSPENSE ACCOUNT NAM FT26010WS6WVBNK,10/01/2026,\"-8000\",,MARKETING TEAM,TRF\n"
        "09/01/2026,BOL MOBILE PAYMENTS STAFF EXPENSE R E TPS SUSPENSE ACCOUNT NAM FT26009GWTM7BNK,09/01/2026,\"-42203\",,STAFF EXPENSE RE,TRF\n"
    ).encode("utf-8")


def _sample_csv_duplicate_amount() -> bytes:
    return (
        "Transactions Report\n"
        "Account Name:,IGNISHA EDUCATION LIMITED\n"
        "Account No:,0100017036593 - SBICKENX\n"
        "Currency:,KES - Kenyan Shilling\n"
        "Range From:,30/01/2026\n"
        "Range To:,06/02/2026\n"
        "Date,Description,Value Date,Debit,Credit,Account owner reference,Type\n"
        "10/01/2026,VENDOR PAYMENT FT26010WS6WVBNK,10/01/2026,\"-8000\",,MARKETING TEAM,TRF\n"
        "10/01/2026,VENDOR PAYMENT SECOND FT26010WS6WVBNK,10/01/2026,\"-8000\",,MARKETING TEAM,TRF\n"
    ).encode("utf-8")


class TestStanbicParser:
    def test_parse_stanbic_csv(self):
        metadata, rows, errors = parse_stanbic_csv(_sample_csv().decode("utf-8"))
        assert errors == []
        assert metadata["kv"]["Account No"].startswith("0100017036593")
        assert metadata["kv"]["Currency"].startswith("KES")
        assert len(rows) == 2
        assert rows[0]["Debit"].strip() == "-8000"
        assert rows[1]["Account owner reference"] == "STAFF EXPENSE RE"


class TestBankStatementImportFlow:
    async def test_import_endpoint_and_dedup(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        token = await _get_admin_token(db_session)

        resp1 = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        assert resp1.status_code == 201
        body1 = resp1.json()["data"]
        assert body1["rows_total"] == 2
        assert body1["transactions_created"] == 2
        assert body1["transactions_linked_existing"] == 0
        assert body1["range_from"] == "2026-01-09"
        assert body1["range_to"] == "2026-01-10"

        resp2 = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        assert resp2.status_code == 201
        body2 = resp2.json()["data"]
        assert body2["rows_total"] == 2
        assert body2["transactions_created"] == 0
        assert body2["transactions_linked_existing"] == 2

        imports = await client.get(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert imports.status_code == 200
        assert len(imports.json()["data"]) == 2

        detail = await client.get(
            f"/api/v1/bank-statements/imports/{body1['id']}?page=1&limit=50&only_unmatched=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["rows"]["total"] == 2

        detail_trf = await client.get(
            f"/api/v1/bank-statements/imports/{body1['id']}?page=1&limit=50&txn_type=TRF",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_trf.status_code == 200
        assert detail_trf.json()["data"]["rows"]["total"] == 2

        detail_chg = await client.get(
            f"/api/v1/bank-statements/imports/{body1['id']}?page=1&limit=50&txn_type=CHG",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_chg.status_code == 200
        assert detail_chg.json()["data"]["rows"]["total"] == 0

        # Global transactions endpoint (debits only) + filter by txn_type
        tx_all = await client.get(
            "/api/v1/bank-statements/transactions?date_from=2026-01-01&date_to=2026-01-31&page=1&limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert tx_all.status_code == 200
        assert tx_all.json()["data"]["total"] >= 2

        tx_trf = await client.get(
            "/api/v1/bank-statements/transactions?date_from=2026-01-01&date_to=2026-01-31&txn_type=TRF&page=1&limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert tx_trf.status_code == 200
        assert tx_trf.json()["data"]["total"] >= 2

        tx_chg = await client.get(
            "/api/v1/bank-statements/transactions?date_from=2026-01-01&date_to=2026-01-31&txn_type=CHG&page=1&limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert tx_chg.status_code == 200
        assert tx_chg.json()["data"]["total"] == 0

        types = await client.get(
            "/api/v1/bank-statements/txn-types?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert types.status_code == 200
        assert "TRF" in types.json()["data"]

    async def test_auto_match_procurement_and_payout(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        token = await _get_admin_token(db_session)

        # Create required procurement purpose + payment
        purpose = PaymentPurpose(name="Marketing", is_active=True)
        db_session.add(purpose)
        await db_session.flush()

        admin_user = await db_session.scalar(
            select(User).where(User.email == "bank_stmt_admin@test.com")
        )
        assert admin_user is not None
        created_by_id = admin_user.id

        payment = ProcurementPayment(
            payment_number="PP-2026-000001",
            purpose_id=purpose.id,
            payee_name="Marketing Team",
            payment_date=date(2026, 1, 10),
            amount=8000,
            payment_method=ProcurementPaymentMethod.BANK.value,
            reference_number="FT26010WS6WVBNK",
            created_by_id=created_by_id,
            company_paid=True,
        )
        db_session.add(payment)

        # Create payout
        auth = AuthService(db_session)
        employee = await auth.create_user(
            email="emp@test.com",
            password="Pass123!",
            full_name="Emp",
            role=UserRole.USER,
        )
        await db_session.flush()

        payout = CompensationPayout(
            payout_number="PAYOUT-2026-000001",
            employee_id=employee.id,
            payout_date=date(2026, 1, 9),
            amount=42203,
            payment_method="bank",
            reference_number="FT26009GWTM7BNK",
        )
        db_session.add(payout)
        await db_session.commit()

        # Import statement
        resp = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        import_id = resp.json()["data"]["id"]

        # Auto match
        m = await client.post(
            f"/api/v1/bank-statements/imports/{import_id}/auto-match",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert m.status_code == 200
        assert m.json()["data"]["matched"] >= 2

        matches = list((await db_session.execute(select(BankTransactionMatch))).scalars().all())
        assert any(x.procurement_payment_id == payment.id for x in matches)
        assert any(x.compensation_payout_id == payout.id for x in matches)

    async def test_auto_match_skips_already_used_procurement_payment(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        token = await _get_admin_token(db_session)

        purpose = PaymentPurpose(name="DupTest", is_active=True)
        db_session.add(purpose)
        await db_session.flush()

        admin_user = await db_session.scalar(
            select(User).where(User.email == "bank_stmt_admin@test.com")
        )
        assert admin_user is not None

        payment = ProcurementPayment(
            payment_number="PP-2026-000002",
            purpose_id=purpose.id,
            payee_name="Vendor",
            payment_date=date(2026, 1, 10),
            amount=8000,
            payment_method=ProcurementPaymentMethod.BANK.value,
            reference_number="FT26010WS6WVBNK",
            created_by_id=admin_user.id,
            company_paid=True,
        )
        db_session.add(payment)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv_duplicate_amount(), "text/csv")},
        )
        assert resp.status_code == 201
        import_id = resp.json()["data"]["id"]

        m = await client.post(
            f"/api/v1/bank-statements/imports/{import_id}/auto-match",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert m.status_code == 200
        body = m.json()["data"]
        assert body["matched"] == 1
        assert body["matched"] + body["ambiguous"] + body["no_candidates"] == 2

        match_count = int(
            (
                await db_session.execute(
                    select(func.count())
                    .select_from(BankTransactionMatch)
                    .where(BankTransactionMatch.procurement_payment_id == payment.id)
                )
            ).scalar_one()
        )
        assert match_count == 1

    async def test_accountant_cannot_upload_or_match(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        auth = AuthService(db_session)
        await auth.create_user(
            email="acc@test.com",
            password="Pass123!",
            full_name="Acc",
            role=UserRole.ACCOUNTANT,
        )
        await db_session.commit()
        _, token, _ = await auth.authenticate("acc@test.com", "Pass123!")

        resp = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        assert resp.status_code == 403

    async def test_reconciliation_ignore_range(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        token = await _get_admin_token(db_session)

        # Purpose + payment outside statement date range (statement is Jan 2026)
        purpose = PaymentPurpose(name="Outside", is_active=True)
        db_session.add(purpose)
        await db_session.flush()
        admin_user = await db_session.scalar(
            select(User).where(User.email == "bank_stmt_admin@test.com")
        )
        assert admin_user is not None

        payment = ProcurementPayment(
            payment_number="PP-2026-000999",
            purpose_id=purpose.id,
            payee_name="Outside Vendor",
            payment_date=date(2026, 3, 1),
            amount=8000,
            payment_method=ProcurementPaymentMethod.BANK.value,
            reference_number="OUTSIDE",
            created_by_id=admin_user.id,
            company_paid=True,
        )
        db_session.add(payment)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        import_id = resp.json()["data"]["id"]

        in_range = await client.get(
            f"/api/v1/bank-statements/imports/{import_id}/reconciliation",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert in_range.status_code == 200
        assert all(p["id"] != payment.id for p in in_range.json()["data"]["unmatched_procurement_payments"])

        ignored = await client.get(
            f"/api/v1/bank-statements/imports/{import_id}/reconciliation?ignore_range=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ignored.status_code == 200
        assert any(p["id"] == payment.id for p in ignored.json()["data"]["unmatched_procurement_payments"])

    async def test_cancelled_procurement_payment_excluded(
        self, client: AsyncClient, db_session: AsyncSession, storage_tmp_path
    ):
        token = await _get_admin_token(db_session)

        purpose = PaymentPurpose(name="CancelTest", is_active=True)
        db_session.add(purpose)
        await db_session.flush()
        admin_user = await db_session.scalar(
            select(User).where(User.email == "bank_stmt_admin@test.com")
        )
        assert admin_user is not None

        cancelled = ProcurementPayment(
            payment_number="PP-2026-000777",
            purpose_id=purpose.id,
            payee_name="Vendor",
            payment_date=date(2026, 1, 10),
            amount=8000,
            payment_method=ProcurementPaymentMethod.BANK.value,
            reference_number="FT26010WS6WVBNK",
            created_by_id=admin_user.id,
            company_paid=True,
            status=ProcurementPaymentStatus.CANCELLED.value,
        )
        db_session.add(cancelled)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/bank-statements/imports",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("stmt.csv", _sample_csv(), "text/csv")},
        )
        import_id = resp.json()["data"]["id"]

        summary = await client.get(
            f"/api/v1/bank-statements/imports/{import_id}/reconciliation",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert summary.status_code == 200
        assert all(
            p["id"] != cancelled.id
            for p in summary.json()["data"]["unmatched_procurement_payments"]
        )
