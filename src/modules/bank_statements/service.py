"""Services for importing bank statements and matching transactions to internal records."""

from __future__ import annotations

import csv
import hashlib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.attachments.service import get_attachment_content, save_attachment
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.bank_statements.models import (
    BankStatementImport,
    BankStatementImportTransaction,
    BankTransaction,
    BankTransactionMatch,
)
from src.modules.compensations.models import CompensationPayout
from src.modules.procurement.models import ProcurementPayment, ProcurementPaymentStatus


EXPECTED_STANBIC_COLUMNS = [
    "Date",
    "Description",
    "Value Date",
    "Debit",
    "Credit",
    "Account owner reference",
    "Type",
]

DEFAULT_CURRENCY = "KES"
DEFAULT_MATCH_WINDOW_DAYS = 3


def _parse_ddmmyyyy(value: str) -> date:
    try:
        day, month, year = value.strip().split("/")
        return date(int(year), int(month), int(day))
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"Invalid date: {value!r}") from exc


def _parse_decimal(value: str) -> Decimal:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        raise ValidationError("Empty amount")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid amount: {value!r}") from exc


def _canonical_text(value: str | None) -> str:
    return " ".join((value or "").strip().split()).lower()


def _compute_fingerprint(
    *,
    account_no: str,
    currency: str,
    transaction_date: date,
    value_date: date,
    amount: Decimal,
    description: str,
    account_owner_reference: str | None,
    txn_type: str | None,
) -> str:
    normalized = "\x1f".join(
        [
            _canonical_text(account_no),
            _canonical_text(currency),
            transaction_date.isoformat(),
            value_date.isoformat(),
            f"{amount.quantize(Decimal('0.01'))}",
            _canonical_text(description),
            _canonical_text(account_owner_reference),
            _canonical_text(txn_type),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_stanbic_csv(content: str) -> tuple[dict, list[dict], list[str]]:
    """
    Parse Stanbic "Transactions Report" CSV.

    Returns: (metadata, transaction_rows, errors)
    - metadata: dict with raw header lines + parsed key/values + range_from/to if present.
    - transaction_rows: list of raw row dicts (header->cell string).
    - errors: list of parse errors (non-fatal where possible).
    """
    errors: list[str] = []
    lines = [ln for ln in content.splitlines() if ln is not None]
    if not lines:
        raise ValidationError("Empty CSV")

    reader = csv.reader(lines)
    parsed_lines: list[list[str]] = list(reader)

    header_idx = None
    for idx, row in enumerate(parsed_lines):
        if not row:
            continue
        if row[: len(EXPECTED_STANBIC_COLUMNS)] == EXPECTED_STANBIC_COLUMNS:
            header_idx = idx
            break
        if row and row[0].strip() == "Date" and row == EXPECTED_STANBIC_COLUMNS:
            header_idx = idx
            break

    if header_idx is None:
        raise ValidationError(
            "Could not find transactions header row (expected Stanbic columns)"
        )

    header_raw_lines = lines[:header_idx]
    header_row = parsed_lines[header_idx]

    # Build metadata from pre-header lines.
    kv: dict[str, str] = {}
    for row in parsed_lines[:header_idx]:
        if len(row) >= 2 and row[0].strip().endswith(":"):
            key = row[0].strip()[:-1].strip()
            value = row[1].strip()
            if key:
                kv[key] = value

    metadata: dict = {
        "format": "stanbic_transactions_report",
        "raw_header_lines": header_raw_lines,
        "kv": kv,
        "csv_header": header_row,
    }

    # Parse transaction rows into raw dicts.
    transaction_rows: list[dict] = []
    for row in parsed_lines[header_idx + 1 :]:
        if not row or all(not (c or "").strip() for c in row):
            continue
        if len(row) < len(EXPECTED_STANBIC_COLUMNS):
            errors.append(f"Row has too few columns: {row!r}")
            continue
        row_dict = {EXPECTED_STANBIC_COLUMNS[i]: (row[i] or "") for i in range(len(EXPECTED_STANBIC_COLUMNS))}
        transaction_rows.append(row_dict)

    return metadata, transaction_rows, errors


class BankStatementService:
    async def import_stanbic_statement(
        self,
        db: AsyncSession,
        file: UploadFile,
        created_by_id: int,
    ) -> tuple[BankStatementImport, int, int, int, list[str]]:
        """Upload CSV to storage, parse, and persist import + transactions."""
        # Some browsers send CSV as octet-stream.
        if (file.content_type or "").strip() in ("", "application/octet-stream"):
            file.content_type = "text/csv"

        attachment = await save_attachment(db, file, created_by_id)
        await db.flush()

        raw_bytes = await get_attachment_content(attachment)
        try:
            content = raw_bytes.decode("utf-8-sig", errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("Failed to decode CSV as UTF-8") from exc

        metadata, raw_rows, parse_errors = parse_stanbic_csv(content)

        kv = metadata.get("kv") or {}
        account_no = (kv.get("Account No") or "").strip()
        currency = (kv.get("Currency") or DEFAULT_CURRENCY).split("-")[0].strip() or DEFAULT_CURRENCY

        if not account_no:
            parse_errors.append("Account No not found in header; using empty account_no for fingerprinting")

        statement_import = BankStatementImport(
            attachment_id=attachment.id,
            file_name=attachment.file_name,
            statement_metadata=metadata,
            created_by_id=created_by_id,
        )
        db.add(statement_import)
        await db.flush()
        await db.refresh(statement_import)

        rows_total = len(raw_rows)
        created = 0
        linked_existing = 0
        min_value_date: date | None = None
        max_value_date: date | None = None

        for idx, row in enumerate(raw_rows, start=1):
            try:
                transaction_date = _parse_ddmmyyyy(row["Date"])
                value_date = _parse_ddmmyyyy(row["Value Date"])
                description = (row.get("Description") or "").strip()
                debit_raw = (row.get("Debit") or "").strip() or None
                credit_raw = (row.get("Credit") or "").strip() or None
                account_owner_reference = (row.get("Account owner reference") or "").strip() or None
                txn_type = (row.get("Type") or "").strip() or None

                if debit_raw and credit_raw:
                    raise ValidationError("Both Debit and Credit are set")

                if debit_raw:
                    amount = _parse_decimal(debit_raw)
                elif credit_raw:
                    amount = _parse_decimal(credit_raw)
                else:
                    raise ValidationError("Neither Debit nor Credit is set")

                # Stanbic debit appears as negative in CSV; keep signed amount.
                amount = amount.quantize(Decimal("0.01"))

                fingerprint = _compute_fingerprint(
                    account_no=account_no,
                    currency=currency,
                    transaction_date=transaction_date,
                    value_date=value_date,
                    amount=amount,
                    description=description,
                    account_owner_reference=account_owner_reference,
                    txn_type=txn_type,
                )
            except ValidationError as exc:
                parse_errors.append(f"Row {idx}: {exc}")
                continue

            if min_value_date is None or value_date < min_value_date:
                min_value_date = value_date
            if max_value_date is None or value_date > max_value_date:
                max_value_date = value_date

            existing_txn = await db.scalar(
                select(BankTransaction).where(BankTransaction.fingerprint == fingerprint)
            )
            if existing_txn:
                bank_txn = existing_txn
                linked_existing += 1
            else:
                bank_txn = BankTransaction(
                    account_no=account_no or "",
                    currency=currency,
                    transaction_date=transaction_date,
                    value_date=value_date,
                    description=description,
                    debit_raw=debit_raw,
                    credit_raw=credit_raw,
                    amount=amount,
                    account_owner_reference=account_owner_reference,
                    txn_type=txn_type,
                    fingerprint=fingerprint,
                )
                db.add(bank_txn)
                await db.flush()
                created += 1

            link = BankStatementImportTransaction(
                import_id=statement_import.id,
                bank_transaction_id=bank_txn.id,
                row_index=idx,
                raw_row=row,
            )
            db.add(link)

        statement_import.range_from = min_value_date
        statement_import.range_to = max_value_date
        await db.flush()

        return statement_import, rows_total, created, linked_existing, parse_errors

    async def list_imports(self, db: AsyncSession) -> list[BankStatementImport]:
        result = await db.execute(
            select(BankStatementImport).order_by(BankStatementImport.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_transactions(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        txn_type: str | None,
        matched: bool | None,
        entity_type: str | None,
        search: str | None,
        page: int,
        limit: int,
    ) -> tuple[list[BankTransaction], int]:
        where = [BankTransaction.amount < 0]

        if date_from:
            where.append(BankTransaction.value_date >= date_from)
        if date_to:
            where.append(BankTransaction.value_date <= date_to)

        if txn_type and txn_type.strip():
            where.append(BankTransaction.txn_type == txn_type.strip())

        if matched is True:
            where.append(BankTransactionMatch.id.is_not(None))
        elif matched is False:
            where.append(BankTransactionMatch.id.is_(None))

        if entity_type == "procurement_payment":
            where.append(BankTransactionMatch.procurement_payment_id.is_not(None))
        elif entity_type == "compensation_payout":
            where.append(BankTransactionMatch.compensation_payout_id.is_not(None))

        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            where.append(
                or_(
                    func.lower(BankTransaction.description).like(s),
                    func.lower(func.coalesce(BankTransaction.account_owner_reference, "")).like(s),
                )
            )

        stmt = (
            select(BankTransaction)
            .outerjoin(
                BankTransactionMatch,
                BankTransactionMatch.bank_transaction_id == BankTransaction.id,
            )
            .options(
                selectinload(BankTransaction.match).selectinload(
                    BankTransactionMatch.procurement_payment
                ),
                selectinload(BankTransaction.match).selectinload(
                    BankTransactionMatch.compensation_payout
                ),
            )
            .where(and_(*where))
            .order_by(BankTransaction.value_date.desc(), BankTransaction.id.desc())
        )

        count_stmt = (
            select(func.count())
            .select_from(BankTransaction)
            .outerjoin(
                BankTransactionMatch,
                BankTransactionMatch.bank_transaction_id == BankTransaction.id,
            )
            .where(and_(*where))
        )

        total = int((await db.execute(count_stmt)).scalar_one())
        items = list((await db.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all())
        return items, total

    async def list_txn_types(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> list[str]:
        where = [BankTransaction.amount < 0, BankTransaction.txn_type.is_not(None)]
        if date_from:
            where.append(BankTransaction.value_date >= date_from)
        if date_to:
            where.append(BankTransaction.value_date <= date_to)

        stmt = (
            select(func.distinct(BankTransaction.txn_type))
            .where(and_(*where))
            .order_by(BankTransaction.txn_type.asc())
        )
        result = await db.execute(stmt)
        raw = [r[0] for r in result.all()]
        cleaned = []
        for t in raw:
            if not t:
                continue
            v = str(t).strip()
            if v:
                cleaned.append(v)
        return cleaned

    async def get_import(self, db: AsyncSession, import_id: int) -> BankStatementImport:
        statement_import = await db.scalar(
            select(BankStatementImport).where(BankStatementImport.id == import_id)
        )
        if not statement_import:
            raise NotFoundError("Bank statement import not found")
        return statement_import

    async def list_import_rows(
        self,
        db: AsyncSession,
        import_id: int,
        *,
        page: int,
        limit: int,
        only_unmatched: bool | None,
        txn_type: str | None,
    ) -> tuple[list[BankStatementImportTransaction], int]:
        await self.get_import(db, import_id)

        where = [BankStatementImportTransaction.import_id == import_id]
        if only_unmatched is True:
            where.append(BankTransactionMatch.id.is_(None))
        elif only_unmatched is False:
            where.append(BankTransactionMatch.id.is_not(None))

        if txn_type and txn_type.strip():
            where.append(BankTransaction.txn_type == txn_type.strip())

        stmt = (
            select(BankStatementImportTransaction)
            .join(
                BankTransaction,
                BankStatementImportTransaction.bank_transaction_id == BankTransaction.id,
            )
            .outerjoin(
                BankTransactionMatch,
                BankTransactionMatch.bank_transaction_id == BankTransaction.id,
            )
            .options(
                selectinload(BankStatementImportTransaction.bank_transaction)
                .selectinload(BankTransaction.match)
                .selectinload(BankTransactionMatch.procurement_payment),
                selectinload(BankStatementImportTransaction.bank_transaction)
                .selectinload(BankTransaction.match)
                .selectinload(BankTransactionMatch.compensation_payout),
            )
            .where(and_(*where))
            .where(BankTransaction.amount < 0)
            .order_by(
                BankTransaction.transaction_date.desc(),
                BankStatementImportTransaction.row_index.desc(),
            )
        )

        count_stmt = (
            select(func.count())
            .select_from(BankStatementImportTransaction)
            .join(
                BankTransaction,
                BankStatementImportTransaction.bank_transaction_id == BankTransaction.id,
            )
            .outerjoin(
                BankTransactionMatch,
                BankTransactionMatch.bank_transaction_id == BankTransaction.id,
            )
            .where(and_(*where))
            .where(BankTransaction.amount < 0)
        )

        total = int((await db.execute(count_stmt)).scalar_one())
        items = list((await db.execute(stmt.offset((page - 1) * limit).limit(limit))).scalars().all())
        return items, total

    async def _score_procurement_payment(
        self, txn: BankTransaction, payment: ProcurementPayment
    ) -> int:
        score = 0
        days = abs((payment.payment_date - txn.value_date).days)
        if days == 0:
            score += 3
        elif days == 1:
            score += 2
        elif days <= DEFAULT_MATCH_WINDOW_DAYS:
            score += 1

        haystack = f"{txn.description} {txn.account_owner_reference or ''}".lower()
        for needle in [
            payment.reference_number,
            payment.payment_number,
            payment.proof_text,
        ]:
            n = (needle or "").strip()
            if n and n.lower() in haystack:
                score += 2
                break
        return score

    async def _score_payout(self, txn: BankTransaction, payout: CompensationPayout) -> int:
        score = 0
        days = abs((payout.payout_date - txn.value_date).days)
        if days == 0:
            score += 3
        elif days == 1:
            score += 2
        elif days <= DEFAULT_MATCH_WINDOW_DAYS:
            score += 1

        haystack = f"{txn.description} {txn.account_owner_reference or ''}".lower()
        for needle in [payout.reference_number, payout.payout_number, payout.proof_text]:
            n = (needle or "").strip()
            if n and n.lower() in haystack:
                score += 2
                break
        return score

    async def auto_match_import(
        self,
        db: AsyncSession,
        import_id: int,
        *,
        matched_by_id: int | None,
        window_days: int = DEFAULT_MATCH_WINDOW_DAYS,
    ) -> tuple[int, int, int]:
        """Auto match unmatched debit transactions from a given import."""
        await self.get_import(db, import_id)

        window = window_days

        txns = list(
            (
                await db.execute(
                    select(BankTransaction)
                    .join(
                        BankStatementImportTransaction,
                        BankStatementImportTransaction.bank_transaction_id
                        == BankTransaction.id,
                    )
                    .outerjoin(
                        BankTransactionMatch,
                        BankTransactionMatch.bank_transaction_id == BankTransaction.id,
                    )
                    .where(BankStatementImportTransaction.import_id == import_id)
                    .where(BankTransactionMatch.id.is_(None))
                    .where(BankTransaction.amount < 0)
                )
            )
            .scalars()
            .all()
        )

        matched = 0
        ambiguous = 0
        no_candidates = 0

        for txn in txns:
            amount_abs = (txn.amount.copy_abs()).quantize(Decimal("0.01"))
            d0 = txn.value_date
            date_min = d0 - timedelta(days=window)
            date_max = d0 + timedelta(days=window)

            procurement_candidates = list(
                (
                    await db.execute(
                        select(ProcurementPayment)
                        .where(ProcurementPayment.company_paid.is_(True))
                        .where(
                            ProcurementPayment.status
                            == ProcurementPaymentStatus.POSTED.value
                        )
                        .where(ProcurementPayment.amount == amount_abs)
                        .where(ProcurementPayment.payment_date.between(date_min, date_max))
                    )
                )
                .scalars()
                .all()
            )

            payout_candidates = list(
                (
                    await db.execute(
                        select(CompensationPayout)
                        .where(CompensationPayout.amount == amount_abs)
                        .where(CompensationPayout.payout_date.between(date_min, date_max))
                    )
                )
                .scalars()
                .all()
            )

            scored: list[tuple[int, str, int]] = []
            for p in procurement_candidates:
                scored.append((await self._score_procurement_payment(txn, p), "procurement", p.id))
            for p in payout_candidates:
                scored.append((await self._score_payout(txn, p), "payout", p.id))

            if not scored:
                no_candidates += 1
                continue

            scored.sort(key=lambda x: (x[0], x[2]), reverse=True)
            best = scored[0]
            second = scored[1] if len(scored) > 1 else None

            if second and best[0] == second[0]:
                ambiguous += 1
                continue

            if best[0] <= 0:
                # Not confident enough.
                ambiguous += 1
                continue

            match = BankTransactionMatch(
                bank_transaction_id=txn.id,
                procurement_payment_id=best[2] if best[1] == "procurement" else None,
                compensation_payout_id=best[2] if best[1] == "payout" else None,
                match_method="auto",
                confidence=Decimal(str(best[0])),
                matched_by_id=matched_by_id,
            )
            db.add(match)
            matched += 1

        return matched, ambiguous, no_candidates

    async def manual_match(
        self,
        db: AsyncSession,
        bank_transaction_id: int,
        *,
        entity_type: str,
        entity_id: int,
        matched_by_id: int,
    ) -> BankTransactionMatch:
        txn = await db.scalar(select(BankTransaction).where(BankTransaction.id == bank_transaction_id))
        if not txn:
            raise NotFoundError("Bank transaction not found")

        existing = await db.scalar(
            select(BankTransactionMatch).where(
                BankTransactionMatch.bank_transaction_id == bank_transaction_id
            )
        )
        if existing:
            raise ValidationError("Transaction is already matched")

        if entity_type == "procurement_payment":
            payment = await db.scalar(
                select(ProcurementPayment).where(ProcurementPayment.id == entity_id)
            )
            if not payment:
                raise NotFoundError("Procurement payment not found")
            if payment.company_paid is not True:
                raise ValidationError("Procurement payment is not marked as company paid")
            if payment.status == ProcurementPaymentStatus.CANCELLED.value:
                raise ValidationError("Procurement payment is cancelled")
            if payment.amount.quantize(Decimal("0.01")) != txn.amount.copy_abs().quantize(
                Decimal("0.01")
            ):
                raise ValidationError("Amount mismatch")
            match = BankTransactionMatch(
                bank_transaction_id=bank_transaction_id,
                procurement_payment_id=payment.id,
                compensation_payout_id=None,
                match_method="manual",
                confidence=Decimal("10.00"),
                matched_by_id=matched_by_id,
            )
        elif entity_type == "compensation_payout":
            payout = await db.scalar(
                select(CompensationPayout).where(CompensationPayout.id == entity_id)
            )
            if not payout:
                raise NotFoundError("Compensation payout not found")
            if payout.amount.quantize(Decimal("0.01")) != txn.amount.copy_abs().quantize(
                Decimal("0.01")
            ):
                raise ValidationError("Amount mismatch")
            match = BankTransactionMatch(
                bank_transaction_id=bank_transaction_id,
                procurement_payment_id=None,
                compensation_payout_id=payout.id,
                match_method="manual",
                confidence=Decimal("10.00"),
                matched_by_id=matched_by_id,
            )
        else:
            raise ValidationError("Invalid entity_type")

        db.add(match)
        await db.flush()
        await db.refresh(match)
        return match

    async def unmatch(self, db: AsyncSession, bank_transaction_id: int) -> None:
        match = await db.scalar(
            select(BankTransactionMatch).where(
                BankTransactionMatch.bank_transaction_id == bank_transaction_id
            )
        )
        if not match:
            raise NotFoundError("Match not found")
        await db.delete(match)

    async def reconciliation_summary_for_import(
        self, db: AsyncSession, import_id: int, *, ignore_range: bool = False
    ) -> tuple[date | None, date | None, int, list[ProcurementPayment], list[CompensationPayout]]:
        statement_import = await self.get_import(db, import_id)

        date_from = statement_import.range_from
        date_to = statement_import.range_to
        if date_from is None or date_to is None:
            minmax = await db.execute(
                select(func.min(BankTransaction.value_date), func.max(BankTransaction.value_date))
                .select_from(BankStatementImportTransaction)
                .join(
                    BankTransaction,
                    BankStatementImportTransaction.bank_transaction_id == BankTransaction.id,
                )
                .where(BankStatementImportTransaction.import_id == import_id)
            )
            date_from, date_to = minmax.one()
            statement_import.range_from = date_from
            statement_import.range_to = date_to
            await db.flush()

        unmatched_transactions = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(BankStatementImportTransaction)
                    .join(
                        BankTransaction,
                        BankStatementImportTransaction.bank_transaction_id
                        == BankTransaction.id,
                    )
                    .outerjoin(
                        BankTransactionMatch,
                        BankTransactionMatch.bank_transaction_id == BankTransaction.id,
                    )
                    .where(BankStatementImportTransaction.import_id == import_id)
                    .where(BankTransactionMatch.id.is_(None))
                    .where(BankTransaction.amount < 0)
                )
            ).scalar_one()
        )

        # Unmatched procurement payments / payouts within statement range (if available).
        proc_where = [
            ProcurementPayment.company_paid.is_(True),
            ProcurementPayment.status == ProcurementPaymentStatus.POSTED.value,
            ~ProcurementPayment.id.in_(
                select(BankTransactionMatch.procurement_payment_id).where(
                    BankTransactionMatch.procurement_payment_id.is_not(None)
                )
            ),
        ]
        payout_where = [
            ~CompensationPayout.id.in_(
                select(BankTransactionMatch.compensation_payout_id).where(
                    BankTransactionMatch.compensation_payout_id.is_not(None)
                )
            )
        ]

        if not ignore_range and date_from and date_to:
            proc_where.append(ProcurementPayment.payment_date.between(date_from, date_to))
            payout_where.append(CompensationPayout.payout_date.between(date_from, date_to))

        unmatched_proc = list((await db.execute(select(ProcurementPayment).where(and_(*proc_where)).order_by(ProcurementPayment.payment_date.desc()))).scalars().all())
        unmatched_payouts = list((await db.execute(select(CompensationPayout).where(and_(*payout_where)).order_by(CompensationPayout.payout_date.desc()))).scalars().all())

        return date_from, date_to, unmatched_transactions, unmatched_proc, unmatched_payouts
