"""Service layer for Purchase Orders."""

import csv
import io
from datetime import date, datetime

from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.documents.number_generator import get_document_number
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.inventory.models import MovementType, StockMovement
from src.modules.inventory.schemas import ReceiveStockRequest
from src.modules.inventory.service import InventoryService
from src.modules.procurement.models import (
    GoodsReceivedLine,
    GoodsReceivedNote,
    GoodsReceivedStatus,
    PaymentPurpose,
    PurchaseOrder,
    PurchaseOrderLine,
    ProcurementPayment,
    ProcurementPaymentStatus,
    PurchaseOrderStatus,
)
from src.modules.procurement.schemas import (
    GoodsReceivedFilters,
    GoodsReceivedNoteCreate,
    PaymentPurposeCreate,
    PaymentPurposeUpdate,
    PurchaseOrderCreate,
    PurchaseOrderFilters,
    PurchaseOrderLineCreate,
    PurchaseOrderUpdate,
    ProcurementPaymentCreate,
    ProcurementPaymentFilters,
)
from src.shared.utils.money import round_money
from src.modules.compensations.service import ExpenseClaimService


class PurchaseOrderService:
    """Service for purchase orders."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_purchase_order(
        self, data: PurchaseOrderCreate, created_by_id: int
    ) -> PurchaseOrder:
        """Create a purchase order."""
        await PaymentPurposeService(self.db).get_purpose_by_id(data.purpose_id)
        po_number = await get_document_number(self.db, "PO")
        order_date = data.order_date or date.today()

        purchase_order = PurchaseOrder(
            po_number=po_number,
            supplier_name=data.supplier_name,
            supplier_contact=data.supplier_contact,
            purpose_id=data.purpose_id,
            status=PurchaseOrderStatus.DRAFT.value,
            order_date=order_date,
            expected_delivery_date=data.expected_delivery_date,
            track_to_warehouse=data.track_to_warehouse,
            notes=data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(purchase_order)
        await self.db.flush()

        for index, line in enumerate(data.lines, start=1):
            line_total = Decimal(line.quantity_expected) * line.unit_price
            po_line = PurchaseOrderLine(
                po_id=purchase_order.id,
                item_id=line.item_id,
                description=line.description,
                quantity_expected=line.quantity_expected,
                quantity_cancelled=0,
                unit_price=line.unit_price,
                line_total=line_total,
                quantity_received=0,
                line_order=index,
            )
            self.db.add(po_line)

        await self._recalculate_totals(purchase_order.id)
        await self.db.commit()
        return await self.get_purchase_order_by_id(purchase_order.id)

    async def update_purchase_order(
        self, po_id: int, data: PurchaseOrderUpdate
    ) -> PurchaseOrder:
        """Update a purchase order (draft/ordered only)."""
        purchase_order = await self.get_purchase_order_by_id(po_id)
        if purchase_order.status not in (
            PurchaseOrderStatus.DRAFT.value,
            PurchaseOrderStatus.ORDERED.value,
        ):
            raise ValidationError("Only draft/ordered purchase orders can be updated")

        update_data = data.model_dump(exclude_unset=True)
        lines = update_data.pop("lines", None)

        for field, value in update_data.items():
            setattr(purchase_order, field, value)

        if lines is not None:
            await self.db.execute(
                PurchaseOrderLine.__table__.delete().where(
                    PurchaseOrderLine.po_id == purchase_order.id
                )
            )
            for index, line in enumerate(lines, start=1):
                line_total = Decimal(line.quantity_expected) * line.unit_price
                po_line = PurchaseOrderLine(
                    po_id=purchase_order.id,
                    item_id=line.item_id,
                    description=line.description,
                    quantity_expected=line.quantity_expected,
                    quantity_cancelled=0,
                    unit_price=line.unit_price,
                    line_total=line_total,
                    quantity_received=0,
                    line_order=index,
                )
                self.db.add(po_line)

        if data.purpose_id is not None:
            await PaymentPurposeService(self.db).get_purpose_by_id(data.purpose_id)
            purchase_order.purpose_id = data.purpose_id

        await self._recalculate_totals(purchase_order.id)
        await self.db.commit()
        return await self.get_purchase_order_by_id(purchase_order.id)

    async def submit_purchase_order(self, po_id: int) -> PurchaseOrder:
        """Mark purchase order as ordered."""
        purchase_order = await self.get_purchase_order_by_id(po_id)
        if purchase_order.status != PurchaseOrderStatus.DRAFT.value:
            raise ValidationError("Only draft purchase orders can be submitted")
        purchase_order.status = PurchaseOrderStatus.ORDERED.value
        await self.db.commit()
        return await self.get_purchase_order_by_id(po_id)

    async def cancel_purchase_order(self, po_id: int, reason: str) -> PurchaseOrder:
        """Cancel a purchase order."""
        purchase_order = await self.get_purchase_order_by_id(po_id)
        if purchase_order.status == PurchaseOrderStatus.CLOSED.value:
            raise ValidationError("Closed purchase orders cannot be cancelled")
        purchase_order.status = PurchaseOrderStatus.CANCELLED.value
        purchase_order.cancelled_reason = reason
        await self.db.commit()
        return await self.get_purchase_order_by_id(po_id)

    async def close_purchase_order(self, po_id: int) -> PurchaseOrder:
        """Close a purchase order and cancel remaining quantities."""
        purchase_order = await self.get_purchase_order_by_id(po_id)
        if purchase_order.status == PurchaseOrderStatus.CANCELLED.value:
            raise ValidationError("Cancelled purchase orders cannot be closed")

        for line in purchase_order.lines:
            remaining = (
                line.quantity_expected - line.quantity_received - line.quantity_cancelled
            )
            if remaining > 0:
                line.quantity_cancelled += remaining
                line.line_total = (
                    Decimal(line.quantity_expected - line.quantity_cancelled)
                    * line.unit_price
                )

        purchase_order.status = PurchaseOrderStatus.CLOSED.value
        await self._recalculate_totals(purchase_order.id)
        await self.db.commit()
        return await self.get_purchase_order_by_id(po_id)

    async def get_purchase_order_by_id(self, po_id: int) -> PurchaseOrder:
        """Get purchase order by ID."""
        result = await self.db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(selectinload(PurchaseOrder.lines))
        )
        purchase_order = result.scalar_one_or_none()
        if not purchase_order:
            raise NotFoundError(f"Purchase order {po_id} not found")
        return purchase_order

    async def list_purchase_orders(
        self, filters: PurchaseOrderFilters
    ) -> tuple[list[PurchaseOrder], int]:
        """List purchase orders with filters."""
        query = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))

        if filters.status:
            query = query.where(PurchaseOrder.status == filters.status)
        if filters.supplier_name:
            query = query.where(
                PurchaseOrder.supplier_name.ilike(f"%{filters.supplier_name}%")
            )
        if filters.date_from:
            query = query.where(PurchaseOrder.order_date >= filters.date_from)
        if filters.date_to:
            query = query.where(PurchaseOrder.order_date <= filters.date_to)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(PurchaseOrder.created_at.desc())
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total or 0

    async def _recalculate_totals(self, po_id: int) -> None:
        """Recalculate totals for a purchase order."""
        # We run with AsyncSession(autoflush=False) in production. Flush explicitly so
        # newly added/updated PO lines are visible to the queries below.
        await self.db.flush()

        result = await self.db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(selectinload(PurchaseOrder.lines))
        )
        purchase_order = result.scalar_one_or_none()
        if not purchase_order:
            return

        expected_total = Decimal("0.00")
        received_value = Decimal("0.00")
        total_expected_qty = 0
        total_received_qty = 0

        for line in purchase_order.lines:
            effective_qty = max(0, line.quantity_expected - line.quantity_cancelled)
            line.line_total = Decimal(effective_qty) * line.unit_price
            expected_total += line.line_total
            received_value += Decimal(line.quantity_received) * line.unit_price
            total_expected_qty += effective_qty
            total_received_qty += line.quantity_received

        purchase_order.expected_total = expected_total
        purchase_order.received_value = received_value
        purchase_order.debt_amount = received_value - purchase_order.paid_total

        self._update_status_from_quantities(
            purchase_order, total_expected_qty, total_received_qty
        )

    def _update_status_from_quantities(
        self, purchase_order: PurchaseOrder, total_expected_qty: int, total_received_qty: int
    ) -> None:
        # Cancelled is terminal.
        if purchase_order.status == PurchaseOrderStatus.CANCELLED.value:
            return

        # If PO was manually closed by cancelling all remaining quantities,
        # keep it closed even if payments change later.
        if (
            purchase_order.status == PurchaseOrderStatus.CLOSED.value
            and total_expected_qty == 0
        ):
            return

        if total_received_qty <= 0:
            # No received quantities: keep draft/ordered, otherwise downgrade to ordered.
            if purchase_order.status not in (
                PurchaseOrderStatus.DRAFT.value,
                PurchaseOrderStatus.ORDERED.value,
            ):
                purchase_order.status = PurchaseOrderStatus.ORDERED.value
            return

        if total_expected_qty > 0 and total_received_qty >= total_expected_qty:
            if purchase_order.paid_total >= purchase_order.received_value:
                purchase_order.status = PurchaseOrderStatus.CLOSED.value
            else:
                purchase_order.status = PurchaseOrderStatus.RECEIVED.value
            return

        purchase_order.status = PurchaseOrderStatus.PARTIALLY_RECEIVED.value

    async def bulk_upload_from_csv(
        self, content: bytes | str, created_by_id: int
    ) -> dict:
        """Parse CSV and create one purchase order. One file = one PO; rows = lines.

        Returns dict with po: {id, po_number} or None, and errors: list of {row, message}.
        If any row has errors, PO is not created.
        """
        if isinstance(content, bytes):
            text = content.decode("utf-8-sig")
        else:
            text = content
        reader = csv.DictReader(io.StringIO(text))
        required = {"supplier_name", "purpose", "description", "quantity_expected", "unit_price"}
        if not reader.fieldnames:
            raise ValidationError("CSV has no headers")
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"CSV missing columns: {sorted(missing)}")

        purpose_service = PaymentPurposeService(self.db)
        errors: list[dict] = []
        rows_data: list[dict] = []

        for row_num, row in enumerate(reader, start=2):
            supplier_name = (row.get("supplier_name") or "").strip()
            purpose_name = (row.get("purpose") or "").strip()
            description = (row.get("description") or "").strip()
            qty_str = (row.get("quantity_expected") or "").strip()
            price_str = (row.get("unit_price") or "").strip()

            if row_num == 2:
                if not supplier_name:
                    errors.append({"row": row_num, "message": "supplier_name is required in first row"})
                if not purpose_name:
                    errors.append({"row": row_num, "message": "purpose is required in first row"})

            if not description:
                errors.append({"row": row_num, "message": "description is required"})
                continue
            try:
                qty = int(qty_str)
            except ValueError:
                errors.append({"row": row_num, "message": f"invalid quantity_expected: {qty_str!r}"})
                continue
            if qty <= 0:
                errors.append({"row": row_num, "message": "quantity_expected must be > 0"})
                continue
            try:
                unit_price = round_money(Decimal(price_str))
                if unit_price < 0:
                    errors.append({"row": row_num, "message": "unit_price must be >= 0"})
                    continue
            except Exception:
                errors.append({"row": row_num, "message": f"invalid unit_price: {price_str!r}"})
                continue

            sku = (row.get("sku") or "").strip() or None
            item_id: int | None = None
            if sku:
                try:
                    from src.modules.items.service import ItemService
                    item_service = ItemService(self.db)
                    item = await item_service.get_item_by_sku(sku)
                    item_id = item.id
                except NotFoundError:
                    errors.append({"row": row_num, "message": f"item with SKU '{sku}' not found"})
                    continue

            rows_data.append({
                "row_num": row_num,
                "supplier_name": supplier_name,
                "purpose_name": purpose_name,
                "supplier_contact": (row.get("supplier_contact") or "").strip() or None,
                "order_date_str": (row.get("order_date") or "").strip() or None,
                "expected_delivery_date_str": (row.get("expected_delivery_date") or "").strip() or None,
                "track_to_warehouse_str": (row.get("track_to_warehouse") or "").strip() or None,
                "notes": (row.get("notes") or "").strip() or None,
                "description": description,
                "quantity_expected": qty,
                "unit_price": unit_price,
                "item_id": item_id,
            })

        if not rows_data:
            if errors:
                return {"po": None, "errors": errors}
            raise ValidationError("CSV has no data rows")

        first = rows_data[0]
        if not first["supplier_name"]:
            errors.append({"row": first["row_num"], "message": "supplier_name is required in first row"})
        if not first["purpose_name"]:
            errors.append({"row": first["row_num"], "message": "purpose is required in first row"})

        if errors:
            return {"po": None, "errors": errors}

        purpose = await purpose_service.get_purpose_by_name(first["purpose_name"])
        order_date: date | None = None
        if first["order_date_str"]:
            try:
                order_date = date.fromisoformat(first["order_date_str"])
            except ValueError:
                errors.append({"row": first["row_num"], "message": f"invalid order_date: {first['order_date_str']!r}"})
        if not order_date:
            order_date = date.today()

        expected_delivery_date: date | None = None
        if first["expected_delivery_date_str"]:
            try:
                expected_delivery_date = date.fromisoformat(first["expected_delivery_date_str"])
            except ValueError:
                errors.append({"row": first["row_num"], "message": f"invalid expected_delivery_date: {first['expected_delivery_date_str']!r}"})

        track_to_warehouse = True
        if first["track_to_warehouse_str"]:
            low = first["track_to_warehouse_str"].lower()
            if low in ("false", "0", "no"):
                track_to_warehouse = False
            elif low in ("true", "1", "yes"):
                track_to_warehouse = True

        lines: list[PurchaseOrderLineCreate] = [
            PurchaseOrderLineCreate(
                item_id=r["item_id"],
                description=r["description"],
                quantity_expected=r["quantity_expected"],
                unit_price=r["unit_price"],
            )
            for r in rows_data
        ]
        create_data = PurchaseOrderCreate(
            supplier_name=first["supplier_name"],
            supplier_contact=first["supplier_contact"],
            purpose_id=purpose.id,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            track_to_warehouse=track_to_warehouse,
            notes=first["notes"] or None,
            lines=lines,
        )
        po = await self.create_purchase_order(create_data, created_by_id)
        return {"po": {"id": po.id, "po_number": po.po_number}, "errors": []}

    async def parse_po_lines_from_csv(self, content: bytes | str) -> dict:
        """Parse CSV into PO lines only (no PO created). For use on create-PO form.

        CSV columns: sku, item_name, quantity_expected, unit_price.
        Returns { lines: [{ item_id?, description, quantity_expected, unit_price }], errors: [...] }.
        """
        if isinstance(content, bytes):
            text = content.decode("utf-8-sig")
        else:
            text = content
        reader = csv.DictReader(io.StringIO(text))
        required = {"sku", "item_name", "quantity_expected", "unit_price"}
        if not reader.fieldnames:
            raise ValidationError("CSV has no headers")
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"CSV missing columns: {sorted(missing)}")

        errors: list[dict] = []
        lines_out: list[dict] = []
        from src.modules.items.service import ItemService
        item_service = ItemService(self.db)

        for row_num, row in enumerate(reader, start=2):
            sku = (row.get("sku") or "").strip() or None
            item_name = (row.get("item_name") or "").strip()
            qty_str = (row.get("quantity_expected") or "").strip()
            price_str = (row.get("unit_price") or "").strip()

            if not qty_str and not price_str and not item_name and not sku:
                continue
            if not qty_str:
                errors.append({"row": row_num, "message": "quantity_expected is required"})
                continue
            if not price_str:
                errors.append({"row": row_num, "message": "unit_price is required"})
                continue
            try:
                qty = int(qty_str)
            except ValueError:
                errors.append({"row": row_num, "message": f"invalid quantity_expected: {qty_str!r}"})
                continue
            if qty <= 0:
                errors.append({"row": row_num, "message": "quantity_expected must be > 0"})
                continue
            try:
                unit_price = round_money(Decimal(price_str))
                if unit_price < 0:
                    errors.append({"row": row_num, "message": "unit_price must be >= 0"})
                    continue
            except Exception:
                errors.append({"row": row_num, "message": f"invalid unit_price: {price_str!r}"})
                continue

            item_id: int | None = None
            description = item_name
            if sku:
                try:
                    item = await item_service.get_item_by_sku(sku)
                    item_id = item.id
                    if not description:
                        description = item.name
                except NotFoundError:
                    errors.append({"row": row_num, "message": f"item with SKU '{sku}' not found"})
                    continue
            if not description:
                errors.append({"row": row_num, "message": "item_name or sku is required"})
                continue

            lines_out.append({
                "item_id": item_id,
                "description": description,
                "quantity_expected": qty,
                "unit_price": unit_price,
            })

        return {"lines": lines_out, "errors": errors}


class GoodsReceivedService:
    """Service for goods received notes (GRN)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.inventory = InventoryService(db)
        self.po_service = PurchaseOrderService(db)

    async def create_grn(
        self, data: GoodsReceivedNoteCreate, received_by_id: int
    ) -> GoodsReceivedNote:
        """Create a draft GRN."""
        po = await self.po_service.get_purchase_order_by_id(data.po_id)
        if po.status in (PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value):
            raise ValidationError("Cannot receive goods for cancelled/closed PO")
        received_date = data.received_date or date.today()

        grn_number = await get_document_number(self.db, "GRN")
        grn = GoodsReceivedNote(
            grn_number=grn_number,
            po_id=po.id,
            status=GoodsReceivedStatus.DRAFT.value,
            received_date=received_date,
            received_by_id=received_by_id,
            notes=data.notes,
        )
        self.db.add(grn)
        await self.db.flush()

        # Filter out lines with quantity_received = 0 (not being received in this GRN)
        lines_to_process = [line for line in data.lines if line.quantity_received > 0]
        if not lines_to_process:
            raise ValidationError("At least one line must have quantity_received > 0")

        po_lines = {line.id: line for line in po.lines}
        for line in lines_to_process:
            if line.po_line_id not in po_lines:
                raise ValidationError("GRN line does not belong to purchase order")
            po_line = po_lines[line.po_line_id]
            remaining = (
                po_line.quantity_expected
                - po_line.quantity_cancelled
                - po_line.quantity_received
            )
            if line.quantity_received > remaining:
                raise ValidationError(
                    f"Quantity exceeds remaining for PO line {po_line.id}"
                )

            grn_line = GoodsReceivedLine(
                grn_id=grn.id,
                po_line_id=po_line.id,
                item_id=po_line.item_id,
                quantity_received=line.quantity_received,
            )
            self.db.add(grn_line)

        await self.db.commit()
        return await self.get_grn_by_id(grn.id)

    async def approve_grn(
        self,
        grn_id: int,
        approved_by_id: int,
        allow_self_approve: bool,
    ) -> GoodsReceivedNote:
        """Approve GRN and apply stock movements / PO updates."""
        grn = await self.get_grn_by_id(grn_id)
        if grn.status != GoodsReceivedStatus.DRAFT.value:
            raise ValidationError("Only draft GRNs can be approved")
        if not allow_self_approve and grn.received_by_id == approved_by_id:
            raise ValidationError("Cannot approve own GRN")

        po = await self.po_service.get_purchase_order_by_id(grn.po_id)
        if po.status in (PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value):
            raise ValidationError("Cannot approve GRN for cancelled/closed PO")
        po_lines = {line.id: line for line in po.lines}

        for line in grn.lines:
            po_line = po_lines.get(line.po_line_id)
            if not po_line:
                raise ValidationError("GRN line does not belong to purchase order")
            remaining = (
                po_line.quantity_expected
                - po_line.quantity_cancelled
                - po_line.quantity_received
            )
            if line.quantity_received > remaining:
                raise ValidationError(
                    f"Quantity exceeds remaining for PO line {po_line.id}"
                )

            po_line.quantity_received += line.quantity_received

            if po.track_to_warehouse and line.item_id:
                receive_data = ReceiveStockRequest(
                    item_id=line.item_id,
                    quantity=line.quantity_received,
                    unit_cost=po_line.unit_price,
                    reference_type="grn",
                    reference_id=grn.id,
                    notes=f"GRN {grn.grn_number}",
                )
                await self.inventory.receive_stock(
                    receive_data, approved_by_id, commit=False
                )

        grn.status = GoodsReceivedStatus.APPROVED.value
        grn.approved_by_id = approved_by_id
        grn.approved_at = datetime.utcnow()

        await self.po_service._recalculate_totals(po.id)
        await self.db.commit()
        return await self.get_grn_by_id(grn.id)

    async def cancel_grn(self, grn_id: int) -> GoodsReceivedNote:
        """Cancel a draft GRN."""
        grn = await self.get_grn_by_id(grn_id)
        if grn.status != GoodsReceivedStatus.DRAFT.value:
            raise ValidationError("Only draft GRNs can be cancelled")
        grn.status = GoodsReceivedStatus.CANCELLED.value
        await self.db.commit()
        return await self.get_grn_by_id(grn.id)

    async def rollback_purchase_order_receiving(
        self, po_id: int, *, rolled_back_by_id: int, reason: str
    ) -> PurchaseOrder:
        """
        Rollback receiving for a PO by cancelling all APPROVED GRNs and reverting:
        - PO line.quantity_received
        - inventory receipt movements (if track_to_warehouse=True)

        Safety:
        - Blocks rollback if there are later receipt movements for the same item
          (outside of GRNs being rolled back), to avoid corrupting average cost.
        """
        if not (reason and reason.strip()):
            raise ValidationError("Reason is required")

        po = await self.po_service.get_purchase_order_by_id(po_id)

        approved_grns = list(
            (
                await self.db.execute(
                    select(GoodsReceivedNote)
                    .where(GoodsReceivedNote.po_id == po_id)
                    .where(GoodsReceivedNote.status == GoodsReceivedStatus.APPROVED.value)
                    .options(selectinload(GoodsReceivedNote.lines))
                    .order_by(GoodsReceivedNote.created_at.desc(), GoodsReceivedNote.id.desc())
                )
            )
            .scalars()
            .all()
        )
        if not approved_grns:
            return po

        # Roll back newest GRNs first so "later receipt movement" checks work.
        for grn in approved_grns:
            await self._rollback_grn_instance(
                grn, rolled_back_by_id=rolled_back_by_id, reason=reason, commit=False
            )

        await self.po_service._recalculate_totals(po.id)
        await self.db.commit()
        return await self.po_service.get_purchase_order_by_id(po.id)

    async def rollback_grn(
        self, grn_id: int, *, rolled_back_by_id: int, reason: str
    ) -> GoodsReceivedNote:
        """Rollback a single approved GRN (SUPER_ADMIN only)."""
        grn = await self.get_grn_by_id(grn_id)
        if grn.status != GoodsReceivedStatus.APPROVED.value:
            raise ValidationError("Only approved GRNs can be rolled back")

        await self._rollback_grn_instance(grn, rolled_back_by_id=rolled_back_by_id, reason=reason, commit=True)
        return await self.get_grn_by_id(grn_id)

    async def _rollback_grn_instance(
        self,
        grn: GoodsReceivedNote,
        *,
        rolled_back_by_id: int,
        reason: str,
        commit: bool,
    ) -> None:
        if not (reason and reason.strip()):
            raise ValidationError("Reason is required")

        po = await self.po_service.get_purchase_order_by_id(grn.po_id)

        po_lines = {line.id: line for line in po.lines}

        for line in grn.lines:
            po_line = po_lines.get(line.po_line_id)
            if not po_line:
                raise ValidationError("GRN line does not belong to purchase order")
            if po_line.quantity_received < line.quantity_received:
                raise ValidationError("Cannot rollback: PO line received quantity is inconsistent")
            po_line.quantity_received -= line.quantity_received

            if po.track_to_warehouse and line.item_id:
                receipt_movement = await self.db.scalar(
                    select(StockMovement)
                    .where(StockMovement.item_id == line.item_id)
                    .where(StockMovement.movement_type == MovementType.RECEIPT.value)
                    .where(StockMovement.reference_type == "grn")
                    .where(StockMovement.reference_id == grn.id)
                    .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                )
                if receipt_movement:
                    later_receipts = await self.db.scalar(
                        select(func.count())
                        .select_from(StockMovement)
                        .where(StockMovement.item_id == line.item_id)
                        .where(StockMovement.movement_type == MovementType.RECEIPT.value)
                        .where(
                            (StockMovement.created_at > receipt_movement.created_at)
                            | (
                                (StockMovement.created_at == receipt_movement.created_at)
                                & (StockMovement.id > receipt_movement.id)
                            )
                        )
                    )
                    if int(later_receipts or 0) > 0:
                        raise ValidationError(
                            "Cannot rollback: item has later receipt movements; "
                            "rollback would corrupt average cost"
                        )

                unit_cost = (receipt_movement.unit_cost if receipt_movement else None) or po_line.unit_price
                await self.inventory.apply_receipt_signed(
                    item_id=line.item_id,
                    quantity_delta=-line.quantity_received,
                    unit_cost=unit_cost,
                    reference_type="grn_rollback",
                    reference_id=grn.id,
                    notes=f"Rollback GRN {grn.grn_number}: {reason.strip()}",
                    created_by_id=rolled_back_by_id,
                    audit_action="inventory.receive.rollback",
                    commit=False,
                )

        grn.status = GoodsReceivedStatus.CANCELLED.value
        if grn.notes:
            grn.notes = f"{grn.notes}\n[ROLLED BACK] {reason.strip()}"
        else:
            grn.notes = f"[ROLLED BACK] {reason.strip()}"

        await self.po_service._recalculate_totals(po.id)
        if commit:
            await self.db.commit()

    async def get_grn_by_id(self, grn_id: int) -> GoodsReceivedNote:
        """Get GRN by ID."""
        result = await self.db.execute(
            select(GoodsReceivedNote)
            .where(GoodsReceivedNote.id == grn_id)
            .options(selectinload(GoodsReceivedNote.lines))
        )
        grn = result.scalar_one_or_none()
        if not grn:
            raise NotFoundError(f"GRN {grn_id} not found")
        return grn

    async def list_grns(
        self, filters: GoodsReceivedFilters
    ) -> tuple[list[GoodsReceivedNote], int]:
        """List GRNs with filters."""
        query = select(GoodsReceivedNote).options(selectinload(GoodsReceivedNote.lines))
        if filters.po_id:
            query = query.where(GoodsReceivedNote.po_id == filters.po_id)
        if filters.status:
            query = query.where(GoodsReceivedNote.status == filters.status)
        if filters.date_from:
            query = query.where(GoodsReceivedNote.received_date >= filters.date_from)
        if filters.date_to:
            query = query.where(GoodsReceivedNote.received_date <= filters.date_to)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(GoodsReceivedNote.created_at.desc())
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total or 0


class ProcurementDashboardService:
    """Service for procurement dashboard statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(self) -> dict:
        """Get dashboard statistics."""
        # Total supplier debt (sum of debt_amount for all active POs)
        total_debt_result = await self.db.execute(
            select(func.coalesce(func.sum(PurchaseOrder.debt_amount), Decimal("0.00")))
            .where(
                PurchaseOrder.status.notin_(
                    [PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.CLOSED.value]
                )
            )
        )
        total_debt = total_debt_result.scalar() or Decimal("0.00")

        # Pending GRN count (draft status)
        pending_grn_result = await self.db.execute(
            select(func.count(GoodsReceivedNote.id)).where(
                GoodsReceivedNote.status == GoodsReceivedStatus.DRAFT.value
            )
        )
        pending_grn_count = pending_grn_result.scalar() or 0

        return {
            "total_supplier_debt": total_debt,
            "pending_grn_count": pending_grn_count,
        }


class PaymentPurposeService:
    """Service for payment purpose catalog."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_purpose(self, data: PaymentPurposeCreate) -> PaymentPurpose:
        existing = await self.db.execute(
            select(PaymentPurpose).where(
                PaymentPurpose.name.ilike(data.name.strip())
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Payment purpose already exists")
        purpose = PaymentPurpose(name=data.name.strip())
        self.db.add(purpose)
        await self.db.commit()
        await self.db.refresh(purpose)
        return purpose

    async def update_purpose(
        self, purpose_id: int, data: PaymentPurposeUpdate
    ) -> PaymentPurpose:
        purpose = await self.get_purpose_by_id(purpose_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(purpose, field, value)
        await self.db.commit()
        return await self.get_purpose_by_id(purpose_id)

    async def list_purposes(
        self, include_inactive: bool = False
    ) -> list[PaymentPurpose]:
        query = select(PaymentPurpose)
        if not include_inactive:
            query = query.where(PaymentPurpose.is_active.is_(True))
        query = query.order_by(PaymentPurpose.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_purpose_by_id(self, purpose_id: int) -> PaymentPurpose:
        result = await self.db.execute(
            select(PaymentPurpose).where(PaymentPurpose.id == purpose_id)
        )
        purpose = result.scalar_one_or_none()
        if not purpose:
            raise NotFoundError(f"Payment purpose {purpose_id} not found")
        return purpose

    async def get_purpose_by_name(self, name: str) -> PaymentPurpose:
        """Get payment purpose by name (case-insensitive). Only active purposes."""
        if not (name and name.strip()):
            raise ValidationError("Payment purpose name is required")
        result = await self.db.execute(
            select(PaymentPurpose)
            .where(PaymentPurpose.name.ilike(name.strip()))
            .where(PaymentPurpose.is_active.is_(True))
        )
        purpose = result.scalar_one_or_none()
        if not purpose:
            raise NotFoundError(f"Payment purpose '{name.strip()}' not found")
        return purpose


class ProcurementPaymentService:
    """Service for procurement payments."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.po_service = PurchaseOrderService(db)

    async def create_payment(
        self, data: ProcurementPaymentCreate, created_by_id: int
    ) -> ProcurementPayment:
        payment_number = await get_document_number(self.db, "PPAY")

        if data.po_id:
            po = await self.po_service.get_purchase_order_by_id(data.po_id)
            purpose_id = po.purpose_id
            if data.purpose_id is not None and data.purpose_id != purpose_id:
                raise ValidationError("Payment purpose must match PO purpose")
        else:
            po = None
            if data.purpose_id is None:
                raise ValidationError("purpose_id is required for payments without PO")
            purpose_id = data.purpose_id

        await PaymentPurposeService(self.db).get_purpose_by_id(purpose_id)

        payment = ProcurementPayment(
            payment_number=payment_number,
            po_id=data.po_id,
            purpose_id=purpose_id,
            payee_name=data.payee_name,
            payment_date=data.payment_date,
            amount=data.amount,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            proof_text=data.proof_text,
            proof_attachment_id=data.proof_attachment_id,
            company_paid=data.company_paid,
            employee_paid_id=data.employee_paid_id,
            status=ProcurementPaymentStatus.POSTED.value,
            created_by_id=created_by_id,
        )
        self.db.add(payment)

        if po:
            po.paid_total += data.amount
            await self.po_service._recalculate_totals(po.id)

        if payment.employee_paid_id:
            await ExpenseClaimService(self.db).create_from_payment(payment)

        await self.db.commit()
        return await self.get_payment_by_id(payment.id)

    async def cancel_payment(
        self, payment_id: int, reason: str, cancelled_by_id: int
    ) -> ProcurementPayment:
        payment = await self.get_payment_by_id(payment_id)
        if payment.status == ProcurementPaymentStatus.CANCELLED.value:
            raise ValidationError("Payment already cancelled")

        payment.status = ProcurementPaymentStatus.CANCELLED.value
        payment.cancelled_reason = reason
        payment.cancelled_by_id = cancelled_by_id
        payment.cancelled_at = datetime.utcnow()

        if payment.po_id:
            po = await self.po_service.get_purchase_order_by_id(payment.po_id)
            po.paid_total -= payment.amount
            await self.po_service._recalculate_totals(po.id)

        await self.db.commit()
        return await self.get_payment_by_id(payment.id)

    async def get_payment_by_id(self, payment_id: int) -> ProcurementPayment:
        result = await self.db.execute(
            select(ProcurementPayment).where(ProcurementPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise NotFoundError(f"Procurement payment {payment_id} not found")
        return payment

    async def list_payments(
        self, filters: ProcurementPaymentFilters
    ) -> tuple[list[ProcurementPayment], int]:
        query = select(ProcurementPayment)
        if filters.po_id:
            query = query.where(ProcurementPayment.po_id == filters.po_id)
        if filters.purpose_id:
            query = query.where(ProcurementPayment.purpose_id == filters.purpose_id)
        if filters.status:
            query = query.where(ProcurementPayment.status == filters.status)
        if filters.date_from:
            query = query.where(ProcurementPayment.payment_date >= filters.date_from)
        if filters.date_to:
            query = query.where(ProcurementPayment.payment_date <= filters.date_to)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(ProcurementPayment.payment_date.desc())
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total or 0
