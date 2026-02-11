"""Service for Reservation module."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.exceptions import NotFoundError, ValidationError
from src.core.documents.number_generator import DocumentNumberGenerator
from src.modules.inventory.models import (
    Issuance,
    IssuanceItem,
    IssuanceStatus,
    IssuanceType,
    RecipientType,
    Stock,
)
from src.modules.inventory.service import InventoryService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceLineComponent, InvoiceStatus
from src.modules.items.models import Item, ItemType, Kit, KitItem
from src.modules.reservations.models import Reservation, ReservationItem, ReservationStatus
from src.modules.students.models import Student


class ReservationService:
    """Service for creating and managing reservations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.inventory = InventoryService(db)

    async def get_by_id(self, reservation_id: int) -> Reservation:
        """Get reservation by ID with items and student."""
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(
                selectinload(Reservation.student),
                selectinload(Reservation.items).selectinload(ReservationItem.item),
            )
        )
        reservation = result.scalar_one_or_none()
        if not reservation:
            raise NotFoundError(f"Reservation with id {reservation_id} not found")
        return reservation

    async def get_by_invoice_line_id(self, invoice_line_id: int) -> Reservation | None:
        """Get reservation by invoice line ID."""
        result = await self.db.execute(
            select(Reservation).where(Reservation.invoice_line_id == invoice_line_id)
        )
        return result.scalar_one_or_none()

    async def list_reservations(
        self,
        student_id: int | None = None,
        invoice_id: int | None = None,
        status: ReservationStatus | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Reservation], int]:
        """List reservations with filters."""
        query = (
            select(Reservation)
            .options(
                selectinload(Reservation.student),
                selectinload(Reservation.items).selectinload(ReservationItem.item),
            )
            .order_by(Reservation.created_at.desc())
        )

        if student_id is not None:
            query = query.where(Reservation.student_id == student_id)
        if invoice_id is not None:
            query = query.where(Reservation.invoice_id == invoice_id)
        if status is not None:
            query = query.where(Reservation.status == status.value)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        reservations = list(result.scalars().all())

        return reservations, total

    async def sync_for_invoice(self, invoice_id: int, user_id: int) -> None:
        """Sync reservations for all lines in an invoice.
        
        Логика:
        - При issue инвойса: создаются резервации для всех product‑китов (до оплаты).
        - При отмене инвойса (cancelled/void): резервации автоматически отменяются.
        - При неполной оплате: резервации остаются (можно выдавать до оплаты).
        """
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.lines).selectinload(InvoiceLine.kit),
                selectinload(Invoice.lines).selectinload(InvoiceLine.components).selectinload(InvoiceLineComponent.item),
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice with id {invoice_id} not found")

        # Если инвойс отменён или аннулирован — отменяем все резервации
        if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.VOID.value):
            for line in invoice.lines:
                existing = await self.get_by_invoice_line_id(line.id)
                if existing and existing.status != ReservationStatus.CANCELLED.value:
                    await self.cancel_reservation(
                        existing.id,
                        cancelled_by_id=user_id,
                        reason=f"Invoice {invoice_id} was {invoice.status}",
                        commit=False,
                    )
            return

        # Для issued/partially_paid/paid инвойсов — создаём резервации для product‑китов
        for line in invoice.lines:
            if not line.kit or line.kit.item_type != ItemType.PRODUCT.value:
                continue

            existing = await self.get_by_invoice_line_id(line.id)
            if not existing:
                await self.create_from_line(line.id, created_by_id=user_id, commit=False)

    async def create_from_line(
        self, invoice_line_id: int, created_by_id: int, commit: bool = True
    ) -> Reservation | None:
        """Create a reservation from an invoice line (independent of payment status)."""
        line = await self._get_invoice_line(invoice_line_id)

        existing = await self.get_by_invoice_line_id(invoice_line_id)
        if existing:
            return existing

        reservation_items = await self._build_reservation_items(line)
        if not reservation_items:
            return None

        reservation = Reservation(
            student_id=line.invoice.student_id,
            invoice_id=line.invoice_id,
            invoice_line_id=line.id,
            status=ReservationStatus.PENDING.value,
            created_by_id=created_by_id,
        )
        reservation.items = []
        self.db.add(reservation)
        await self.db.flush()

        for item_id, quantity_required in reservation_items:
            reservation_item = ReservationItem(
                reservation_id=reservation.id,
                item_id=item_id,
                quantity_required=quantity_required,
                quantity_issued=0,
            )
            self.db.add(reservation_item)
            reservation.items.append(reservation_item)

        reservation.status = self._calculate_status(reservation)

        await self.audit.log(
            action="reservation.create",
            entity_type="Reservation",
            entity_id=reservation.id,
            user_id=created_by_id,
            new_values={
                "invoice_id": reservation.invoice_id,
                "invoice_line_id": reservation.invoice_line_id,
                "status": reservation.status,
            },
        )

        if commit:
            await self.db.commit()
            return await self.get_by_id(reservation.id)
        return reservation

    async def issue_items(
        self, reservation_id: int, items: list[tuple[int, int]], issued_by_id: int, notes: str | None = None
    ) -> Issuance:
        """Issue reserved items for a reservation."""
        reservation = await self.get_by_id(reservation_id)

        if reservation.status == ReservationStatus.CANCELLED.value:
            raise ValidationError("Reservation is cancelled")
        if reservation.status == ReservationStatus.FULFILLED.value:
            raise ValidationError("Reservation already fulfilled")

        student = await self._get_student(reservation.student_id)

        # Build map for quick access
        item_map = {ri.id: ri for ri in reservation.items}

        # Filter out items with quantity 0 and validate at least one item to issue
        items_to_issue = [(rid, qty) for rid, qty in items if qty > 0]
        if not items_to_issue:
            raise ValidationError("At least one item with quantity > 0 must be provided")

        issuance = await self._create_issuance(
            reservation=reservation,
            student=student,
            issued_by_id=issued_by_id,
            notes=notes,
        )

        for reservation_item_id, quantity in items_to_issue:
            if reservation_item_id not in item_map:
                raise ValidationError(f"Reservation item {reservation_item_id} not found")
            reservation_item = item_map[reservation_item_id]

            if quantity > (reservation_item.quantity_required - reservation_item.quantity_issued):
                raise ValidationError("Issue quantity exceeds required remaining amount")

            # Demand-based reservation: do not physically allocate stock to a specific reservation.
            # Issuance is allowed as long as there is stock on hand.
            stock_result = await self.db.execute(
                select(Stock)
                .where(Stock.item_id == reservation_item.item_id)
                .with_for_update()
            )
            stock = stock_result.scalar_one_or_none()
            if not stock:
                item = await self.inventory._get_item(reservation_item.item_id)
                raise ValidationError(f"No stock for item '{item.name}'. Receive stock first.")
            if quantity > stock.quantity_on_hand:
                raise ValidationError(
                    f"Insufficient stock for reservation_item {reservation_item.id}. "
                    f"On hand: {stock.quantity_on_hand}, requested: {quantity}"
                )

            unit_cost = stock.average_cost if stock else Decimal("0.00")

            await self.inventory._issue_stock_internal(
                stock=stock,
                quantity=quantity,
                reference_type="reservation",
                reference_id=reservation.id,
                issued_by_id=issued_by_id,
            )
            reservation_item.quantity_issued += quantity

            issuance_item = IssuanceItem(
                issuance_id=issuance.id,
                item_id=reservation_item.item_id,
                quantity=quantity,
                unit_cost=unit_cost,
                reservation_item_id=reservation_item.id,
            )
            self.db.add(issuance_item)

        reservation.status = self._calculate_status(reservation)

        await self.audit.log(
            action="reservation.issue",
            entity_type="Reservation",
            entity_id=reservation.id,
            user_id=issued_by_id,
            new_values={"status": reservation.status},
        )

        await self.db.commit()
        await self.db.refresh(issuance)
        return issuance

    async def cancel_reservation(
        self,
        reservation_id: int,
        cancelled_by_id: int,
        reason: str | None = None,
        commit: bool = True,
    ) -> Reservation:
        """Cancel a reservation and return issued items if needed."""
        reservation = await self.get_by_id(reservation_id)

        if reservation.status == ReservationStatus.CANCELLED.value:
            raise ValidationError("Reservation is already cancelled")

        # Cancel all issuances linked to this reservation (return stock)
        issuances_result = await self.db.execute(
            select(Issuance).where(
                Issuance.reservation_id == reservation.id,
                Issuance.status == IssuanceStatus.COMPLETED.value,
            )
        )
        issuances = list(issuances_result.scalars().all())
        for issuance in issuances:
            await self.inventory.cancel_issuance(
                issuance_id=issuance.id,
                cancelled_by_id=cancelled_by_id,
                commit=False,
            )

        reservation.status = ReservationStatus.CANCELLED.value

        await self.audit.log(
            action="reservation.cancel",
            entity_type="Reservation",
            entity_id=reservation.id,
            user_id=cancelled_by_id,
            new_values={"status": reservation.status},
            comment=reason,
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(reservation)
        return reservation

    # --- Helpers ---

    async def _get_invoice_line(self, line_id: int) -> InvoiceLine:
        result = await self.db.execute(
            select(InvoiceLine)
            .where(InvoiceLine.id == line_id)
            .options(
                selectinload(InvoiceLine.invoice),
                selectinload(InvoiceLine.components).selectinload(InvoiceLineComponent.item),
                selectinload(InvoiceLine.kit).selectinload(Kit.kit_items).selectinload(KitItem.item),
                selectinload(InvoiceLine.kit).selectinload(Kit.kit_items).selectinload(KitItem.default_item),
            )
        )
        line = result.scalar_one_or_none()
        if not line:
            raise NotFoundError(f"Invoice line with id {line_id} not found")
        return line

    async def _get_student(self, student_id: int) -> Student:
        result = await self.db.execute(select(Student).where(Student.id == student_id))
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError(f"Student with id {student_id} not found")
        return student

    async def _build_reservation_items(self, line: InvoiceLine) -> list[tuple[int, int]]:
        """Build list of (item_id, quantity_required) for reservation from an invoice line.

        If configurable components are defined for the line (invoice_line_components),
        they take precedence over the static Kit.kit_items definition.
        """
        items: list[tuple[int, int]] = []

        # Prefer explicit components if present
        if hasattr(line, "components") and line.components:
            for comp in line.components:
                if comp.quantity <= 0:
                    continue
                items.append((comp.item_id, comp.quantity))
            return items

        # Fallback to kit definition
        if line.kit and hasattr(line.kit, "kit_items"):
            if line.kit.item_type != ItemType.PRODUCT.value:
                return items
            # Ensure kit_items are loaded (should be via selectinload, but check)
            if not line.kit.kit_items:
                return items
            for kit_item in line.kit.kit_items:
                # Determine which item_id to use based on source_type
                item_id_to_use: int | None = None
                if kit_item.source_type == "item":
                    item_id_to_use = kit_item.item_id
                elif kit_item.source_type == "variant":
                    item_id_to_use = kit_item.default_item_id

                if not item_id_to_use:
                    continue

                # Verify item exists and is a product
                item_result = await self.db.execute(
                    select(Item).where(Item.id == item_id_to_use)
                )
                item = item_result.scalar_one_or_none()
                if not item or item.item_type != ItemType.PRODUCT.value:
                    continue

                quantity_required = kit_item.quantity * line.quantity
                items.append((item_id_to_use, quantity_required))

        return items

    def _calculate_status(self, reservation: Reservation) -> str:
        total_required = sum(item.quantity_required for item in reservation.items)
        total_issued = sum(item.quantity_issued for item in reservation.items)

        if total_required > 0 and total_issued >= total_required:
            return ReservationStatus.FULFILLED.value
        if total_issued > 0:
            return ReservationStatus.PARTIAL.value
        return ReservationStatus.PENDING.value

    async def _create_issuance(
        self,
        reservation: Reservation,
        student: Student,
        issued_by_id: int,
        notes: str | None,
    ) -> Issuance:
        number_gen = DocumentNumberGenerator(self.db)
        issuance = Issuance(
            issuance_number=await number_gen.generate("ISS"),
            issuance_type=IssuanceType.RESERVATION.value,
            recipient_type=RecipientType.STUDENT.value,
            recipient_id=student.id,
            recipient_name=f"{student.first_name} {student.last_name}",
            reservation_id=reservation.id,
            issued_by_id=issued_by_id,
            notes=notes,
            status=IssuanceStatus.COMPLETED.value,
        )
        self.db.add(issuance)
        await self.db.flush()
        return issuance
