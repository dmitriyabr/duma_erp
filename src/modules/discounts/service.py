"""Service for Discounts module."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.shared.utils.money import round_money
from src.modules.discounts.models import (
    Discount,
    DiscountReason,
    DiscountValueType,
    StudentDiscount,
    StudentDiscountAppliesTo,
)
from src.modules.discounts.schemas import (
    DiscountApply,
    DiscountReasonCreate,
    DiscountReasonUpdate,
    StudentDiscountCreate,
    StudentDiscountUpdate,
)
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.students.models import Student


class DiscountService:
    """Service for managing discounts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # --- Discount Reason Methods ---

    async def create_reason(
        self, data: DiscountReasonCreate, created_by_id: int
    ) -> DiscountReason:
        """Create a new discount reason."""
        # Check for duplicate code
        existing = await self.db.execute(
            select(DiscountReason).where(DiscountReason.code == data.code)
        )
        if existing.scalar_one_or_none():
            raise DuplicateError("DiscountReason", "code", data.code)

        reason = DiscountReason(
            code=data.code,
            name=data.name,
        )
        self.db.add(reason)
        await self.db.flush()

        await self.audit.log(
            action="discount_reason.create",
            entity_type="DiscountReason",
            entity_id=reason.id,
            user_id=created_by_id,
            new_values={"code": data.code, "name": data.name},
        )

        await self.db.commit()
        await self.db.refresh(reason)
        return reason

    async def get_reason_by_id(self, reason_id: int) -> DiscountReason:
        """Get discount reason by ID."""
        result = await self.db.execute(
            select(DiscountReason).where(DiscountReason.id == reason_id)
        )
        reason = result.scalar_one_or_none()
        if not reason:
            raise NotFoundError(f"Discount reason with id {reason_id} not found")
        return reason

    async def list_reasons(self, include_inactive: bool = False) -> list[DiscountReason]:
        """List all discount reasons."""
        query = select(DiscountReason).order_by(DiscountReason.name)
        if not include_inactive:
            query = query.where(DiscountReason.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_reason(
        self, reason_id: int, data: DiscountReasonUpdate, updated_by_id: int
    ) -> DiscountReason:
        """Update a discount reason."""
        reason = await self.get_reason_by_id(reason_id)
        old_values = {}
        new_values = {}

        if data.code is not None and data.code != reason.code:
            # Check for duplicate
            existing = await self.db.execute(
                select(DiscountReason).where(
                    DiscountReason.code == data.code, DiscountReason.id != reason_id
                )
            )
            if existing.scalar_one_or_none():
                raise DuplicateError("DiscountReason", "code", data.code)
            old_values["code"] = reason.code
            reason.code = data.code
            new_values["code"] = data.code

        if data.name is not None and data.name != reason.name:
            old_values["name"] = reason.name
            reason.name = data.name
            new_values["name"] = data.name

        if data.is_active is not None and data.is_active != reason.is_active:
            old_values["is_active"] = reason.is_active
            reason.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if new_values:
            await self.audit.log(
                action="discount_reason.update",
                entity_type="DiscountReason",
                entity_id=reason_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(reason)
        return reason

    # --- Discount Methods (applied to invoice line) ---

    def _calculate_discount_amount(
        self, value_type: str, value: Decimal, line_total: Decimal
    ) -> Decimal:
        """Calculate the actual discount amount."""
        if value_type == DiscountValueType.FIXED.value:
            # Fixed discount cannot exceed line total
            return min(round_money(value), line_total)
        elif value_type == DiscountValueType.PERCENTAGE.value:
            # Percentage of line total
            return round_money(line_total * value / Decimal("100"))
        else:
            raise ValidationError(f"Unknown discount value type: {value_type}")

    async def apply_discount(
        self, data: DiscountApply, applied_by_id: int
    ) -> Discount:
        """Apply a discount to an invoice line."""
        # Get invoice line
        result = await self.db.execute(
            select(InvoiceLine)
            .where(InvoiceLine.id == data.invoice_line_id)
            .options(selectinload(InvoiceLine.invoice))
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {data.invoice_line_id} not found")

        invoice = line.invoice

        # Check invoice status - can apply discount to draft or issued
        if invoice.status in (
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.VOID.value,
            InvoiceStatus.PAID.value,
        ):
            raise ValidationError(f"Cannot apply discount to invoice with status '{invoice.status}'")

        # Validate reason if provided
        if data.reason_id:
            reason = await self.get_reason_by_id(data.reason_id)
            if not reason.is_active:
                raise ValidationError(f"Discount reason '{reason.name}' is not active")

        # Calculate discount amount
        calculated_amount = self._calculate_discount_amount(
            data.value_type.value, data.value, line.line_total
        )

        # Check if discount exceeds line total
        current_discount = line.discount_amount
        total_discount = current_discount + calculated_amount
        if total_discount > line.line_total:
            raise ValidationError(
                f"Total discount ({total_discount}) would exceed line total ({line.line_total})"
            )

        # Create discount record
        discount = Discount(
            invoice_line_id=data.invoice_line_id,
            value_type=data.value_type.value,
            value=data.value,
            calculated_amount=calculated_amount,
            reason_id=data.reason_id,
            reason_text=data.reason_text,
            applied_by_id=applied_by_id,
        )
        self.db.add(discount)
        await self.db.flush()  # Get discount.id for audit

        # Update line discount amount
        line.discount_amount = round_money(line.discount_amount + calculated_amount)
        line.net_amount = round_money(line.line_total - line.discount_amount)
        line.remaining_amount = round_money(line.net_amount - line.paid_amount)

        # Recalculate invoice totals
        await self._recalculate_invoice(invoice)

        await self.audit.log(
            action="discount.apply",
            entity_type="Discount",
            entity_id=discount.id,
            user_id=applied_by_id,
            new_values={
                "invoice_line_id": data.invoice_line_id,
                "value_type": data.value_type.value,
                "value": str(data.value),
                "calculated_amount": str(calculated_amount),
            },
        )

        await self.db.commit()
        await self.db.refresh(discount)
        return discount

    async def remove_discount(
        self, discount_id: int, removed_by_id: int
    ) -> None:
        """Remove a discount from an invoice line."""
        result = await self.db.execute(
            select(Discount)
            .where(Discount.id == discount_id)
            .options(
                selectinload(Discount.invoice_line).selectinload(InvoiceLine.invoice)
            )
        )
        discount = result.scalar_one_or_none()
        if not discount:
            raise NotFoundError(f"Discount with id {discount_id} not found")

        line = discount.invoice_line
        invoice = line.invoice

        # Check invoice status
        if invoice.status in (
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.VOID.value,
            InvoiceStatus.PAID.value,
        ):
            raise ValidationError(f"Cannot remove discount from invoice with status '{invoice.status}'")

        # Update line discount amount
        line.discount_amount = round_money(line.discount_amount - discount.calculated_amount)
        line.net_amount = round_money(line.line_total - line.discount_amount)
        line.remaining_amount = round_money(line.net_amount - line.paid_amount)

        # Recalculate invoice totals
        await self._recalculate_invoice(invoice)

        await self.audit.log(
            action="discount.remove",
            entity_type="Discount",
            entity_id=discount_id,
            user_id=removed_by_id,
            old_values={
                "invoice_line_id": discount.invoice_line_id,
                "calculated_amount": str(discount.calculated_amount),
            },
        )

        await self.db.delete(discount)
        await self.db.commit()

    async def get_line_discounts(self, invoice_line_id: int) -> list[Discount]:
        """Get all discounts applied to an invoice line."""
        result = await self.db.execute(
            select(Discount)
            .where(Discount.invoice_line_id == invoice_line_id)
            .options(selectinload(Discount.reason))
            .order_by(Discount.created_at)
        )
        return list(result.scalars().all())

    async def _recalculate_invoice(self, invoice: Invoice) -> None:
        """Recalculate invoice totals."""
        # Reload lines to get updated values
        result = await self.db.execute(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        )
        lines = list(result.scalars().all())

        invoice.subtotal = round_money(sum(line.line_total for line in lines))
        invoice.discount_total = round_money(sum(line.discount_amount for line in lines))
        invoice.total = round_money(invoice.subtotal - invoice.discount_total)
        invoice.paid_total = round_money(sum(line.paid_amount for line in lines))
        invoice.amount_due = round_money(invoice.total - invoice.paid_total)

        # Update status
        if invoice.status not in (
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.VOID.value,
            InvoiceStatus.DRAFT.value,
        ):
            if invoice.amount_due == Decimal("0.00"):
                invoice.status = InvoiceStatus.PAID.value
            elif invoice.paid_total > Decimal("0.00"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID.value
            else:
                invoice.status = InvoiceStatus.ISSUED.value

    # --- Student Discount Methods (standing discount) ---

    async def create_student_discount(
        self, data: StudentDiscountCreate, created_by_id: int
    ) -> StudentDiscount:
        """Create a standing discount for a student."""
        # Validate student exists
        result = await self.db.execute(
            select(Student).where(Student.id == data.student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {data.student_id} not found")

        # Validate reason if provided
        if data.reason_id:
            reason = await self.get_reason_by_id(data.reason_id)
            if not reason.is_active:
                raise ValidationError(f"Discount reason '{reason.name}' is not active")

        student_discount = StudentDiscount(
            student_id=data.student_id,
            applies_to=data.applies_to.value,
            value_type=data.value_type.value,
            value=data.value,
            reason_id=data.reason_id,
            reason_text=data.reason_text,
            is_active=True,
            created_by_id=created_by_id,
        )
        self.db.add(student_discount)
        await self.db.flush()

        await self.audit.log(
            action="student_discount.create",
            entity_type="StudentDiscount",
            entity_id=student_discount.id,
            user_id=created_by_id,
            new_values={
                "student_id": data.student_id,
                "applies_to": data.applies_to.value,
                "value_type": data.value_type.value,
                "value": str(data.value),
            },
        )

        await self.db.commit()
        await self.db.refresh(student_discount)
        return student_discount

    async def get_student_discount_by_id(self, discount_id: int) -> StudentDiscount:
        """Get student discount by ID."""
        result = await self.db.execute(
            select(StudentDiscount)
            .where(StudentDiscount.id == discount_id)
            .options(
                selectinload(StudentDiscount.student),
                selectinload(StudentDiscount.reason),
            )
        )
        discount = result.scalar_one_or_none()
        if not discount:
            raise NotFoundError(f"Student discount with id {discount_id} not found")
        return discount

    async def list_student_discounts(
        self,
        student_id: int | None = None,
        include_inactive: bool = False,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[StudentDiscount], int]:
        """List student discounts."""
        query = (
            select(StudentDiscount)
            .options(
                selectinload(StudentDiscount.student),
                selectinload(StudentDiscount.reason),
            )
            .order_by(StudentDiscount.created_at.desc())
        )

        if student_id is not None:
            query = query.where(StudentDiscount.student_id == student_id)
        if not include_inactive:
            query = query.where(StudentDiscount.is_active == True)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        discounts = list(result.scalars().all())

        return discounts, total

    async def update_student_discount(
        self, discount_id: int, data: StudentDiscountUpdate, updated_by_id: int
    ) -> StudentDiscount:
        """Update a student discount."""
        discount = await self.get_student_discount_by_id(discount_id)
        old_values = {}
        new_values = {}

        if data.value_type is not None and data.value_type.value != discount.value_type:
            old_values["value_type"] = discount.value_type
            discount.value_type = data.value_type.value
            new_values["value_type"] = data.value_type.value

        if data.value is not None and data.value != discount.value:
            old_values["value"] = str(discount.value)
            discount.value = data.value
            new_values["value"] = str(data.value)

        if data.reason_id is not None:
            if data.reason_id != discount.reason_id:
                if data.reason_id:
                    reason = await self.get_reason_by_id(data.reason_id)
                    if not reason.is_active:
                        raise ValidationError(f"Discount reason '{reason.name}' is not active")
                old_values["reason_id"] = discount.reason_id
                discount.reason_id = data.reason_id
                new_values["reason_id"] = data.reason_id

        if data.reason_text is not None and data.reason_text != discount.reason_text:
            old_values["reason_text"] = discount.reason_text
            discount.reason_text = data.reason_text
            new_values["reason_text"] = data.reason_text

        if data.is_active is not None and data.is_active != discount.is_active:
            old_values["is_active"] = discount.is_active
            discount.is_active = data.is_active
            new_values["is_active"] = data.is_active

        if new_values:
            await self.audit.log(
                action="student_discount.update",
                entity_type="StudentDiscount",
                entity_id=discount_id,
                user_id=updated_by_id,
                old_values=old_values,
                new_values=new_values,
            )

        await self.db.commit()
        await self.db.refresh(discount)
        return discount

    async def get_active_student_discounts(
        self, student_id: int, applies_to: StudentDiscountAppliesTo
    ) -> list[StudentDiscount]:
        """Get active discounts for a student that apply to a specific type."""
        result = await self.db.execute(
            select(StudentDiscount)
            .where(
                StudentDiscount.student_id == student_id,
                StudentDiscount.applies_to == applies_to.value,
                StudentDiscount.is_active == True,
            )
            .options(selectinload(StudentDiscount.reason))
        )
        return list(result.scalars().all())

    async def apply_student_discounts_to_line(
        self, invoice_line_id: int, student_id: int, invoice_type: str, applied_by_id: int
    ) -> list[Discount]:
        """Apply all active student discounts to an invoice line.

        Called during term invoice generation.
        """
        # Determine what discounts apply based on invoice type
        if invoice_type == InvoiceType.SCHOOL_FEE.value:
            applies_to = StudentDiscountAppliesTo.SCHOOL_FEE
        else:
            return []  # No auto-discounts for other types yet

        student_discounts = await self.get_active_student_discounts(student_id, applies_to)

        applied = []
        for sd in student_discounts:
            discount = await self.apply_discount(
                DiscountApply(
                    invoice_line_id=invoice_line_id,
                    value_type=DiscountValueType(sd.value_type),
                    value=sd.value,
                    reason_id=sd.reason_id,
                    reason_text=sd.reason_text,
                ),
                applied_by_id=applied_by_id,
            )
            # Link to student discount
            discount.student_discount_id = sd.id
            applied.append(discount)

        if applied:
            await self.db.commit()

        return applied
