"""Service for Invoices module."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.shared.utils.money import round_money
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceFilters,
    InvoiceLineCreate,
    InvoiceUpdate,
    TermInvoiceGenerationResult,
)
from src.modules.items.models import Kit, PriceType
from src.modules.students.models import Student, StudentStatus
from src.modules.terms.models import PriceSetting, Term, TermStatus, TransportPricing
from src.modules.discounts.models import StudentDiscount, StudentDiscountAppliesTo, DiscountValueType


class InvoiceService:
    """Service for managing invoices."""

    ADMISSION_FEE_SKU = "ADMISSION-FEE"
    INTERVIEW_FEE_SKU = "INTERVIEW-FEE"
    INITIAL_FEE_SKUS = {ADMISSION_FEE_SKU, INTERVIEW_FEE_SKU}

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # --- Helper Methods ---

    async def _get_kit_price(
        self,
        kit: Kit,
        term_id: int | None,
        grade_id: int | None,
        zone_id: int | None,
        allow_missing: bool = False,
    ) -> Decimal | None:
        """Get the price for a kit based on its price_type."""
        if kit.price_type == PriceType.STANDARD.value:
            if kit.price is None:
                raise ValidationError(f"Kit '{kit.name}' has no price set")
            return kit.price

        elif kit.price_type == PriceType.BY_GRADE.value:
            if term_id is None or grade_id is None:
                if allow_missing:
                    return None
                raise ValidationError(
                    f"Kit '{kit.name}' requires term and grade for pricing"
                )
            # Get the grade code and name first
            from src.modules.students.models import Grade

            grade_result = await self.db.execute(
                select(Grade.code, Grade.name).where(Grade.id == grade_id)
            )
            grade_row = grade_result.one_or_none()
            if not grade_row:
                if allow_missing:
                    return None
                raise ValidationError(f"Grade with id {grade_id} not found")
            grade_code, grade_name = grade_row

            result = await self.db.execute(
                select(PriceSetting).where(
                    PriceSetting.term_id == term_id,
                    PriceSetting.grade == grade_code,
                )
            )
            price_setting = result.scalar_one_or_none()
            if not price_setting:
                if allow_missing:
                    return None
                raise ValidationError(
                    f"No price setting found for term {term_id} and grade {grade_code}"
                )
            return price_setting.school_fee_amount

        elif kit.price_type == PriceType.BY_ZONE.value:
            if term_id is None or zone_id is None:
                if allow_missing:
                    return None
                raise ValidationError(
                    f"Kit '{kit.name}' requires term and transport zone for pricing"
                )
            result = await self.db.execute(
                select(TransportPricing).where(
                    TransportPricing.term_id == term_id,
                    TransportPricing.zone_id == zone_id,
                )
            )
            transport_pricing = result.scalar_one_or_none()
            if not transport_pricing:
                if allow_missing:
                    return None
                raise ValidationError(
                    f"No transport pricing found for term {term_id} and zone {zone_id}"
                )
            return transport_pricing.transport_fee_amount

        raise ValidationError(f"Unknown price type: {kit.price_type}")

    def _recalculate_line(self, line: InvoiceLine) -> None:
        """Recalculate line totals."""
        line.line_total = round_money(line.unit_price * line.quantity)
        line.net_amount = round_money(line.line_total - line.discount_amount)
        line.remaining_amount = round_money(line.net_amount - line.paid_amount)

    def _recalculate_invoice(self, invoice: Invoice) -> None:
        """Recalculate invoice totals from lines."""
        invoice.subtotal = round_money(sum(line.line_total for line in invoice.lines))
        invoice.discount_total = round_money(
            sum(line.discount_amount for line in invoice.lines)
        )
        invoice.total = round_money(invoice.subtotal - invoice.discount_total)
        invoice.paid_total = round_money(sum(line.paid_amount for line in invoice.lines))
        invoice.amount_due = round_money(invoice.total - invoice.paid_total)

        # Update status based on payment
        if invoice.status not in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value, InvoiceStatus.DRAFT.value):
            if invoice.amount_due == Decimal("0.00"):
                invoice.status = InvoiceStatus.PAID.value
            elif invoice.paid_total > Decimal("0.00"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID.value
            else:
                invoice.status = InvoiceStatus.ISSUED.value

    async def _apply_student_discounts(
        self,
        line_id: int,
        student_id: int,
        invoice_type: str,
        applied_by_id: int,
    ) -> None:
        """Apply active student discounts to an invoice line."""
        # Determine applies_to based on invoice type
        if invoice_type == InvoiceType.SCHOOL_FEE.value:
            applies_to = StudentDiscountAppliesTo.SCHOOL_FEE.value
        else:
            return  # No auto-discounts for other types yet

        # Get active student discounts
        result = await self.db.execute(
            select(StudentDiscount).where(
                StudentDiscount.student_id == student_id,
                StudentDiscount.applies_to == applies_to,
                StudentDiscount.is_active == True,
            )
        )
        student_discounts = list(result.scalars().all())

        if not student_discounts:
            return

        # Get the invoice line
        line_result = await self.db.execute(
            select(InvoiceLine).where(InvoiceLine.id == line_id)
        )
        line = line_result.scalar_one()

        # Apply each discount
        from src.modules.discounts.models import Discount

        for sd in student_discounts:
            # Calculate discount amount
            if sd.value_type == DiscountValueType.FIXED.value:
                calculated_amount = min(round_money(sd.value), line.line_total - line.discount_amount)
            else:  # percentage
                calculated_amount = round_money(line.line_total * sd.value / Decimal("100"))
                # Ensure doesn't exceed remaining line amount
                calculated_amount = min(calculated_amount, line.line_total - line.discount_amount)

            if calculated_amount <= 0:
                continue

            # Create discount record
            discount = Discount(
                invoice_line_id=line_id,
                value_type=sd.value_type,
                value=sd.value,
                calculated_amount=calculated_amount,
                reason_id=sd.reason_id,
                reason_text=sd.reason_text,
                student_discount_id=sd.id,
                applied_by_id=applied_by_id,
            )
            self.db.add(discount)

            # Update line discount
            line.discount_amount = round_money(line.discount_amount + calculated_amount)
            line.net_amount = round_money(line.line_total - line.discount_amount)
            line.remaining_amount = round_money(line.net_amount - line.paid_amount)

    # --- Invoice CRUD ---

    async def create_adhoc_invoice(
        self, data: InvoiceCreate, created_by_id: int
    ) -> Invoice:
        """Create an ad-hoc invoice (draft)."""
        # Validate student
        result = await self.db.execute(
            select(Student).where(Student.id == data.student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {data.student_id} not found")

        # Generate invoice number
        number_gen = DocumentNumberGenerator(self.db)
        invoice_number = await number_gen.generate("INV")

        invoice = Invoice(
            invoice_number=invoice_number,
            student_id=data.student_id,
            term_id=None,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.DRAFT.value,
            due_date=data.due_date,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        invoice.lines = []  # Initialize lines collection
        self.db.add(invoice)
        await self.db.flush()

        # Add lines if provided
        for line_data in data.lines:
            await self._add_line_to_invoice(
                invoice, line_data, student.grade_id, student.transport_zone_id
            )

        self._recalculate_invoice(invoice)

        await self.audit.log(
            action="invoice.create",
            entity_type="Invoice",
            entity_id=invoice.id,
            user_id=created_by_id,
            new_values={
                "invoice_number": invoice_number,
                "student_id": data.student_id,
                "type": InvoiceType.ADHOC.value,
            },
        )

        await self.db.commit()
        # Re-fetch with relationships loaded
        return await self.get_invoice_by_id(invoice.id)

    async def _add_line_to_invoice(
        self,
        invoice: Invoice,
        line_data: InvoiceLineCreate,
        grade_id: int | None,
        zone_id: int | None,
    ) -> InvoiceLine:
        """Add a line to an invoice."""
        result = await self.db.execute(select(Kit).where(Kit.id == line_data.kit_id))
        kit = result.scalar_one_or_none()
        if not kit:
            raise NotFoundError(f"Kit with id {line_data.kit_id} not found")
        if not kit.is_active:
            raise ValidationError(f"Kit '{kit.name}' is not active")
        await self._ensure_single_fee_allowed(invoice, kit, line_data.quantity)

        if line_data.unit_price_override is not None:
            unit_price = line_data.unit_price_override
        else:
            unit_price = await self._get_kit_price(
                kit, invoice.term_id, grade_id, zone_id
            )
        description = kit.name

        line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=kit.id,
            description=description,
            quantity=line_data.quantity,
            unit_price=unit_price,
            line_total=Decimal("0.00"),
            discount_amount=line_data.discount_amount,
            net_amount=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("0.00"),
        )

        self._recalculate_line(line)
        self.db.add(line)
        invoice.lines.append(line)
        return line

    async def add_line(
        self, invoice_id: int, line_data: InvoiceLineCreate, added_by_id: int
    ) -> Invoice:
        """Add a line to a draft invoice."""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice.is_editable:
            raise ValidationError("Cannot add lines to a non-draft invoice")

        # Get student for grade/zone info
        result = await self.db.execute(
            select(Student).where(Student.id == invoice.student_id)
        )
        student = result.scalar_one_or_none()

        await self._add_line_to_invoice(
            invoice, line_data, student.grade_id, student.transport_zone_id
        )
        self._recalculate_invoice(invoice)

        await self.audit.log(
            action="invoice.add_line",
            entity_type="Invoice",
            entity_id=invoice_id,
            user_id=added_by_id,
            new_values={
                "kit_id": line_data.kit_id,
                "quantity": line_data.quantity,
            },
        )

        await self.db.commit()
        # Re-fetch with relationships loaded
        return await self.get_invoice_by_id(invoice_id)

    async def remove_line(
        self, invoice_id: int, line_id: int, removed_by_id: int
    ) -> Invoice:
        """Remove a line from a draft invoice."""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice.is_editable:
            raise ValidationError("Cannot remove lines from a non-draft invoice")

        line_to_remove = None
        for line in invoice.lines:
            if line.id == line_id:
                line_to_remove = line
                break

        if not line_to_remove:
            raise NotFoundError(f"Line with id {line_id} not found in invoice")

        invoice.lines.remove(line_to_remove)
        await self.db.delete(line_to_remove)
        self._recalculate_invoice(invoice)

        await self.audit.log(
            action="invoice.remove_line",
            entity_type="Invoice",
            entity_id=invoice_id,
            user_id=removed_by_id,
            old_values={"line_id": line_id, "description": line_to_remove.description},
        )

        await self.db.commit()
        # Re-fetch with relationships loaded
        return await self.get_invoice_by_id(invoice_id)

    async def update_line_discount(
        self, invoice_id: int, line_id: int, discount_amount: Decimal, updated_by_id: int
    ) -> Invoice:
        """Update discount on a specific line."""
        invoice = await self.get_invoice_by_id(invoice_id)

        # Can update discount on draft or issued invoices
        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value, InvoiceStatus.PAID.value):
            raise ValidationError("Cannot update discount on this invoice")

        line = None
        for l in invoice.lines:
            if l.id == line_id:
                line = l
                break

        if not line:
            raise NotFoundError(f"Line with id {line_id} not found in invoice")

        if discount_amount > line.line_total:
            raise ValidationError("Discount cannot exceed line total")

        old_discount = line.discount_amount
        line.discount_amount = round_money(discount_amount)
        self._recalculate_line(line)
        self._recalculate_invoice(invoice)

        await self.audit.log(
            action="invoice.update_line_discount",
            entity_type="Invoice",
            entity_id=invoice_id,
            user_id=updated_by_id,
            old_values={"line_id": line_id, "discount_amount": str(old_discount)},
            new_values={"line_id": line_id, "discount_amount": str(discount_amount)},
        )

        await self.db.commit()
        # Re-fetch with relationships loaded
        return await self.get_invoice_by_id(invoice_id)

    async def issue_invoice(
        self, invoice_id: int, issued_by_id: int, due_date: date | None = None
    ) -> Invoice:
        """Issue a draft invoice."""
        invoice = await self.get_invoice_by_id(invoice_id)

        if invoice.status != InvoiceStatus.DRAFT.value:
            raise ValidationError("Only draft invoices can be issued")

        if not invoice.lines:
            raise ValidationError("Cannot issue an invoice with no lines")

        invoice.status = InvoiceStatus.ISSUED.value
        invoice.issue_date = date.today()
        invoice.due_date = due_date or (date.today() + timedelta(days=30))

        await self.audit.log(
            action="invoice.issue",
            entity_type="Invoice",
            entity_id=invoice_id,
            user_id=issued_by_id,
            new_values={"status": InvoiceStatus.ISSUED.value},
        )

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def cancel_invoice(self, invoice_id: int, cancelled_by_id: int) -> Invoice:
        """Cancel an invoice (only if no payments received)."""
        invoice = await self.get_invoice_by_id(invoice_id)

        if not invoice.can_be_cancelled:
            if invoice.paid_total > Decimal("0.00"):
                raise ValidationError(
                    "Cannot cancel invoice with payments. Use void instead."
                )
            raise ValidationError(
                f"Cannot cancel invoice with status '{invoice.status}'"
            )

        invoice.status = InvoiceStatus.CANCELLED.value

        await self.audit.log(
            action="invoice.cancel",
            entity_type="Invoice",
            entity_id=invoice_id,
            user_id=cancelled_by_id,
            new_values={"status": InvoiceStatus.CANCELLED.value},
        )

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def get_invoice_by_id(self, invoice_id: int) -> Invoice:
        """Get invoice by ID with lines, student (with grade), term loaded."""
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.student).selectinload(Student.grade),
                selectinload(Invoice.term),
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice with id {invoice_id} not found")
        return invoice

    async def get_invoice_by_number(self, invoice_number: str) -> Invoice:
        """Get invoice by number."""
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.invoice_number == invoice_number)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.student),
                selectinload(Invoice.term),
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice '{invoice_number}' not found")
        return invoice

    async def list_invoices(
        self, filters: InvoiceFilters
    ) -> tuple[list[Invoice], int]:
        """List invoices with filters."""
        query = (
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.student),
                selectinload(Invoice.term),
            )
            .order_by(Invoice.created_at.desc())
        )

        if filters.student_id is not None:
            query = query.where(Invoice.student_id == filters.student_id)
        if filters.term_id is not None:
            query = query.where(Invoice.term_id == filters.term_id)
        if filters.invoice_type is not None:
            query = query.where(Invoice.invoice_type == filters.invoice_type.value)
        if filters.status is not None:
            query = query.where(Invoice.status == filters.status.value)
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.join(Student).where(
                or_(
                    Invoice.invoice_number.ilike(search_term),
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                    Student.student_number.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (filters.page - 1) * filters.limit
        query = query.offset(offset).limit(filters.limit)

        result = await self.db.execute(query)
        invoices = list(result.scalars().all())

        return invoices, total

    # --- Term Invoice Generation ---

    async def generate_term_invoices(
        self, term_id: int, generated_by_id: int
    ) -> TermInvoiceGenerationResult:
        """Generate invoices for all active students for a term."""
        # Validate term
        result = await self.db.execute(select(Term).where(Term.id == term_id))
        term = result.scalar_one_or_none()
        if not term:
            raise NotFoundError(f"Term with id {term_id} not found")
        if term.status != TermStatus.ACTIVE.value:
            raise ValidationError("Can only generate invoices for active term")

        # Get School Fee and Transport Fee kits
        school_fee_kit = await self._get_kit_by_price_type(PriceType.BY_GRADE.value)
        transport_fee_kit = await self._get_kit_by_price_type(PriceType.BY_ZONE.value)
        admission_fee_kit = await self._get_kit_by_sku(self.ADMISSION_FEE_SKU)
        interview_fee_kit = await self._get_kit_by_sku(self.INTERVIEW_FEE_SKU)

        if not school_fee_kit:
            raise ValidationError("No School Fee kit found (price_type=by_grade)")
        if not admission_fee_kit:
            raise ValidationError(
                f"Admission fee kit not found (sku_code={self.ADMISSION_FEE_SKU})"
            )
        if not interview_fee_kit:
            raise ValidationError(
                f"Interview fee kit not found (sku_code={self.INTERVIEW_FEE_SKU})"
            )

        # Get all active students
        result = await self.db.execute(
            select(Student)
            .where(Student.status == StudentStatus.ACTIVE.value)
            .options(selectinload(Student.grade))
        )
        students = list(result.scalars().all())

        number_gen = DocumentNumberGenerator(self.db)

        school_fee_created = 0
        transport_created = 0
        skipped = 0
        affected_student_ids: set[int] = set()

        for student in students:
            has_initial_fees = await self._student_has_fee_lines(
                student.id, self.INITIAL_FEE_SKUS
            )
            if not has_initial_fees:
                await self._create_initial_fees_invoice(
                    student,
                    term_id,
                    admission_fee_kit,
                    interview_fee_kit,
                    generated_by_id,
                    number_gen,
                )
                affected_student_ids.add(student.id)

            # Check if student already has school_fee invoice for this term
            existing_school_fee = await self._check_existing_invoice(
                student.id, term_id, InvoiceType.SCHOOL_FEE.value
            )
            if existing_school_fee:
                skipped += 1
                continue

            # Create School Fee invoice
            school_fee_price = await self._get_kit_price(
                school_fee_kit,
                term_id,
                student.grade_id,
                None,
                allow_missing=True,
            )
            if school_fee_price is None:
                skipped += 1
                continue

            school_fee_invoice = Invoice(
                invoice_number=await number_gen.generate("INV"),
                student_id=student.id,
                term_id=term_id,
                invoice_type=InvoiceType.SCHOOL_FEE.value,
                status=InvoiceStatus.ISSUED.value,
                issue_date=date.today(),
                due_date=date.today() + timedelta(days=30),
                created_by_id=generated_by_id,
            )
            school_fee_invoice.lines = []  # Initialize lines collection
            self.db.add(school_fee_invoice)
            await self.db.flush()

            # Add School Fee line
            grade_name = student.grade.name if student.grade else "Unknown"
            school_fee_line = InvoiceLine(
                invoice_id=school_fee_invoice.id,
                kit_id=school_fee_kit.id,
                description=f"{school_fee_kit.name} - {grade_name}",
                quantity=1,
                unit_price=school_fee_price,
                line_total=school_fee_price,
                discount_amount=Decimal("0.00"),
                net_amount=school_fee_price,
                paid_amount=Decimal("0.00"),
                remaining_amount=school_fee_price,
            )
            self.db.add(school_fee_line)
            school_fee_invoice.lines.append(school_fee_line)
            await self.db.flush()  # Get line ID for discount application

            # Apply student discounts for school fees
            await self._apply_student_discounts(
                school_fee_line.id, student.id, InvoiceType.SCHOOL_FEE.value, generated_by_id
            )

            self._recalculate_invoice(school_fee_invoice)
            school_fee_created += 1
            affected_student_ids.add(student.id)

            # Create Transport invoice if student has transport zone
            if student.transport_zone_id and transport_fee_kit:
                existing_transport = await self._check_existing_invoice(
                    student.id, term_id, InvoiceType.TRANSPORT.value
                )
                if not existing_transport:
                    transport_price = await self._get_kit_price(
                        transport_fee_kit,
                        term_id,
                        None,
                        student.transport_zone_id,
                        allow_missing=True,
                    )
                    if transport_price is None:
                        continue

                    transport_invoice = Invoice(
                        invoice_number=await number_gen.generate("INV"),
                        student_id=student.id,
                        term_id=term_id,
                        invoice_type=InvoiceType.TRANSPORT.value,
                        status=InvoiceStatus.ISSUED.value,
                        issue_date=date.today(),
                        due_date=date.today() + timedelta(days=30),
                        created_by_id=generated_by_id,
                    )
                    transport_invoice.lines = []  # Initialize lines collection
                    self.db.add(transport_invoice)
                    await self.db.flush()

                    transport_line = InvoiceLine(
                        invoice_id=transport_invoice.id,
                        kit_id=transport_fee_kit.id,
                        description=f"{transport_fee_kit.name}",
                        quantity=1,
                        unit_price=transport_price,
                        line_total=transport_price,
                        discount_amount=Decimal("0.00"),
                        net_amount=transport_price,
                        paid_amount=Decimal("0.00"),
                        remaining_amount=transport_price,
                    )
                    self.db.add(transport_line)
                    transport_invoice.lines.append(transport_line)
                    self._recalculate_invoice(transport_invoice)
                    transport_created += 1
                    affected_student_ids.add(student.id)

        await self.audit.log(
            action="invoice.generate_term",
            entity_type="Term",
            entity_id=term_id,
            user_id=generated_by_id,
            new_values={
                "school_fee_invoices": school_fee_created,
                "transport_invoices": transport_created,
                "skipped": skipped,
            },
        )

        await self.db.commit()

        return TermInvoiceGenerationResult(
            school_fee_invoices_created=school_fee_created,
            transport_invoices_created=transport_created,
            students_skipped=skipped,
            total_students_processed=len(students),
            affected_student_ids=list(affected_student_ids),
        )

    async def generate_term_invoices_for_student(
        self, term_id: int, student_id: int, generated_by_id: int
    ) -> TermInvoiceGenerationResult:
        """Generate term invoices for a single student."""
        # Validate term
        result = await self.db.execute(select(Term).where(Term.id == term_id))
        term = result.scalar_one_or_none()
        if not term:
            raise NotFoundError(f"Term with id {term_id} not found")
        if term.status != TermStatus.ACTIVE.value:
            raise ValidationError("Can only generate invoices for active term")

        # Validate student
        result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id)
            .options(selectinload(Student.grade))
        )
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        if student.status != StudentStatus.ACTIVE.value:
            raise ValidationError("Student is not active")

        # Get School Fee and Transport Fee kits
        school_fee_kit = await self._get_kit_by_price_type(PriceType.BY_GRADE.value)
        transport_fee_kit = await self._get_kit_by_price_type(PriceType.BY_ZONE.value)
        admission_fee_kit = await self._get_kit_by_sku(self.ADMISSION_FEE_SKU)
        interview_fee_kit = await self._get_kit_by_sku(self.INTERVIEW_FEE_SKU)

        if not school_fee_kit:
            raise ValidationError("No School Fee kit found (price_type=by_grade)")
        if not admission_fee_kit:
            raise ValidationError(
                f"Admission fee kit not found (sku_code={self.ADMISSION_FEE_SKU})"
            )
        if not interview_fee_kit:
            raise ValidationError(
                f"Interview fee kit not found (sku_code={self.INTERVIEW_FEE_SKU})"
            )

        number_gen = DocumentNumberGenerator(self.db)
        school_fee_created = 0
        transport_created = 0
        skipped = 0
        created_any_invoice = False

        has_initial_fees = await self._student_has_fee_lines(
            student.id, self.INITIAL_FEE_SKUS
        )
        if not has_initial_fees:
            await self._create_initial_fees_invoice(
                student,
                term_id,
                admission_fee_kit,
                interview_fee_kit,
                generated_by_id,
                number_gen,
            )
            created_any_invoice = True

        existing_school_fee = await self._check_existing_invoice(
            student.id, term_id, InvoiceType.SCHOOL_FEE.value
        )
        if existing_school_fee:
            skipped += 1
        else:
            school_fee_price = await self._get_kit_price(
                school_fee_kit, term_id, student.grade_id, None
            )

            school_fee_invoice = Invoice(
                invoice_number=await number_gen.generate("INV"),
                student_id=student.id,
                term_id=term_id,
                invoice_type=InvoiceType.SCHOOL_FEE.value,
                status=InvoiceStatus.ISSUED.value,
                issue_date=date.today(),
                due_date=date.today() + timedelta(days=30),
                created_by_id=generated_by_id,
            )
            school_fee_invoice.lines = []
            self.db.add(school_fee_invoice)
            await self.db.flush()

            grade_name = student.grade.name if student.grade else "Unknown"
            school_fee_line = InvoiceLine(
                invoice_id=school_fee_invoice.id,
                kit_id=school_fee_kit.id,
                description=f"{school_fee_kit.name} - {grade_name}",
                quantity=1,
                unit_price=school_fee_price,
                line_total=school_fee_price,
                discount_amount=Decimal("0.00"),
                net_amount=school_fee_price,
                paid_amount=Decimal("0.00"),
                remaining_amount=school_fee_price,
            )
            self.db.add(school_fee_line)
            school_fee_invoice.lines.append(school_fee_line)
            await self.db.flush()

            await self._apply_student_discounts(
                school_fee_line.id, student.id, InvoiceType.SCHOOL_FEE.value, generated_by_id
            )
            self._recalculate_invoice(school_fee_invoice)
            school_fee_created += 1

        if student.transport_zone_id and transport_fee_kit:
            existing_transport = await self._check_existing_invoice(
                student.id, term_id, InvoiceType.TRANSPORT.value
            )
            if existing_transport:
                skipped += 1
            else:
                transport_price = await self._get_kit_price(
                    transport_fee_kit, term_id, None, student.transport_zone_id
                )
                transport_invoice = Invoice(
                    invoice_number=await number_gen.generate("INV"),
                    student_id=student.id,
                    term_id=term_id,
                    invoice_type=InvoiceType.TRANSPORT.value,
                    status=InvoiceStatus.ISSUED.value,
                    issue_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                    created_by_id=generated_by_id,
                )
                transport_invoice.lines = []
                self.db.add(transport_invoice)
                await self.db.flush()

                transport_line = InvoiceLine(
                    invoice_id=transport_invoice.id,
                    kit_id=transport_fee_kit.id,
                    description=f"{transport_fee_kit.name}",
                    quantity=1,
                    unit_price=transport_price,
                    line_total=transport_price,
                    discount_amount=Decimal("0.00"),
                    net_amount=transport_price,
                    paid_amount=Decimal("0.00"),
                    remaining_amount=transport_price,
                )
                self.db.add(transport_line)
                transport_invoice.lines.append(transport_line)
                await self.db.flush()
                self._recalculate_invoice(transport_invoice)
                transport_created += 1

        await self.db.commit()
        affected = [student_id] if (created_any_invoice or school_fee_created > 0 or transport_created > 0) else []
        return TermInvoiceGenerationResult(
            school_fee_invoices_created=school_fee_created,
            transport_invoices_created=transport_created,
            students_skipped=skipped,
            total_students_processed=1,
            affected_student_ids=affected,
        )

    async def _get_kit_by_price_type(self, price_type: str) -> Kit | None:
        """Get an active kit by price_type."""
        result = await self.db.execute(
            select(Kit).where(Kit.price_type == price_type, Kit.is_active == True)
        )
        return result.scalar_one_or_none()

    async def _get_kit_by_sku(self, sku_code: str) -> Kit | None:
        """Get an active kit by sku_code."""
        result = await self.db.execute(
            select(Kit).where(Kit.sku_code == sku_code, Kit.is_active == True)
        )
        return result.scalar_one_or_none()

    async def _check_existing_invoice(
        self, student_id: int, term_id: int, invoice_type: str
    ) -> bool:
        """Check if an invoice already exists for student/term/type."""
        result = await self.db.execute(
            select(Invoice.id).where(
                Invoice.student_id == student_id,
                Invoice.term_id == term_id,
                Invoice.invoice_type == invoice_type,
                Invoice.status != InvoiceStatus.CANCELLED.value,
                Invoice.status != InvoiceStatus.VOID.value,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _student_has_fee_lines(
        self, student_id: int, sku_codes: set[str]
    ) -> bool:
        """Check if a student already has invoice lines for given SKU codes."""
        result = await self.db.execute(
            select(InvoiceLine.id)
            .join(Kit, InvoiceLine.kit_id == Kit.id)
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .where(
                Invoice.student_id == student_id,
                Kit.sku_code.in_(sku_codes),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _ensure_single_fee_allowed(
        self, invoice: Invoice, kit: Kit, quantity: int
    ) -> None:
        """Ensure admission/interview fees are billed only once per student."""
        if kit.sku_code not in self.INITIAL_FEE_SKUS:
            return
        if quantity != 1:
            raise ValidationError(f"'{kit.name}' must have quantity 1")
        if any(line.kit_id == kit.id for line in invoice.lines):
            raise ValidationError(f"'{kit.name}' already billed for this student")
        has_existing = await self._student_has_fee_lines(invoice.student_id, {kit.sku_code})
        if has_existing:
            raise ValidationError(f"'{kit.name}' already billed for this student")

    async def _create_initial_fees_invoice(
        self,
        student: Student,
        term_id: int,
        admission_fee_kit: Kit,
        interview_fee_kit: Kit,
        generated_by_id: int,
        number_gen: DocumentNumberGenerator,
    ) -> Invoice:
        """Create a single invoice with admission + interview fees."""
        admission_price = await self._get_kit_price(
            admission_fee_kit, term_id, student.grade_id, student.transport_zone_id
        )
        interview_price = await self._get_kit_price(
            interview_fee_kit, term_id, student.grade_id, student.transport_zone_id
        )

        invoice = Invoice(
            invoice_number=await number_gen.generate("INV"),
            student_id=student.id,
            term_id=term_id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            created_by_id=generated_by_id,
        )
        invoice.lines = []
        self.db.add(invoice)
        await self.db.flush()

        admission_line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=admission_fee_kit.id,
            description=admission_fee_kit.name,
            quantity=1,
            unit_price=admission_price,
            line_total=admission_price,
            discount_amount=Decimal("0.00"),
            net_amount=admission_price,
            paid_amount=Decimal("0.00"),
            remaining_amount=admission_price,
        )
        interview_line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=interview_fee_kit.id,
            description=interview_fee_kit.name,
            quantity=1,
            unit_price=interview_price,
            line_total=interview_price,
            discount_amount=Decimal("0.00"),
            net_amount=interview_price,
            paid_amount=Decimal("0.00"),
            remaining_amount=interview_price,
        )
        self.db.add(admission_line)
        self.db.add(interview_line)
        invoice.lines.extend([admission_line, interview_line])
        self._recalculate_invoice(invoice)
        return invoice

    # --- Payment Recording (called by Payment service) ---

    async def record_line_payment(
        self, line_id: int, amount: Decimal
    ) -> InvoiceLine:
        """Record a payment against a specific invoice line.

        This method is called by the Payment service during allocation.
        """
        result = await self.db.execute(
            select(InvoiceLine)
            .where(InvoiceLine.id == line_id)
            .options(selectinload(InvoiceLine.invoice))
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {line_id} not found")

        if amount > line.remaining_amount:
            raise ValidationError(
                f"Payment amount {amount} exceeds remaining {line.remaining_amount}"
            )

        line.paid_amount = round_money(line.paid_amount + amount)
        line.remaining_amount = round_money(line.net_amount - line.paid_amount)

        # Recalculate invoice totals
        invoice = line.invoice
        self._recalculate_invoice(invoice)

        return line

    async def reverse_line_payment(
        self, line_id: int, amount: Decimal
    ) -> InvoiceLine:
        """Reverse a payment against a specific invoice line.

        This method is called by the Payment service during payment reversal.
        """
        result = await self.db.execute(
            select(InvoiceLine)
            .where(InvoiceLine.id == line_id)
            .options(selectinload(InvoiceLine.invoice))
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {line_id} not found")

        if amount > line.paid_amount:
            raise ValidationError(
                f"Reversal amount {amount} exceeds paid amount {line.paid_amount}"
            )

        line.paid_amount = round_money(line.paid_amount - amount)
        line.remaining_amount = round_money(line.net_amount - line.paid_amount)

        # Recalculate invoice totals
        invoice = line.invoice
        self._recalculate_invoice(invoice)

        return line
