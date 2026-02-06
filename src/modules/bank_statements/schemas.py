"""Pydantic schemas for bank statement imports and reconciliation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from src.shared.schemas.base import BaseSchema, PaginatedResponse


MatchedEntityType = Literal["procurement_payment", "compensation_payout"]


class BankStatementImportListItem(BaseSchema):
    id: int
    attachment_id: int
    file_name: str
    range_from: date | None = None
    range_to: date | None = None
    created_by_id: int
    created_at: datetime


class BankStatementImportSummary(BaseSchema):
    id: int
    attachment_id: int
    file_name: str
    metadata: dict
    range_from: date | None = None
    range_to: date | None = None
    created_by_id: int
    created_at: datetime
    rows_total: int
    transactions_created: int
    transactions_linked_existing: int
    errors: list[str] = []


class BankTransactionMatchInfo(BaseSchema):
    id: int
    entity_type: MatchedEntityType
    entity_id: int
    entity_number: str
    match_method: str
    confidence: Decimal
    matched_at: datetime
    proof_attachment_id: int | None = None


class BankTransactionResponse(BaseSchema):
    id: int
    account_no: str
    currency: str
    transaction_date: date
    value_date: date
    description: str
    debit_raw: str | None
    credit_raw: str | None
    amount: Decimal
    account_owner_reference: str | None
    txn_type: str | None
    match: BankTransactionMatchInfo | None = None


class BankStatementImportTransactionResponse(BaseSchema):
    id: int
    row_index: int
    raw_row: dict
    transaction: BankTransactionResponse


class BankStatementImportDetail(BaseSchema):
    statement_import: BankStatementImportListItem
    rows: PaginatedResponse[BankStatementImportTransactionResponse]


class AutoMatchResult(BaseSchema):
    matched: int
    ambiguous: int
    no_candidates: int


class ManualMatchRequest(BaseSchema):
    entity_type: MatchedEntityType
    entity_id: int = Field(..., gt=0)

    @model_validator(mode="after")
    def _validate(self):
        # placeholder: future constraints can be added here
        return self


class UnmatchedProcurementPayment(BaseSchema):
    id: int
    payment_number: str
    payment_date: date
    amount: Decimal
    payee_name: str | None = None
    reference_number: str | None = None


class UnmatchedCompensationPayout(BaseSchema):
    id: int
    payout_number: str
    payout_date: date
    amount: Decimal
    reference_number: str | None = None


class ImportReconciliationSummary(BaseSchema):
    import_id: int
    range_from: date | None = None
    range_to: date | None = None
    unmatched_transactions: int
    unmatched_procurement_payments: list[UnmatchedProcurementPayment]
    unmatched_compensation_payouts: list[UnmatchedCompensationPayout]
