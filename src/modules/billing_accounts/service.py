"""Service layer for shared billing accounts."""

from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.billing_accounts.models import BillingAccount
from src.modules.billing_accounts.schemas import (
    BillingAccountAddMembersRequest,
    BillingAccountChildCreate,
    BillingAccountCreate,
    BillingAccountDetail,
    BillingAccountListFilters,
    BillingAccountMemberResponse,
    BillingAccountSummary,
    BillingAccountUpdate,
)
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.payments.models import (
    CreditAllocation,
    Payment,
    PaymentRefund,
    PaymentRefundSource,
    PaymentStatus,
)
from src.modules.students.models import Student
from src.modules.students.schemas import StudentCreate
from src.shared.utils.money import round_money


class BillingAccountService:
    """Manage billing owners that can span multiple students."""

    _BILLABLE_INVOICE_STATUSES = (
        InvoiceStatus.ISSUED.value,
        InvoiceStatus.PARTIALLY_PAID.value,
        InvoiceStatus.PAID.value,
    )
    _OPEN_INVOICE_STATUSES = (
        InvoiceStatus.ISSUED.value,
        InvoiceStatus.PARTIALLY_PAID.value,
    )

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def ensure_student_billing_account(self, student_id: int) -> BillingAccount:
        """Guarantee that a student has a billing account."""
        student = await self._get_student(student_id)
        if student.billing_account_id:
            return await self.get_billing_account_by_id(student.billing_account_id)

        number_gen = DocumentNumberGenerator(self.db)
        account = BillingAccount(
            account_number=await number_gen.generate("FAM"),
            display_name=student.full_name,
            primary_guardian_name=student.guardian_name,
            primary_guardian_phone=student.guardian_phone,
            primary_guardian_email=student.guardian_email,
            created_by_id=student.created_by_id,
        )
        self.db.add(account)
        await self.db.flush()

        student.billing_account_id = account.id
        student.cached_credit_balance = Decimal("0.00")
        await self.db.flush()

        await self.audit.log(
            action="billing_account.create",
            entity_type="BillingAccount",
            entity_id=account.id,
            entity_identifier=account.account_number,
            user_id=student.created_by_id,
            new_values={
                "display_name": account.display_name,
                "student_id": student.id,
            },
        )
        return account

    async def list_billing_accounts(
        self, filters: BillingAccountListFilters
    ) -> tuple[list[BillingAccountSummary], int]:
        """List billing accounts with balances and member counts."""
        query = (
            select(BillingAccount)
            .options(selectinload(BillingAccount.students).selectinload(Student.grade))
            .order_by(BillingAccount.updated_at.desc(), BillingAccount.id.desc())
        )

        if filters.search and filters.search.strip():
            search_term = f"%{filters.search.strip()}%"
            query = (
                query.outerjoin(Student, Student.billing_account_id == BillingAccount.id)
                .where(
                    or_(
                        BillingAccount.account_number.ilike(search_term),
                        BillingAccount.display_name.ilike(search_term),
                        BillingAccount.primary_guardian_name.ilike(search_term),
                        BillingAccount.primary_guardian_phone.ilike(search_term),
                        Student.first_name.ilike(search_term),
                        Student.last_name.ilike(search_term),
                        Student.student_number.ilike(search_term),
                    )
                )
                .distinct()
            )

        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        accounts = list((await self.db.execute(query)).scalars().unique().all())
        return await self._build_summaries(accounts), total

    async def get_parent_balances_export(self, search: str | None = None) -> dict:
        """Build all-parent balance rows for export."""
        query = (
            select(BillingAccount)
            .options(selectinload(BillingAccount.students).selectinload(Student.grade))
            .order_by(BillingAccount.display_name, BillingAccount.id)
        )
        if search and search.strip():
            search_term = f"%{search.strip()}%"
            query = (
                query.outerjoin(Student, Student.billing_account_id == BillingAccount.id)
                .where(
                    or_(
                        BillingAccount.account_number.ilike(search_term),
                        BillingAccount.display_name.ilike(search_term),
                        BillingAccount.primary_guardian_name.ilike(search_term),
                        BillingAccount.primary_guardian_phone.ilike(search_term),
                        Student.first_name.ilike(search_term),
                        Student.last_name.ilike(search_term),
                        Student.student_number.ilike(search_term),
                    )
                )
                .distinct()
            )

        accounts = list((await self.db.execute(query)).scalars().unique().all())
        amount_map = await self._get_balance_export_amount_map([account.id for account in accounts])
        rows = [
            self._build_parent_balance_export_row(account, amount_map.get(account.id, {}))
            for account in accounts
        ]
        summary_keys = [
            "total_payments",
            "total_refunds",
            "net_paid",
            "paid_to_invoices",
            "available_credit",
            "total_invoiced",
            "invoice_adjustments",
            "outstanding_debt",
            "amount_to_pay_now",
            "credit_after_debts",
            "net_balance",
        ]
        summary = {"account_count": len(rows)}
        for key in summary_keys:
            summary[key] = round_money(
                sum((row.get(key, Decimal("0.00")) for row in rows), Decimal("0.00"))
            )
        return {
            "generated_on": date.today(),
            "search": search.strip() if search and search.strip() else None,
            "rows": rows,
            "summary": summary,
        }

    async def get_billing_account_detail(self, account_id: int) -> BillingAccountDetail:
        """Get one billing account with member roster and totals."""
        account = await self.get_billing_account_by_id(account_id)
        summary = await self._build_summary(account)
        return BillingAccountDetail(
            **summary.model_dump(),
            members=[
                BillingAccountMemberResponse(
                    id=student.id,
                    student_id=student.id,
                    student_number=student.student_number,
                    student_name=student.full_name,
                    grade_name=student.grade.name if student.grade else None,
                    guardian_name=student.guardian_name,
                    guardian_phone=student.guardian_phone,
                    status=student.status,
                )
                for student in account.students
            ],
        )

    async def get_parent_balance_export(self, account_id: int) -> dict:
        """Build detailed parent balance export data for one billing account."""
        account = await self.get_billing_account_by_id(account_id)
        amount_map = await self._get_balance_export_amount_map([account.id])
        summary_row = self._build_parent_balance_export_row(
            account,
            amount_map.get(account.id, {}),
        )

        invoices_result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.billing_account_id == account.id,
                Invoice.status.in_(self._BILLABLE_INVOICE_STATUSES),
            )
            .options(selectinload(Invoice.student), selectinload(Invoice.term))
            .order_by(Invoice.term_id, Invoice.due_date, Invoice.invoice_number, Invoice.id)
        )
        invoices = list(invoices_result.scalars().unique().all())

        payments_result = await self.db.execute(
            select(Payment)
            .where(Payment.billing_account_id == account.id)
            .options(selectinload(Payment.student))
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc(), Payment.id.desc())
        )
        payments = list(payments_result.scalars().unique().all())
        refunded_by_payment = await self._get_payment_refunded_amount_map(
            [payment.id for payment in payments]
        )

        refunds_result = await self.db.execute(
            select(PaymentRefund)
            .where(PaymentRefund.billing_account_id == account.id)
            .order_by(PaymentRefund.refund_date.desc(), PaymentRefund.created_at.desc())
        )
        refunds = list(refunds_result.scalars().all())

        students = [
            {
                "student_number": student.student_number,
                "student_name": student.full_name,
                "grade_name": student.grade.name if student.grade else None,
                "guardian_name": student.guardian_name,
                "guardian_phone": student.guardian_phone,
                "status": student.status,
            }
            for student in account.students
        ]

        return {
            "generated_on": date.today(),
            "account": {
                "id": account.id,
                "account_number": account.account_number,
                "display_name": account.display_name,
                "primary_guardian_name": account.primary_guardian_name,
                "primary_guardian_phone": account.primary_guardian_phone,
                "primary_guardian_email": account.primary_guardian_email,
                "students": self._student_roster(account),
            },
            "summary": summary_row,
            "students": students,
            "invoices": [
                {
                    "invoice_number": invoice.invoice_number,
                    "student_name": invoice.student.full_name if invoice.student else None,
                    "term_id": invoice.term_id,
                    "term_name": invoice.term.display_name if invoice.term else None,
                    "invoice_type": invoice.invoice_type,
                    "status": invoice.status,
                    "issue_date": invoice.issue_date,
                    "due_date": invoice.due_date,
                    "total": round_money(invoice.total),
                    "paid_total": round_money(invoice.paid_total),
                    "adjustment_total": round_money(
                        getattr(invoice, "adjustment_total", None) or Decimal("0.00")
                    ),
                    "amount_due": round_money(invoice.amount_due),
                }
                for invoice in invoices
            ],
            "payments": [
                {
                    "payment_date": payment.payment_date,
                    "payment_number": payment.payment_number,
                    "receipt_number": payment.receipt_number,
                    "student_name": payment.student.full_name if payment.student else None,
                    "payment_method": payment.payment_method,
                    "reference": payment.reference,
                    "status": payment.status,
                    "amount": round_money(payment.amount),
                    "refunded_amount": refunded_by_payment.get(payment.id, Decimal("0.00")),
                    "net_amount": round_money(
                        payment.amount - refunded_by_payment.get(payment.id, Decimal("0.00"))
                    ),
                }
                for payment in payments
            ],
            "refunds": [
                {
                    "refund_date": refund.refund_date,
                    "refund_number": refund.refund_number,
                    "refund_method": refund.refund_method,
                    "reference_number": refund.reference_number,
                    "reason": refund.reason,
                    "amount": round_money(refund.amount),
                }
                for refund in refunds
            ],
        }

    async def get_billing_account_by_id(self, account_id: int) -> BillingAccount:
        """Load account with members."""
        result = await self.db.execute(
            select(BillingAccount)
            .where(BillingAccount.id == account_id)
            .options(selectinload(BillingAccount.students).selectinload(Student.grade))
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Billing account with id {account_id} not found")
        return account

    async def create_family_account(
        self, data: BillingAccountCreate, created_by_id: int
    ) -> BillingAccount:
        """Create a new billing account and move selected students into it."""
        students = await self._get_students(data.student_ids) if data.student_ids else []

        number_gen = DocumentNumberGenerator(self.db)
        account = BillingAccount(
            account_number=await number_gen.generate("FAM"),
            display_name=data.display_name.strip(),
            primary_guardian_name=data.primary_guardian_name,
            primary_guardian_phone=data.primary_guardian_phone,
            primary_guardian_email=data.primary_guardian_email,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(account)
        await self.db.flush()

        for student in students:
            await self._move_student_to_account(student, account)
        created_children = await self._create_children(account, data.new_children, created_by_id)

        await self._refresh_account_state(account)
        await self._allocate_account_credit(account.id, created_by_id)
        await self.audit.log(
            action="billing_account.create",
            entity_type="BillingAccount",
            entity_id=account.id,
            entity_identifier=account.account_number,
            user_id=created_by_id,
            new_values={
                "display_name": account.display_name,
                "student_ids": [student.id for student in students],
                "new_child_ids": created_children,
            },
        )
        await self.db.commit()
        return await self.get_billing_account_by_id(account.id)

    async def update_billing_account(
        self,
        account_id: int,
        data: BillingAccountUpdate,
        updated_by_id: int,
    ) -> BillingAccount:
        """Update billing account metadata."""
        account = await self.get_billing_account_by_id(account_id)
        old_values: dict[str, str | None] = {}
        new_values: dict[str, str | None] = {}

        if data.display_name is not None and data.display_name.strip() != account.display_name:
            old_values["display_name"] = account.display_name
            account.display_name = data.display_name.strip()
            new_values["display_name"] = account.display_name
        if data.primary_guardian_name is not None and data.primary_guardian_name != account.primary_guardian_name:
            old_values["primary_guardian_name"] = account.primary_guardian_name
            account.primary_guardian_name = data.primary_guardian_name
            new_values["primary_guardian_name"] = data.primary_guardian_name
        if data.primary_guardian_phone is not None and data.primary_guardian_phone != account.primary_guardian_phone:
            old_values["primary_guardian_phone"] = account.primary_guardian_phone
            account.primary_guardian_phone = data.primary_guardian_phone
            new_values["primary_guardian_phone"] = data.primary_guardian_phone
        if data.primary_guardian_email is not None and data.primary_guardian_email != account.primary_guardian_email:
            old_values["primary_guardian_email"] = account.primary_guardian_email
            account.primary_guardian_email = data.primary_guardian_email
            new_values["primary_guardian_email"] = data.primary_guardian_email
        if "notes" in data.model_fields_set and data.notes != account.notes:
            old_values["notes"] = account.notes
            account.notes = data.notes
            new_values["notes"] = data.notes

        if new_values:
            await self.audit.log(
                action="billing_account.update",
                entity_type="BillingAccount",
                entity_id=account.id,
                entity_identifier=account.account_number,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        return await self.get_billing_account_by_id(account.id)

    async def add_members(
        self,
        account_id: int,
        data: BillingAccountAddMembersRequest,
        added_by_id: int,
    ) -> BillingAccount:
        """Attach more students to an existing billing account."""
        account = await self.get_billing_account_by_id(account_id)
        students = await self._get_students(data.student_ids)

        moved_ids: list[int] = []
        for student in students:
            if student.billing_account_id == account.id:
                continue
            await self._move_student_to_account(student, account)
            moved_ids.append(student.id)

        if not moved_ids:
            raise ValidationError("No new students were added to this billing account")

        await self._refresh_account_state(account)
        await self._allocate_account_credit(account.id, added_by_id)
        await self.audit.log(
            action="billing_account.add_members",
            entity_type="BillingAccount",
            entity_id=account.id,
            entity_identifier=account.account_number,
            user_id=added_by_id,
            new_values={"student_ids": moved_ids},
        )
        await self.db.commit()
        return await self.get_billing_account_by_id(account.id)

    async def add_child(
        self,
        account_id: int,
        data: BillingAccountChildCreate,
        added_by_id: int,
    ) -> BillingAccount:
        """Create a brand-new student directly inside an existing billing account."""
        account = await self.get_billing_account_by_id(account_id)

        created_children = await self._create_children(account, [data], added_by_id)
        await self._refresh_account_state(account)
        await self._allocate_account_credit(account.id, added_by_id)
        await self.audit.log(
            action="billing_account.add_child",
            entity_type="BillingAccount",
            entity_id=account.id,
            entity_identifier=account.account_number,
            user_id=added_by_id,
            new_values={"student_ids": created_children},
        )
        await self.db.commit()
        return await self.get_billing_account_by_id(account.id)

    async def sync_cached_balance(self, account_id: int) -> None:
        """Mirror the account credit balance down to its member students."""
        result = await self.db.execute(
            select(BillingAccount.cached_credit_balance).where(BillingAccount.id == account_id)
        )
        cached_balance = Decimal(str(result.scalar_one_or_none() or 0))
        await self.db.execute(
            update(Student)
            .where(Student.billing_account_id == account_id)
            .values(cached_credit_balance=round_money(cached_balance))
        )

    async def _build_summaries(
        self, accounts: list[BillingAccount]
    ) -> list[BillingAccountSummary]:
        if not accounts:
            return []
        debt_map = await self._get_outstanding_debt_map([account.id for account in accounts])
        return [
            BillingAccountSummary(
                id=account.id,
                account_number=account.account_number,
                primary_student_number=self._display_student_number(account),
                display_name=account.display_name,
                primary_guardian_name=account.primary_guardian_name,
                primary_guardian_phone=account.primary_guardian_phone,
                primary_guardian_email=account.primary_guardian_email,
                notes=account.notes,
                member_count=len(account.students),
                available_balance=round_money(account.cached_credit_balance),
                outstanding_debt=debt_map.get(account.id, Decimal("0.00")),
                balance=round_money(
                    round_money(account.cached_credit_balance)
                    - debt_map.get(account.id, Decimal("0.00"))
                ),
            )
            for account in accounts
        ]

    @staticmethod
    def _display_student_number(account: BillingAccount) -> str | None:
        if not account.students:
            return None
        return min(student.student_number for student in account.students)

    async def _build_summary(self, account: BillingAccount) -> BillingAccountSummary:
        summaries = await self._build_summaries([account])
        return summaries[0]

    async def _get_outstanding_debt_map(
        self, account_ids: list[int]
    ) -> dict[int, Decimal]:
        if not account_ids:
            return {}
        result = await self.db.execute(
            select(
                Invoice.billing_account_id,
                func.coalesce(func.sum(InvoiceLine.remaining_amount), 0),
            )
            .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
            .where(
                Invoice.billing_account_id.in_(account_ids),
                Invoice.status.in_(
                    [InvoiceStatus.ISSUED.value, InvoiceStatus.PARTIALLY_PAID.value]
                ),
            )
            .group_by(Invoice.billing_account_id)
        )
        return {row[0]: round_money(Decimal(str(row[1]))) for row in result.all()}

    async def _get_balance_export_amount_map(
        self,
        account_ids: list[int],
    ) -> dict[int, dict[str, Decimal | date | None]]:
        """Aggregate current parent balance amounts by billing account."""
        if not account_ids:
            return {}

        amounts: dict[int, dict[str, Decimal | date | None]] = {
            account_id: {
                "total_payments": Decimal("0.00"),
                "total_refunds": Decimal("0.00"),
                "current_allocated": Decimal("0.00"),
                "total_invoiced": Decimal("0.00"),
                "paid_to_invoices": Decimal("0.00"),
                "invoice_adjustments": Decimal("0.00"),
                "outstanding_debt": Decimal("0.00"),
                "last_payment_date": None,
            }
            for account_id in account_ids
        }

        payment_result = await self.db.execute(
            select(
                Payment.billing_account_id,
                func.coalesce(func.sum(Payment.amount), 0),
                func.max(Payment.payment_date),
            )
            .where(
                Payment.billing_account_id.in_(account_ids),
                Payment.status == PaymentStatus.COMPLETED.value,
            )
            .group_by(Payment.billing_account_id)
        )
        for account_id, total, last_payment_date in payment_result.all():
            amounts[int(account_id)]["total_payments"] = round_money(Decimal(str(total or 0)))
            amounts[int(account_id)]["last_payment_date"] = last_payment_date

        refund_result = await self.db.execute(
            select(
                PaymentRefund.billing_account_id,
                func.coalesce(func.sum(PaymentRefund.amount), 0),
            )
            .where(PaymentRefund.billing_account_id.in_(account_ids))
            .group_by(PaymentRefund.billing_account_id)
        )
        for account_id, total in refund_result.all():
            amounts[int(account_id)]["total_refunds"] = round_money(Decimal(str(total or 0)))

        allocation_result = await self.db.execute(
            select(
                CreditAllocation.billing_account_id,
                func.coalesce(func.sum(CreditAllocation.amount), 0),
            )
            .where(CreditAllocation.billing_account_id.in_(account_ids))
            .group_by(CreditAllocation.billing_account_id)
        )
        for account_id, total in allocation_result.all():
            amounts[int(account_id)]["current_allocated"] = round_money(Decimal(str(total or 0)))

        invoice_result = await self.db.execute(
            select(
                Invoice.billing_account_id,
                func.coalesce(func.sum(Invoice.total), 0),
                func.coalesce(func.sum(Invoice.paid_total), 0),
                func.coalesce(func.sum(Invoice.adjustment_total), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Invoice.status.in_(self._OPEN_INVOICE_STATUSES),
                                Invoice.amount_due,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    0,
                ),
            )
            .where(
                Invoice.billing_account_id.in_(account_ids),
                Invoice.status.in_(self._BILLABLE_INVOICE_STATUSES),
            )
            .group_by(Invoice.billing_account_id)
        )
        for account_id, total, paid, adjusted, due in invoice_result.all():
            account_amounts = amounts[int(account_id)]
            account_amounts["total_invoiced"] = round_money(Decimal(str(total or 0)))
            account_amounts["paid_to_invoices"] = round_money(Decimal(str(paid or 0)))
            account_amounts["invoice_adjustments"] = round_money(Decimal(str(adjusted or 0)))
            account_amounts["outstanding_debt"] = round_money(Decimal(str(due or 0)))

        return amounts

    async def _get_payment_refunded_amount_map(
        self,
        payment_ids: list[int],
    ) -> dict[int, Decimal]:
        if not payment_ids:
            return {}

        refunded: dict[int, Decimal] = {payment_id: Decimal("0.00") for payment_id in payment_ids}
        source_result = await self.db.execute(
            select(
                PaymentRefundSource.payment_id,
                func.coalesce(func.sum(PaymentRefundSource.amount), 0),
            )
            .where(PaymentRefundSource.payment_id.in_(payment_ids))
            .group_by(PaymentRefundSource.payment_id)
        )
        for payment_id, amount in source_result.all():
            refunded[int(payment_id)] = round_money(Decimal(str(amount or 0)))

        legacy_result = await self.db.execute(
            select(
                PaymentRefund.payment_id,
                func.coalesce(func.sum(PaymentRefund.amount), 0),
            )
            .where(
                PaymentRefund.payment_id.in_(payment_ids),
                ~select(PaymentRefundSource.id)
                .where(PaymentRefundSource.refund_id == PaymentRefund.id)
                .exists(),
            )
            .group_by(PaymentRefund.payment_id)
        )
        for payment_id, amount in legacy_result.all():
            if payment_id is None:
                continue
            refunded[int(payment_id)] = round_money(
                refunded.get(int(payment_id), Decimal("0.00")) + Decimal(str(amount or 0))
            )

        return refunded

    def _build_parent_balance_export_row(
        self,
        account: BillingAccount,
        amounts: dict[str, Decimal | date | None],
    ) -> dict:
        total_payments = round_money(
            Decimal(str(amounts.get("total_payments") or Decimal("0.00")))
        )
        total_refunds = round_money(
            Decimal(str(amounts.get("total_refunds") or Decimal("0.00")))
        )
        current_allocated = round_money(
            Decimal(str(amounts.get("current_allocated") or Decimal("0.00")))
        )
        outstanding_debt = round_money(
            Decimal(str(amounts.get("outstanding_debt") or Decimal("0.00")))
        )
        net_paid = round_money(total_payments - total_refunds)
        available_credit = round_money(net_paid - current_allocated)
        net_balance = round_money(available_credit - outstanding_debt)
        amount_to_pay_now = round_money(max(Decimal("0.00"), outstanding_debt - available_credit))
        credit_after_debts = round_money(max(Decimal("0.00"), available_credit - outstanding_debt))

        return {
            "account_id": account.id,
            "account_number": account.account_number,
            "primary_student_number": self._display_student_number(account),
            "display_name": account.display_name,
            "primary_guardian_name": account.primary_guardian_name,
            "primary_guardian_phone": account.primary_guardian_phone,
            "primary_guardian_email": account.primary_guardian_email,
            "students": self._student_roster(account),
            "member_count": len(account.students),
            "total_payments": total_payments,
            "total_refunds": total_refunds,
            "net_paid": net_paid,
            "paid_to_invoices": round_money(
                Decimal(str(amounts.get("paid_to_invoices") or Decimal("0.00")))
            ),
            "available_credit": available_credit,
            "total_invoiced": round_money(
                Decimal(str(amounts.get("total_invoiced") or Decimal("0.00")))
            ),
            "invoice_adjustments": round_money(
                Decimal(str(amounts.get("invoice_adjustments") or Decimal("0.00")))
            ),
            "outstanding_debt": outstanding_debt,
            "amount_to_pay_now": amount_to_pay_now,
            "credit_after_debts": credit_after_debts,
            "net_balance": net_balance,
            "last_payment_date": amounts.get("last_payment_date"),
        }

    @staticmethod
    def _student_roster(account: BillingAccount) -> str:
        return ", ".join(student.full_name for student in account.students)

    async def _get_student(self, student_id: int) -> Student:
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .options(
                selectinload(Student.grade),
                selectinload(Student.billing_account).selectinload(BillingAccount.students),
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def _get_students(self, student_ids: list[int]) -> list[Student]:
        unique_ids = sorted({int(student_id) for student_id in student_ids})
        result = await self.db.execute(
            select(Student)
            .where(Student.id.in_(unique_ids))
            .options(
                selectinload(Student.grade),
                selectinload(Student.billing_account).selectinload(BillingAccount.students),
            )
        )
        students = list(result.scalars().unique().all())
        found_ids = {student.id for student in students}
        missing = [str(student_id) for student_id in unique_ids if student_id not in found_ids]
        if missing:
            raise ValidationError(f"Students not found: {', '.join(missing)}")
        return sorted(students, key=lambda student: unique_ids.index(student.id))

    async def _move_student_to_account(
        self,
        student: Student,
        account: BillingAccount,
    ) -> None:
        source_account = student.billing_account
        if source_account and source_account.id == account.id:
            return

        if source_account is None:
            source_account = await self.ensure_student_billing_account(student.id)

        if source_account.id == account.id:
            return

        source_member_count = len(source_account.students)
        if source_member_count > 1:
            raise ValidationError(
                f"Student {student.full_name} already belongs to another shared billing account"
            )

        await self.db.execute(
            update(Invoice)
            .where(
                or_(
                    Invoice.student_id == student.id,
                    Invoice.billing_account_id == source_account.id,
                )
            )
            .values(billing_account_id=account.id)
        )
        await self.db.execute(
            update(Payment)
            .where(
                or_(
                    Payment.student_id == student.id,
                    Payment.billing_account_id == source_account.id,
                )
            )
            .values(billing_account_id=account.id)
        )
        await self.db.execute(
            update(CreditAllocation)
            .where(
                or_(
                    CreditAllocation.student_id == student.id,
                    CreditAllocation.billing_account_id == source_account.id,
                )
            )
            .values(billing_account_id=account.id)
        )

        student.billing_account = account
        await self.db.flush()

        await self._recalculate_account_cached_balance(account.id)
        await self.sync_cached_balance(account.id)
        if source_account.id != account.id:
            source_member_count = (
                await self.db.execute(
                    select(func.count())
                    .select_from(Student)
                    .where(Student.billing_account_id == source_account.id)
                )
            ).scalar() or 0
            if source_member_count == 0:
                await self.db.delete(source_account)
            else:
                await self._recalculate_account_cached_balance(source_account.id)
                await self.sync_cached_balance(source_account.id)

    async def _refresh_account_state(self, account: BillingAccount) -> None:
        await self.db.refresh(account, attribute_names=["students"])
        await self._recalculate_account_cached_balance(account.id)
        await self.sync_cached_balance(account.id)

    async def _recalculate_account_cached_balance(self, account_id: int) -> None:
        payments_result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.billing_account_id == account_id,
                Payment.status == "completed",
            )
        )
        total_payments = Decimal(str(payments_result.scalar() or 0))

        refunds_result = await self.db.execute(
            select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(
                PaymentRefund.billing_account_id == account_id
            )
        )
        total_refunded = Decimal(str(refunds_result.scalar() or 0))

        allocations_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditAllocation.amount), 0)).where(
                CreditAllocation.billing_account_id == account_id
            )
        )
        total_allocated = Decimal(str(allocations_result.scalar() or 0))

        await self.db.execute(
            update(BillingAccount)
            .where(BillingAccount.id == account_id)
            .values(
                cached_credit_balance=round_money(
                    total_payments - total_refunded - total_allocated
                )
            )
        )

    async def _allocate_account_credit(self, account_id: int, user_id: int) -> None:
        """Apply shared credit immediately after a billing account membership change."""
        from src.modules.payments.schemas import AutoAllocateRequest
        from src.modules.payments.service import PaymentService

        payment_service = PaymentService(self.db)
        await payment_service.allocate_auto(
            AutoAllocateRequest(billing_account_id=account_id),
            user_id,
            commit=False,
        )

    async def _create_children(
        self,
        account: BillingAccount,
        children: list[BillingAccountChildCreate],
        created_by_id: int,
    ) -> list[int]:
        if not children:
            return []

        from src.modules.students.service import StudentService

        student_service = StudentService(self.db)
        created_ids: list[int] = []
        for child in children:
            guardian_name = (child.guardian_name or account.primary_guardian_name or "").strip()
            guardian_phone = (child.guardian_phone or account.primary_guardian_phone or "").strip()
            guardian_email = (
                child.guardian_email
                if child.guardian_email is not None
                else account.primary_guardian_email
            )

            if not guardian_name:
                raise ValidationError(
                    "Guardian name is required either on the billing account or the child",
                    field="guardian_name",
                )
            if not guardian_phone:
                raise ValidationError(
                    "Guardian phone is required either on the billing account or the child",
                    field="guardian_phone",
                )

            student = await student_service.create_student(
                StudentCreate(
                    first_name=child.first_name,
                    last_name=child.last_name,
                    date_of_birth=child.date_of_birth,
                    gender=child.gender,
                    grade_id=child.grade_id,
                    transport_zone_id=child.transport_zone_id,
                    guardian_name=guardian_name,
                    guardian_phone=guardian_phone,
                    guardian_email=guardian_email,
                    enrollment_date=child.enrollment_date,
                    notes=child.notes,
                    billing_account_id=account.id,
                ),
                created_by_id=created_by_id,
                commit=False,
            )
            created_ids.append(student.id)

        return created_ids
