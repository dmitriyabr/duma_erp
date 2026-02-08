"""API endpoints for bank statement imports and reconciliation."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.bank_statements.schemas import (
    AutoMatchResult,
    BankStatementImportDetail,
    BankStatementImportListItem,
    BankStatementImportSummary,
    BankTransactionMatchInfo,
    BankTransactionResponse,
    BankStatementImportTransactionResponse,
    ImportReconciliationSummary,
    ManualMatchRequest,
    UnmatchedCompensationPayout,
    UnmatchedProcurementPayment,
)
from src.modules.bank_statements.service import BankStatementService
from src.modules.bank_statements.models import BankTransactionMatch
from src.modules.procurement.models import ProcurementPayment
from src.modules.compensations.models import CompensationPayout
from src.shared.schemas.base import ApiResponse, PaginatedResponse


router = APIRouter(prefix="/bank-statements", tags=["Bank Statements"])


BankReadRole = Depends(
    require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
)
BankWriteRole = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))


@router.post(
    "/imports",
    response_model=ApiResponse[BankStatementImportSummary],
    status_code=status.HTTP_201_CREATED,
)
async def import_bank_statement(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = BankWriteRole,
):
    service = BankStatementService()
    statement_import, rows_total, created, linked_existing, errors = (
        await service.import_stanbic_statement(
        db, file=file, created_by_id=current_user.id
        )
    )
    await db.commit()
    return ApiResponse(
        success=True,
        message="Bank statement imported",
        data=BankStatementImportSummary(
            id=statement_import.id,
            attachment_id=statement_import.attachment_id,
            file_name=statement_import.file_name,
            metadata=statement_import.statement_metadata,
            range_from=statement_import.range_from,
            range_to=statement_import.range_to,
            created_by_id=statement_import.created_by_id,
            created_at=statement_import.created_at,
            rows_total=rows_total,
            transactions_created=created,
            transactions_linked_existing=linked_existing,
            errors=errors,
        ),
    )


@router.get("/imports", response_model=ApiResponse[list[BankStatementImportListItem]])
async def list_bank_statement_imports(
    db: AsyncSession = Depends(get_db),
    current_user: User = BankReadRole,
):
    service = BankStatementService()
    imports = await service.list_imports(db)
    return ApiResponse(
        data=[
            BankStatementImportListItem(
                id=i.id,
                attachment_id=i.attachment_id,
                file_name=i.file_name,
                range_from=i.range_from,
                range_to=i.range_to,
                created_by_id=i.created_by_id,
                created_at=i.created_at,
            )
            for i in imports
        ]
    )


@router.get("/imports/{import_id}", response_model=ApiResponse[BankStatementImportDetail])
async def get_bank_statement_import(
    import_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    only_unmatched: bool | None = Query(None),
    txn_type: str | None = Query(None, description="Filter statement rows by txn_type (Type column)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = BankReadRole,
):
    service = BankStatementService()
    statement_import = await service.get_import(db, import_id)
    items, total = await service.list_import_rows(
        db,
        import_id,
        page=page,
        limit=limit,
        only_unmatched=only_unmatched,
        txn_type=txn_type,
    )

    # Preload matches in one query (avoid N+1).
    # SQLAlchemy relationship is lazy; build match info by querying match table.
    # For simplicity, reuse relationship if already available; otherwise it will lazy-load.

    rows: list[BankStatementImportTransactionResponse] = []
    for row in items:
        t = row.bank_transaction
        match_info = None
        if t.match:
            if t.match.procurement_payment_id:
                payment: ProcurementPayment | None = t.match.procurement_payment
                payment_number = payment.payment_number if payment else str(t.match.procurement_payment_id)
                proof_attachment_id = payment.proof_attachment_id if payment else None
                match_info = BankTransactionMatchInfo(
                    id=t.match.id,
                    entity_type="procurement_payment",
                    entity_id=t.match.procurement_payment_id,
                    entity_number=payment_number,
                    match_method=t.match.match_method,
                    confidence=t.match.confidence,
                    matched_at=t.match.matched_at,
                    proof_attachment_id=proof_attachment_id,
                )
            elif t.match.compensation_payout_id:
                payout: CompensationPayout | None = t.match.compensation_payout
                payout_number = payout.payout_number if payout else str(t.match.compensation_payout_id)
                proof_attachment_id = payout.proof_attachment_id if payout else None
                match_info = BankTransactionMatchInfo(
                    id=t.match.id,
                    entity_type="compensation_payout",
                    entity_id=t.match.compensation_payout_id,
                    entity_number=payout_number,
                    match_method=t.match.match_method,
                    confidence=t.match.confidence,
                    matched_at=t.match.matched_at,
                    proof_attachment_id=proof_attachment_id,
                )
        rows.append(
            BankStatementImportTransactionResponse(
                id=row.id,
                row_index=row.row_index,
                raw_row=row.raw_row,
                transaction=BankTransactionResponse(
                    id=t.id,
                    account_no=t.account_no,
                    currency=t.currency,
                    transaction_date=t.transaction_date,
                    value_date=t.value_date,
                    description=t.description,
                    debit_raw=t.debit_raw,
                    credit_raw=t.credit_raw,
                    amount=t.amount,
                    account_owner_reference=t.account_owner_reference,
                    txn_type=t.txn_type,
                    match=match_info,
                ),
            )
        )

    return ApiResponse(
        data=BankStatementImportDetail(
            statement_import=BankStatementImportListItem(
                id=statement_import.id,
                attachment_id=statement_import.attachment_id,
                file_name=statement_import.file_name,
                range_from=statement_import.range_from,
                range_to=statement_import.range_to,
                created_by_id=statement_import.created_by_id,
                created_at=statement_import.created_at,
            ),
            rows=PaginatedResponse.create(rows, total, page, limit),
        )
    )


@router.get(
    "/transactions",
    response_model=ApiResponse[PaginatedResponse[BankTransactionResponse]],
)
async def list_bank_transactions(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    txn_type: str | None = Query(None, description="Transaction type code from statement (e.g. TRF/CHG/TAX)"),
    matched: bool | None = Query(None, description="Filter by matched status"),
    entity_type: str | None = Query(
        None, description="procurement_payment | compensation_payout"
    ),
    search: str | None = Query(None, description="Search in description/reference"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = BankReadRole,
):
    service = BankStatementService()
    items, total = await service.list_transactions(
        db,
        date_from=date_from,
        date_to=date_to,
        txn_type=txn_type,
        matched=matched,
        entity_type=entity_type,
        search=search,
        page=page,
        limit=limit,
    )

    txns: list[BankTransactionResponse] = []
    for t in items:
        match_info = None
        if t.match:
            if t.match.procurement_payment_id:
                payment: ProcurementPayment | None = t.match.procurement_payment
                payment_number = payment.payment_number if payment else str(t.match.procurement_payment_id)
                proof_attachment_id = payment.proof_attachment_id if payment else None
                match_info = BankTransactionMatchInfo(
                    id=t.match.id,
                    entity_type="procurement_payment",
                    entity_id=t.match.procurement_payment_id,
                    entity_number=payment_number,
                    match_method=t.match.match_method,
                    confidence=t.match.confidence,
                    matched_at=t.match.matched_at,
                    proof_attachment_id=proof_attachment_id,
                )
            elif t.match.compensation_payout_id:
                payout: CompensationPayout | None = t.match.compensation_payout
                payout_number = payout.payout_number if payout else str(t.match.compensation_payout_id)
                proof_attachment_id = payout.proof_attachment_id if payout else None
                match_info = BankTransactionMatchInfo(
                    id=t.match.id,
                    entity_type="compensation_payout",
                    entity_id=t.match.compensation_payout_id,
                    entity_number=payout_number,
                    match_method=t.match.match_method,
                    confidence=t.match.confidence,
                    matched_at=t.match.matched_at,
                    proof_attachment_id=proof_attachment_id,
                )
        txns.append(
            BankTransactionResponse(
                id=t.id,
                account_no=t.account_no,
                currency=t.currency,
                transaction_date=t.transaction_date,
                value_date=t.value_date,
                description=t.description,
                debit_raw=t.debit_raw,
                credit_raw=t.credit_raw,
                amount=t.amount,
                account_owner_reference=t.account_owner_reference,
                txn_type=t.txn_type,
                match=match_info,
            )
        )

    return ApiResponse(data=PaginatedResponse.create(txns, total, page, limit))


@router.get(
    "/txn-types",
    response_model=ApiResponse[list[str]],
)
async def list_bank_transaction_types(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = BankReadRole,
):
    """List distinct transaction types (Type column) for outgoing bank transactions."""
    service = BankStatementService()
    items = await service.list_txn_types(db, date_from=date_from, date_to=date_to)
    return ApiResponse(data=items)


@router.post(
    "/imports/{import_id}/auto-match",
    response_model=ApiResponse[AutoMatchResult],
)
async def auto_match_import(
    import_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BankWriteRole,
):
    service = BankStatementService()
    matched, ambiguous, no_candidates = await service.auto_match_import(
        db, import_id, matched_by_id=current_user.id
    )
    await db.commit()
    return ApiResponse(data=AutoMatchResult(matched=matched, ambiguous=ambiguous, no_candidates=no_candidates))


@router.post(
    "/transactions/{bank_transaction_id}/match",
    response_model=ApiResponse[BankTransactionMatchInfo],
)
async def manual_match_transaction(
    bank_transaction_id: int,
    body: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = BankWriteRole,
):
    service = BankStatementService()
    match = await service.manual_match(
        db,
        bank_transaction_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        matched_by_id=current_user.id,
    )
    await db.commit()

    match = await db.scalar(
        select(BankTransactionMatch)
        .where(BankTransactionMatch.id == match.id)
        .options(
            selectinload(BankTransactionMatch.procurement_payment),
            selectinload(BankTransactionMatch.compensation_payout),
        )
    )
    assert match is not None

    if match.procurement_payment_id:
        payment: ProcurementPayment | None = match.procurement_payment
        payment_number = payment.payment_number if payment else str(match.procurement_payment_id)
        proof_attachment_id = payment.proof_attachment_id if payment else None
        entity_type = "procurement_payment"
        entity_id = match.procurement_payment_id
        entity_number = payment_number
    else:
        payout: CompensationPayout | None = match.compensation_payout
        payout_number = payout.payout_number if payout else str(match.compensation_payout_id or 0)
        proof_attachment_id = payout.proof_attachment_id if payout else None
        entity_type = "compensation_payout"
        entity_id = match.compensation_payout_id or 0
        entity_number = payout_number
    return ApiResponse(
        data=BankTransactionMatchInfo(
            id=match.id,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=entity_id,
            entity_number=entity_number,
            match_method=match.match_method,
            confidence=match.confidence,
            matched_at=match.matched_at,
            proof_attachment_id=proof_attachment_id,
        )
    )


@router.delete("/transactions/{bank_transaction_id}/match", response_model=ApiResponse[dict])
async def unmatch_transaction(
    bank_transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = BankWriteRole,
):
    service = BankStatementService()
    await service.unmatch(db, bank_transaction_id)
    await db.commit()
    return ApiResponse(data={"ok": True})


@router.get(
    "/imports/{import_id}/reconciliation",
    response_model=ApiResponse[ImportReconciliationSummary],
)
async def get_import_reconciliation_summary(
    import_id: int,
    ignore_range: bool = Query(False, description="Ignore statement date range filters"),
    db: AsyncSession = Depends(get_db),
    current_user: User = BankReadRole,
):
    service = BankStatementService()
    date_from, date_to, unmatched_txns, unmatched_proc, unmatched_payouts = (
        await service.reconciliation_summary_for_import(db, import_id, ignore_range=ignore_range)
    )

    return ApiResponse(
        data=ImportReconciliationSummary(
            import_id=import_id,
            range_from=date_from,
            range_to=date_to,
            unmatched_transactions=unmatched_txns,
            unmatched_procurement_payments=[
                UnmatchedProcurementPayment(
                    id=p.id,
                    payment_number=p.payment_number,
                    payment_date=p.payment_date,
                    amount=p.amount,
                    payee_name=p.payee_name,
                    reference_number=p.reference_number,
                )
                for p in unmatched_proc
            ],
            unmatched_compensation_payouts=[
                UnmatchedCompensationPayout(
                    id=p.id,
                    payout_number=p.payout_number,
                    payout_date=p.payout_date,
                    amount=p.amount,
                    reference_number=p.reference_number,
                )
                for p in unmatched_payouts
            ],
        )
    )
