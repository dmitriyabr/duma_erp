"""API endpoints for student withdrawal settlements."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.dependencies import require_roles
from src.core.auth.models import User, UserRole
from src.core.database.session import get_db
from src.modules.withdrawals.schemas import (
    BillingAccountWithdrawalSettlementCreate,
    BillingAccountWithdrawalSettlementPreviewRequest,
    InvoiceAdjustmentResponse,
    WithdrawalSettlementCreate,
    WithdrawalSettlementLineResponse,
    WithdrawalSettlementPreview,
    WithdrawalSettlementPreviewRequest,
    WithdrawalSettlementResponse,
    WithdrawalSettlementStudentResponse,
)
from src.modules.withdrawals.service import WithdrawalSettlementService
from src.shared.schemas.base import ApiResponse

router = APIRouter(tags=["Withdrawal Settlements"])


def _settlement_line_to_response(line) -> WithdrawalSettlementLineResponse:
    return WithdrawalSettlementLineResponse(
        id=line.id,
        settlement_id=line.settlement_id,
        invoice_id=line.invoice_id,
        invoice_number=line.invoice.invoice_number if line.invoice else None,
        invoice_line_id=line.invoice_line_id,
        action=line.action,
        amount=line.amount,
        notes=line.notes,
        created_at=line.created_at,
    )


def _invoice_adjustment_to_response(adjustment) -> InvoiceAdjustmentResponse:
    return InvoiceAdjustmentResponse(
        id=adjustment.id,
        adjustment_number=adjustment.adjustment_number,
        invoice_id=adjustment.invoice_id,
        invoice_number=adjustment.invoice.invoice_number if adjustment.invoice else None,
        invoice_line_id=adjustment.invoice_line_id,
        settlement_id=adjustment.settlement_id,
        adjustment_type=adjustment.adjustment_type,
        amount=adjustment.amount,
        reason=adjustment.reason,
        notes=adjustment.notes,
        created_by_id=adjustment.created_by_id,
        created_at=adjustment.created_at,
    )


def _settlement_to_response(settlement) -> WithdrawalSettlementResponse:
    return WithdrawalSettlementResponse(
        id=settlement.id,
        settlement_number=settlement.settlement_number,
        student_id=settlement.student_id,
        student_name=settlement.student.full_name if settlement.student else None,
        students=[
            WithdrawalSettlementStudentResponse(
                student_id=item.student_id,
                student_name=item.student.full_name if item.student else None,
                status_before=item.status_before,
                status_after=item.status_after,
            )
            for item in getattr(settlement, "students", [])
        ],
        billing_account_id=settlement.billing_account_id,
        refund_id=settlement.refund_id,
        refund_number=settlement.refund.refund_number if settlement.refund else None,
        settlement_date=settlement.settlement_date,
        status=settlement.status,
        retained_amount=settlement.retained_amount,
        deduction_amount=settlement.deduction_amount,
        write_off_amount=settlement.write_off_amount,
        cancelled_amount=settlement.cancelled_amount,
        refund_amount=settlement.refund_amount,
        remaining_collectible_debt=settlement.remaining_collectible_debt,
        reason=settlement.reason,
        notes=settlement.notes,
        proof_attachment_id=settlement.proof_attachment_id,
        created_by_id=settlement.created_by_id,
        posted_at=settlement.posted_at,
        created_at=settlement.created_at,
        updated_at=settlement.updated_at,
        lines=[_settlement_line_to_response(line) for line in getattr(settlement, "lines", [])],
        invoice_adjustments=[
            _invoice_adjustment_to_response(adjustment)
            for adjustment in getattr(settlement, "invoice_adjustments", [])
        ],
    )


@router.post(
    "/billing-accounts/{account_id}/withdrawal-settlements/preview",
    response_model=ApiResponse[WithdrawalSettlementPreview],
)
async def preview_billing_account_withdrawal_settlement(
    account_id: int,
    data: BillingAccountWithdrawalSettlementPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = WithdrawalSettlementService(db)
    preview = await service.preview_billing_account_settlement(account_id, data)
    return ApiResponse(data=preview)


@router.post(
    "/billing-accounts/{account_id}/withdrawal-settlements",
    response_model=ApiResponse[WithdrawalSettlementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_account_withdrawal_settlement(
    account_id: int,
    data: BillingAccountWithdrawalSettlementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = WithdrawalSettlementService(db)
    settlement = await service.create_billing_account_settlement(
        account_id,
        data,
        current_user.id,
    )
    return ApiResponse(
        data=_settlement_to_response(settlement),
        message="Withdrawal settlement posted successfully",
    )


@router.get(
    "/billing-accounts/{account_id}/withdrawal-settlements",
    response_model=ApiResponse[list[WithdrawalSettlementResponse]],
)
async def list_billing_account_withdrawal_settlements(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = WithdrawalSettlementService(db)
    settlements = await service.list_billing_account_settlements(account_id)
    return ApiResponse(data=[_settlement_to_response(settlement) for settlement in settlements])


@router.post(
    "/students/{student_id}/withdrawal-settlements/preview",
    response_model=ApiResponse[WithdrawalSettlementPreview],
)
async def preview_student_withdrawal_settlement(
    student_id: int,
    data: WithdrawalSettlementPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = WithdrawalSettlementService(db)
    preview = await service.preview_settlement(student_id, data)
    return ApiResponse(data=preview)


@router.post(
    "/students/{student_id}/withdrawal-settlements",
    response_model=ApiResponse[WithdrawalSettlementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_student_withdrawal_settlement(
    student_id: int,
    data: WithdrawalSettlementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
):
    service = WithdrawalSettlementService(db)
    settlement = await service.create_settlement(student_id, data, current_user.id)
    return ApiResponse(
        data=_settlement_to_response(settlement),
        message="Withdrawal settlement posted successfully",
    )


@router.get(
    "/students/{student_id}/withdrawal-settlements",
    response_model=ApiResponse[list[WithdrawalSettlementResponse]],
)
async def list_student_withdrawal_settlements(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = WithdrawalSettlementService(db)
    settlements = await service.list_student_settlements(student_id)
    return ApiResponse(data=[_settlement_to_response(settlement) for settlement in settlements])


@router.get(
    "/withdrawal-settlements/{settlement_id}",
    response_model=ApiResponse[WithdrawalSettlementResponse],
)
async def get_withdrawal_settlement(
    settlement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTANT)
    ),
):
    service = WithdrawalSettlementService(db)
    settlement = await service.get_settlement_by_id(settlement_id)
    return ApiResponse(data=_settlement_to_response(settlement))
