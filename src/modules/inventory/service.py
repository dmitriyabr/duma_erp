"""Service for Inventory module."""

import csv
import io
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit.service import AuditService
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.exceptions import NotFoundError, ValidationError
from src.modules.inventory.models import (
    Issuance,
    IssuanceItem,
    IssuanceStatus,
    IssuanceType,
    MovementType,
    RecipientType,
    Stock,
    StockMovement,
)
from src.modules.inventory.schemas import (
    AdjustStockRequest,
    InternalIssuanceCreate,
    IssueStockRequest,
    ReceiveStockRequest,
    WriteOffItem,
    InventoryCountItem,
)
from src.core.auth.models import User
from src.modules.items.models import Category, Item, ItemType, ItemVariantMembership, Kit, KitItem
from src.modules.procurement.models import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus
from src.modules.reservations.models import Reservation, ReservationItem, ReservationStatus
from src.modules.students.models import Student
from src.shared.utils.money import round_money


class InventoryService:
    """Service for managing inventory stock and movements."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def _get_item(self, item_id: int) -> Item:
        """Get item by ID and verify it's a product."""
        result = await self.db.execute(select(Item).where(Item.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(f"Item with id {item_id} not found")
        if item.item_type != ItemType.PRODUCT.value:
            raise ValidationError(f"Item '{item.name}' is not a product and cannot have stock")
        return item

    async def _get_or_create_stock(self, item_id: int) -> Stock:
        """Get existing stock record or create new one."""
        result = await self.db.execute(
            select(Stock).where(Stock.item_id == item_id)
        )
        stock = result.scalar_one_or_none()

        if not stock:
            # Verify item exists and is a product
            await self._get_item(item_id)

            stock = Stock(
                item_id=item_id,
                quantity_on_hand=0,
                average_cost=Decimal("0.00"),
            )
            self.db.add(stock)
            await self.db.flush()

        return stock

    async def get_stock_by_item_id(self, item_id: int) -> Stock | None:
        """Get stock record for an item."""
        result = await self.db.execute(
            select(Stock)
            .options(selectinload(Stock.item))
            .where(Stock.item_id == item_id)
        )
        return result.scalar_one_or_none()

    async def list_stock(
        self,
        include_zero: bool = False,
        category_id: int | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Stock], int]:
        """List all stock records with optional filters."""
        query = (
            select(Stock)
            .options(selectinload(Stock.item))
            .join(Item)
            .order_by(Item.name)
        )

        if not include_zero:
            query = query.where(Stock.quantity_on_hand > 0)

        if category_id is not None:
            query = query.where(Item.category_id == category_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        stocks = list(result.scalars().all())

        return stocks, total

    async def get_owed_quantities_by_item_id(self, item_ids: list[int]) -> dict[int, int]:
        """Return outstanding owed quantities for active reservations per item_id.

        Owed = sum(quantity_required - quantity_issued) for reservations in pending/partial status.
        This represents demand, not physical stock allocation.
        """
        if not item_ids:
            return {}

        result = await self.db.execute(
            select(
                ReservationItem.item_id,
                func.coalesce(
                    func.sum(ReservationItem.quantity_required - ReservationItem.quantity_issued),
                    0,
                ).label("owed"),
            )
            .join(Reservation, Reservation.id == ReservationItem.reservation_id)
            .where(
                Reservation.status.in_(
                    [ReservationStatus.PENDING.value, ReservationStatus.PARTIAL.value]
                )
            )
            .where(ReservationItem.item_id.in_(item_ids))
            .group_by(ReservationItem.item_id)
        )
        return {int(row[0]): int(row[1] or 0) for row in result.all()}

    async def _get_sellable_item_ids_from_active_product_kits(self) -> set[int]:
        """Return item IDs that are sellable/issuable based on active product kits.

        Definition:
        - Includes KitItem.source_type == 'item' → KitItem.item_id
        - Includes KitItem.source_type == 'variant' → ALL items from the variant group
          (ItemVariantMembership.variant_id == KitItem.variant_id)
        - Only kits with Kit.is_active == True and Kit.item_type == product are considered.
        """
        fixed_ids_result = await self.db.execute(
            select(func.distinct(KitItem.item_id))
            .join(Kit, Kit.id == KitItem.kit_id)
            .where(Kit.is_active.is_(True))
            .where(Kit.item_type == ItemType.PRODUCT.value)
            .where(KitItem.source_type == "item")
            .where(KitItem.item_id.is_not(None))
        )
        fixed_ids = {int(r[0]) for r in fixed_ids_result.all() if r[0] is not None}

        variant_ids_result = await self.db.execute(
            select(func.distinct(ItemVariantMembership.item_id))
            .select_from(KitItem)
            .join(Kit, Kit.id == KitItem.kit_id)
            .join(
                ItemVariantMembership,
                ItemVariantMembership.variant_id == KitItem.variant_id,
            )
            .where(Kit.is_active.is_(True))
            .where(Kit.item_type == ItemType.PRODUCT.value)
            .where(KitItem.source_type == "variant")
            .where(KitItem.variant_id.is_not(None))
        )
        variant_item_ids = {
            int(r[0]) for r in variant_ids_result.all() if r[0] is not None
        }

        return fixed_ids | variant_item_ids

    async def get_inbound_quantities_by_item_id(self, item_ids: list[int]) -> dict[int, int]:
        """Return inbound quantities (ordered but not yet received) per item_id.

        Inbound is computed from Purchase Orders:
        inbound = sum(max(0, quantity_expected - quantity_cancelled - quantity_received))

        Only includes:
        - PurchaseOrder.track_to_warehouse == True
        - PurchaseOrder.status not in (cancelled, closed)
        - PurchaseOrderLine.item_id is not null
        """
        if not item_ids:
            return {}

        remaining_raw = (
            PurchaseOrderLine.quantity_expected
            - PurchaseOrderLine.quantity_cancelled
            - PurchaseOrderLine.quantity_received
        )
        remaining_expr = case((remaining_raw > 0, remaining_raw), else_=0)
        result = await self.db.execute(
            select(
                PurchaseOrderLine.item_id,
                func.coalesce(func.sum(remaining_expr), 0).label("inbound"),
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
            .where(PurchaseOrder.track_to_warehouse.is_(True))
            .where(
                PurchaseOrder.status.notin_(
                    [
                        PurchaseOrderStatus.CANCELLED.value,
                        PurchaseOrderStatus.CLOSED.value,
                    ]
                )
            )
            .where(PurchaseOrderLine.item_id.in_(item_ids))
            .group_by(PurchaseOrderLine.item_id)
        )
        return {int(r[0]): int(r[1] or 0) for r in result.all() if r[0] is not None}

    async def list_restock_rows(
        self,
        *,
        search: str | None = None,
        category_id: int | None = None,
        only_demand: bool = True,
    ) -> list[dict]:
        """Return restock-planning rows for sellable items only."""
        sellable_ids = await self._get_sellable_item_ids_from_active_product_kits()
        if not sellable_ids:
            return []

        q = (
            select(
                Item.id,
                Item.sku_code,
                Item.name,
                Item.category_id,
                Category.name.label("category_name"),
            )
            .join(Category, Category.id == Item.category_id)
            .where(Item.id.in_(sorted(sellable_ids)))
            .where(Item.item_type == ItemType.PRODUCT.value)
            .where(Item.is_active.is_(True))
        )
        if category_id is not None:
            q = q.where(Item.category_id == category_id)
        if search and search.strip():
            s = f"%{search.strip()}%"
            q = q.where(Item.name.ilike(s) | Item.sku_code.ilike(s))

        q = q.order_by(Item.name)
        items = list((await self.db.execute(q)).all())
        item_ids = [int(r.id) for r in items]
        if not item_ids:
            return []

        stock_rows = await self.db.execute(
            select(Stock.item_id, Stock.quantity_on_hand)
            .where(Stock.item_id.in_(item_ids))
        )
        on_hand_by_item_id = {
            int(r[0]): int(r[1] or 0) for r in stock_rows.all() if r[0] is not None
        }
        owed_by_item_id = await self.get_owed_quantities_by_item_id(item_ids)
        inbound_by_item_id = await self.get_inbound_quantities_by_item_id(item_ids)

        rows: list[dict] = []
        for r in items:
            item_id = int(r.id)
            on_hand = int(on_hand_by_item_id.get(item_id, 0))
            owed = int(owed_by_item_id.get(item_id, 0))
            inbound = int(inbound_by_item_id.get(item_id, 0))
            net = on_hand + inbound - owed
            to_order = max(0, owed - (on_hand + inbound))

            if only_demand and not (owed > 0 or to_order > 0):
                continue

            rows.append(
                {
                    "item_id": item_id,
                    "item_sku": r.sku_code,
                    "item_name": r.name,
                    "category_id": int(r.category_id) if r.category_id is not None else None,
                    "category_name": r.category_name,
                    "quantity_on_hand": on_hand,
                    "quantity_owed": owed,
                    "quantity_inbound": inbound,
                    "quantity_net": net,
                    "quantity_to_order": to_order,
                }
            )

        rows.sort(
            key=lambda x: (
                -int(x["quantity_to_order"]),
                -int(x["quantity_owed"]),
                str(x["item_name"] or ""),
            )
        )
        return rows

    async def list_reorder_rows(
        self,
        *,
        search: str | None = None,
        category_id: int | None = None,
        only_demand: bool = True,
    ) -> list[dict]:
        """Backward-compatible alias for list_restock_rows."""
        return await self.list_restock_rows(
            search=search,
            category_id=category_id,
            only_demand=only_demand,
        )

    async def receive_stock(
        self,
        data: ReceiveStockRequest,
        received_by_id: int,
        commit: bool = True,
    ) -> StockMovement:
        """Receive stock (incoming goods).

        Updates quantity_on_hand and recalculates average_cost using weighted average.
        """
        stock = await self._get_or_create_stock(data.item_id)

        # Store before values
        quantity_before = stock.quantity_on_hand
        average_cost_before = stock.average_cost

        # Calculate new weighted average cost
        # new_avg = (old_qty * old_avg + new_qty * new_cost) / (old_qty + new_qty)
        total_value_before = Decimal(quantity_before) * average_cost_before
        total_value_new = Decimal(data.quantity) * data.unit_cost
        new_total_quantity = quantity_before + data.quantity

        if new_total_quantity > 0:
            new_average_cost = round_money(
                (total_value_before + total_value_new) / Decimal(new_total_quantity)
            )
        else:
            new_average_cost = data.unit_cost

        # Update stock
        stock.quantity_on_hand = new_total_quantity
        stock.average_cost = new_average_cost

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=data.item_id,
            movement_type=MovementType.RECEIPT.value,
            quantity=data.quantity,
            unit_cost=data.unit_cost,
            quantity_before=quantity_before,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=average_cost_before,
            average_cost_after=new_average_cost,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            created_by_id=received_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action="inventory.receive",
            entity_type="Stock",
            entity_id=stock.id,
            user_id=received_by_id,
            old_values={
                "quantity_on_hand": quantity_before,
                "average_cost": str(average_cost_before),
            },
            new_values={
                "quantity_on_hand": stock.quantity_on_hand,
                "average_cost": str(new_average_cost),
                "received_quantity": data.quantity,
                "unit_cost": str(data.unit_cost),
            },
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
        return movement

    async def apply_receipt_signed(
        self,
        *,
        item_id: int,
        quantity_delta: int,
        unit_cost: Decimal,
        reference_type: str | None,
        reference_id: int | None,
        notes: str | None,
        created_by_id: int,
        audit_action: str = "inventory.receive",
        commit: bool = True,
    ) -> StockMovement:
        """
        Apply a receipt movement with a signed quantity delta.

        This is intended for internal workflows (e.g. rollback of a GRN receipt).
        Public API uses `receive_stock()` which enforces positive quantities.
        """
        if quantity_delta == 0:
            raise ValidationError("Receipt quantity must be non-zero")
        if unit_cost < 0:
            raise ValidationError("Unit cost must be >= 0")

        stock = await self._get_or_create_stock(item_id)

        quantity_before = stock.quantity_on_hand
        average_cost_before = stock.average_cost

        new_total_quantity = quantity_before + quantity_delta
        if new_total_quantity < 0:
            raise ValidationError(
                f"Receipt would result in negative stock ({new_total_quantity}). "
                f"Current quantity: {quantity_before}, change: {quantity_delta}"
            )
        total_value_before = Decimal(quantity_before) * average_cost_before
        total_value_new = Decimal(quantity_delta) * unit_cost

        if new_total_quantity > 0:
            new_average_cost = round_money(
                (total_value_before + total_value_new) / Decimal(new_total_quantity)
            )
        else:
            # No stock left: keep previous average cost to avoid surprising jumps.
            new_average_cost = average_cost_before

        stock.quantity_on_hand = new_total_quantity
        stock.average_cost = new_average_cost

        movement = StockMovement(
            stock_id=stock.id,
            item_id=item_id,
            movement_type=MovementType.RECEIPT.value,
            quantity=quantity_delta,
            unit_cost=unit_cost,
            quantity_before=quantity_before,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=average_cost_before,
            average_cost_after=new_average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by_id=created_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action=audit_action,
            entity_type="Stock",
            entity_id=stock.id,
            user_id=created_by_id,
            old_values={
                "quantity_on_hand": quantity_before,
                "average_cost": str(average_cost_before),
            },
            new_values={
                "quantity_on_hand": stock.quantity_on_hand,
                "average_cost": str(new_average_cost),
                "quantity_delta": quantity_delta,
                "unit_cost": str(unit_cost),
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
        return movement

    async def adjust_stock(
        self,
        data: AdjustStockRequest,
        adjusted_by_id: int,
        commit: bool = True,
    ) -> StockMovement:
        """Adjust stock (correction, write-off).

        Can increase or decrease quantity. Does not change average_cost.
        """
        movement = await self._apply_adjustment(
            item_id=data.item_id,
            quantity_delta=data.quantity,
            reason=data.reason,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            adjusted_by_id=adjusted_by_id,
            audit_action="inventory.adjust",
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
        return movement

    async def write_off_items(
        self, items: list[WriteOffItem], written_off_by_id: int
    ) -> list[StockMovement]:
        """Write off items with reasons (damage/expired/lost/other)."""
        movements: list[StockMovement] = []
        for item in items:
            reason_detail = f"{item.reason_category.value}"
            if item.reason_detail:
                reason_detail = f"{reason_detail}: {item.reason_detail}"
            movement = await self._apply_adjustment(
                item_id=item.item_id,
                quantity_delta=-item.quantity,
                reason=reason_detail,
                reference_type="writeoff",
                reference_id=None,
                adjusted_by_id=written_off_by_id,
                audit_action="inventory.writeoff",
            )
            movements.append(movement)

        await self.db.commit()
        return movements

    async def bulk_inventory_adjustment(
        self, items: list[InventoryCountItem], adjusted_by_id: int
    ) -> list[StockMovement]:
        """Adjust stock based on actual counted quantities."""
        movements: list[StockMovement] = []
        for item in items:
            stock = await self._get_or_create_stock(item.item_id)
            delta = item.actual_quantity - stock.quantity_on_hand
            if delta == 0:
                continue
            movement = await self._apply_adjustment(
                item_id=item.item_id,
                quantity_delta=delta,
                reason=f"Inventory count: actual {item.actual_quantity}",
                reference_type="inventory_count",
                reference_id=None,
                adjusted_by_id=adjusted_by_id,
                audit_action="inventory.adjust",
            )
            movements.append(movement)

        await self.db.commit()
        return movements

    async def _apply_adjustment(
        self,
        item_id: int,
        quantity_delta: int,
        reason: str,
        reference_type: str | None,
        reference_id: int | None,
        adjusted_by_id: int,
        audit_action: str,
    ) -> StockMovement:
        stock = await self._get_or_create_stock(item_id)

        quantity_before = stock.quantity_on_hand
        new_quantity = quantity_before + quantity_delta

        if new_quantity < 0:
            raise ValidationError(
                f"Adjustment would result in negative stock ({new_quantity}). "
                f"Current quantity: {quantity_before}, adjustment: {quantity_delta}"
            )

        stock.quantity_on_hand = new_quantity

        movement = StockMovement(
            stock_id=stock.id,
            item_id=item_id,
            movement_type=MovementType.ADJUSTMENT.value,
            quantity=quantity_delta,
            unit_cost=None,
            quantity_before=quantity_before,
            quantity_after=new_quantity,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=reason,
            created_by_id=adjusted_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action=audit_action,
            entity_type="Stock",
            entity_id=stock.id,
            user_id=adjusted_by_id,
            old_values={"quantity_on_hand": quantity_before},
            new_values={
                "quantity_on_hand": new_quantity,
                "adjustment": quantity_delta,
                "reason": reason,
            },
        )

        return movement

    async def issue_stock(
        self, data: IssueStockRequest, issued_by_id: int
    ) -> StockMovement:
        """Issue stock (manual issue without reservation).

        Decreases quantity_on_hand. For reserved stock, use reserve/unreserve methods.
        """
        stock = await self._get_or_create_stock(data.item_id)

        # Store before values
        quantity_before = stock.quantity_on_hand

        if data.quantity > stock.quantity_on_hand:
            raise ValidationError(
                f"Insufficient stock. On hand: {stock.quantity_on_hand}, requested: {data.quantity}."
            )

        # Update stock
        stock.quantity_on_hand -= data.quantity

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=data.item_id,
            movement_type=MovementType.ISSUE.value,
            quantity=-data.quantity,  # Negative for outgoing
            unit_cost=stock.average_cost,  # Use current average cost
            quantity_before=quantity_before,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,  # No change
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            created_by_id=issued_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action="inventory.issue",
            entity_type="Stock",
            entity_id=stock.id,
            user_id=issued_by_id,
            old_values={"quantity_on_hand": quantity_before},
            new_values={
                "quantity_on_hand": stock.quantity_on_hand,
                "issued_quantity": data.quantity,
            },
        )

        await self.db.commit()
        await self.db.refresh(movement)
        return movement

    async def get_movements(
        self,
        item_id: int | None = None,
        movement_type: MovementType | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[StockMovement], int]:
        """Get stock movements with optional filters."""
        query = (
            select(StockMovement)
            .options(
                selectinload(StockMovement.item),
                selectinload(StockMovement.created_by),
            )
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        )

        if item_id is not None:
            query = query.where(StockMovement.item_id == item_id)
        if movement_type is not None:
            query = query.where(StockMovement.movement_type == movement_type.value)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        movements = list(result.scalars().all())

        return movements, total

    async def get_movements_by_ids(
        self, movement_ids: list[int]
    ) -> list[StockMovement]:
        """Get stock movements by IDs with relationships loaded."""
        if not movement_ids:
            return []
        result = await self.db.execute(
            select(StockMovement)
            .where(StockMovement.id.in_(movement_ids))
            .options(
                selectinload(StockMovement.item),
                selectinload(StockMovement.created_by),
            )
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        )
        return list(result.scalars().all())

    # --- Issuance Methods ---

    async def create_internal_issuance(
        self, data: InternalIssuanceCreate, issued_by_id: int
    ) -> Issuance:
        """Create an internal issuance (to employee, student, or other).

        This creates an issuance record and issues stock for each item.
        """
        # Validate recipient and resolve recipient_name for employee/student
        recipient_id: int | None = data.recipient_id
        recipient_name = data.recipient_name

        if data.recipient_type == RecipientType.EMPLOYEE:
            if recipient_id is None:
                raise ValidationError("recipient_id is required for employee")
            result = await self.db.execute(select(User).where(User.id == recipient_id))
            user = result.scalar_one_or_none()
            if not user:
                raise NotFoundError(f"User with id {recipient_id} not found")
            recipient_name = user.full_name or data.recipient_name
        elif data.recipient_type == RecipientType.STUDENT:
            if recipient_id is None:
                raise ValidationError("recipient_id is required for student")
            result = await self.db.execute(
                select(Student).where(Student.id == recipient_id)
            )
            student = result.scalar_one_or_none()
            if not student:
                raise NotFoundError(f"Student with id {recipient_id} not found")
            recipient_name = (
                f"{student.first_name} {student.last_name}".strip()
                or data.recipient_name
            )
        elif data.recipient_type == RecipientType.OTHER:
            recipient_id = None  # Ensure null for other

        # Validate all items have sufficient stock
        for item_data in data.items:
            stock = await self.get_stock_by_item_id(item_data.item_id)
            if not stock:
                item = await self._get_item(item_data.item_id)
                raise ValidationError(
                    f"No stock for item '{item.name}'. Receive stock first."
                )
            if item_data.quantity > stock.quantity_on_hand:
                raise ValidationError(
                    f"Insufficient stock for item {item_data.item_id}. "
                    f"On hand: {stock.quantity_on_hand}, requested: {item_data.quantity}"
                )

        # Generate issuance number
        number_gen = DocumentNumberGenerator(self.db)
        issuance_number = await number_gen.generate("ISS")

        # Create issuance
        issuance = Issuance(
            issuance_number=issuance_number,
            issuance_type=IssuanceType.INTERNAL.value,
            recipient_type=data.recipient_type.value,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            reservation_id=None,
            issued_by_id=issued_by_id,
            notes=data.notes,
            status=IssuanceStatus.COMPLETED.value,
        )
        self.db.add(issuance)
        await self.db.flush()

        # Create issuance items and issue stock
        for item_data in data.items:
            stock = await self.get_stock_by_item_id(item_data.item_id)

            # Create issuance item
            issuance_item = IssuanceItem(
                issuance_id=issuance.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                unit_cost=stock.average_cost,
                reservation_item_id=None,
            )
            self.db.add(issuance_item)

            # Issue stock (without commit, we'll commit at the end)
            await self._issue_stock_internal(
                stock=stock,
                quantity=item_data.quantity,
                reference_type="issuance",
                reference_id=issuance.id,
                issued_by_id=issued_by_id,
            )

        await self.audit.log(
            action="inventory.issuance.create",
            entity_type="Issuance",
            entity_id=issuance.id,
            user_id=issued_by_id,
            new_values={
                "issuance_number": issuance_number,
                "recipient_type": data.recipient_type.value,
                "recipient_name": data.recipient_name,
                "items": [
                    {"item_id": i.item_id, "quantity": i.quantity}
                    for i in data.items
                ],
            },
        )

        await self.db.commit()
        await self.db.refresh(issuance)
        return issuance

    async def _issue_stock_internal(
        self,
        stock: Stock,
        quantity: int,
        reference_type: str,
        reference_id: int,
        issued_by_id: int,
    ) -> StockMovement:
        """Internal method to issue stock without commit.

        Used by issuance methods to batch multiple stock operations.
        """
        quantity_before = stock.quantity_on_hand

        # Update stock
        stock.quantity_on_hand -= quantity

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=stock.item_id,
            movement_type=MovementType.ISSUE.value,
            quantity=-quantity,
            unit_cost=stock.average_cost,
            quantity_before=quantity_before,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=None,
            created_by_id=issued_by_id,
        )
        self.db.add(movement)

        return movement

    async def get_issuance_by_id(self, issuance_id: int) -> Issuance:
        """Get issuance by ID with items loaded."""
        result = await self.db.execute(
            select(Issuance)
            .options(
                selectinload(Issuance.items).selectinload(IssuanceItem.item),
                selectinload(Issuance.issued_by),
            )
            .where(Issuance.id == issuance_id)
        )
        issuance = result.scalar_one_or_none()
        if not issuance:
            raise NotFoundError(f"Issuance with id {issuance_id} not found")
        return issuance

    async def get_issuance_by_number(self, issuance_number: str) -> Issuance:
        """Get issuance by number with items loaded."""
        result = await self.db.execute(
            select(Issuance)
            .options(
                selectinload(Issuance.items).selectinload(IssuanceItem.item),
                selectinload(Issuance.issued_by),
            )
            .where(Issuance.issuance_number == issuance_number)
        )
        issuance = result.scalar_one_or_none()
        if not issuance:
            raise NotFoundError(f"Issuance with number '{issuance_number}' not found")
        return issuance

    async def list_issuances(
        self,
        issuance_type: IssuanceType | None = None,
        recipient_type: RecipientType | None = None,
        recipient_id: int | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Issuance], int]:
        """List issuances with optional filters."""
        query = (
            select(Issuance)
            .options(
                selectinload(Issuance.items).selectinload(IssuanceItem.item),
                selectinload(Issuance.issued_by),
            )
            .order_by(Issuance.issued_at.desc())
        )

        if issuance_type is not None:
            query = query.where(Issuance.issuance_type == issuance_type.value)
        if recipient_type is not None:
            query = query.where(Issuance.recipient_type == recipient_type.value)
        if recipient_id is not None:
            query = query.where(Issuance.recipient_id == recipient_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        issuances = list(result.scalars().all())

        return issuances, total

    async def cancel_issuance(
        self, issuance_id: int, cancelled_by_id: int, commit: bool = True
    ) -> Issuance:
        """Cancel an issuance and return stock.

        This reverses all stock movements from the issuance.
        """
        issuance = await self.get_issuance_by_id(issuance_id)

        if issuance.status == IssuanceStatus.CANCELLED.value:
            raise ValidationError("Issuance is already cancelled")

        # If this issuance came from a reservation, we should also roll back the
        # reservation's issued quantities. Stock and reservations are tracked
        # separately:
        # - stock.quantity_on_hand tracks physical stock
        # - reservation_items.quantity_issued tracks progress of fulfilling demand
        rollback_by_reservation_item_id: dict[int, int] = {}
        for issuance_item in issuance.items:
            if issuance_item.reservation_item_id:
                rid = int(issuance_item.reservation_item_id)
                rollback_by_reservation_item_id[rid] = int(
                    rollback_by_reservation_item_id.get(rid, 0)
                ) + int(issuance_item.quantity)

        # Return stock for each item
        for issuance_item in issuance.items:
            stock = await self._get_or_create_stock(issuance_item.item_id)

            # Increase stock (return)
            quantity_before = stock.quantity_on_hand
            stock.quantity_on_hand += issuance_item.quantity

            # Create movement record for return
            movement = StockMovement(
                stock_id=stock.id,
                item_id=issuance_item.item_id,
                movement_type=MovementType.ADJUSTMENT.value,
                quantity=issuance_item.quantity,
                unit_cost=None,
                quantity_before=quantity_before,
                quantity_after=stock.quantity_on_hand,
                average_cost_before=stock.average_cost,
                average_cost_after=stock.average_cost,
                reference_type="issuance_cancellation",
                reference_id=issuance.id,
                notes=f"Return from cancelled issuance {issuance.issuance_number}",
                created_by_id=cancelled_by_id,
            )
            self.db.add(movement)

        reservation_status_before: str | None = None
        reservation_status_after: str | None = None
        if issuance.reservation_id and rollback_by_reservation_item_id:
            # Lock and update reservation items
            for reservation_item_id, qty in rollback_by_reservation_item_id.items():
                res_item_result = await self.db.execute(
                    select(ReservationItem)
                    .where(ReservationItem.id == reservation_item_id)
                    .with_for_update()
                )
                res_item = res_item_result.scalar_one_or_none()
                if not res_item:
                    raise NotFoundError(
                        f"ReservationItem with id {reservation_item_id} not found"
                    )
                if int(res_item.reservation_id) != int(issuance.reservation_id):
                    raise ValidationError(
                        f"ReservationItem {reservation_item_id} does not belong to "
                        f"Reservation {issuance.reservation_id}"
                    )
                if qty <= 0:
                    continue
                if res_item.quantity_issued < qty:
                    raise ValidationError(
                        f"Cannot rollback reservation_item {reservation_item_id}: "
                        f"issued={res_item.quantity_issued}, rollback={qty}"
                    )
                res_item.quantity_issued -= qty

            # Recalculate reservation status (unless it's already cancelled)
            reservation_result = await self.db.execute(
                select(Reservation)
                .where(Reservation.id == issuance.reservation_id)
                .options(selectinload(Reservation.items))
            )
            reservation = reservation_result.scalar_one_or_none()
            if not reservation:
                raise NotFoundError(
                    f"Reservation with id {issuance.reservation_id} not found"
                )
            reservation_status_before = reservation.status
            if reservation.status != ReservationStatus.CANCELLED.value:
                total_required = sum(
                    int(i.quantity_required) for i in reservation.items
                )
                total_issued = sum(int(i.quantity_issued) for i in reservation.items)
                if total_required > 0 and total_issued >= total_required:
                    reservation.status = ReservationStatus.FULFILLED.value
                elif total_issued > 0:
                    reservation.status = ReservationStatus.PARTIAL.value
                else:
                    reservation.status = ReservationStatus.PENDING.value
            reservation_status_after = reservation.status

        # Update issuance status
        issuance.status = IssuanceStatus.CANCELLED.value

        await self.audit.log(
            action="inventory.issuance.cancel",
            entity_type="Issuance",
            entity_id=issuance.id,
            user_id=cancelled_by_id,
            old_values={"status": IssuanceStatus.COMPLETED.value},
            new_values={
                "status": IssuanceStatus.CANCELLED.value,
                "reservation_id": issuance.reservation_id,
                "reservation_items_rollback": rollback_by_reservation_item_id or None,
                "reservation_status_before": reservation_status_before,
                "reservation_status_after": reservation_status_after,
            },
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(issuance)
        return issuance

    # --- Bulk CSV ---

    async def export_stock_to_csv(self) -> bytes:
        """Export current stock (quantity_on_hand only, no reserved) to CSV.

        Columns: category, item_name, sku, quantity, unit_cost.
        """
        query = (
            select(Stock)
            .options(
                selectinload(Stock.item).selectinload(Item.category),
            )
            .join(Item)
            .where(Item.item_type == ItemType.PRODUCT.value)
            .order_by(Item.name)
        )
        result = await self.db.execute(query)
        stocks = list(result.scalars().unique().all())

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["category", "item_name", "sku", "quantity", "unit_cost"])
        for stock in stocks:
            cat_name = stock.item.category.name if stock.item and stock.item.category else ""
            name = stock.item.name if stock.item else ""
            sku = stock.item.sku_code if stock.item else ""
            qty = stock.quantity_on_hand
            cost = str(stock.average_cost) if stock.average_cost is not None else ""
            writer.writerow([cat_name, name, sku, qty, cost])

        return ("\ufeff" + buf.getvalue()).encode("utf-8")

    async def bulk_upload_from_csv(
        self,
        content: bytes | str,
        mode: str,
        user_id: int,
    ) -> dict:
        """Parse CSV and apply stock updates. mode: 'overwrite' | 'update'.

        Overwrite: zero quantity_on_hand for all product stocks (only where reserved=0), then set from CSV.
        Update: only set quantity for rows in CSV.
        Returns dict with rows_processed, items_created, errors (list of {row, message}).
        """
        from src.modules.items.service import ItemService

        if isinstance(content, bytes):
            text = content.decode("utf-8-sig")
        else:
            text = content
        reader = csv.DictReader(io.StringIO(text))
        required = {"category", "item_name", "quantity"}
        if not reader.fieldnames:
            raise ValidationError("CSV has no headers")
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"CSV missing columns: {sorted(missing)}")

        item_service = ItemService(self.db)
        rows_processed = 0
        items_created = 0
        errors: list[dict] = []

        if mode == "overwrite":
            # Under demand-based reservations, we do not physically allocate stock.
            # Still, overwriting warehouse counts while there are outstanding reservations is unsafe.
            outstanding_result = await self.db.execute(
                select(func.count())
                .select_from(ReservationItem)
                .join(Reservation, Reservation.id == ReservationItem.reservation_id)
                .where(
                    Reservation.status.in_(
                        [ReservationStatus.PENDING.value, ReservationStatus.PARTIAL.value]
                    )
                )
                .where(ReservationItem.quantity_required > ReservationItem.quantity_issued)
            )
            outstanding = int(outstanding_result.scalar() or 0)
            if outstanding > 0:
                raise ValidationError(
                    "Cannot overwrite warehouse while there are outstanding reservations. "
                    "Cancel or fulfill reservations first."
                )

            # Zero quantity_on_hand only.
            result = await self.db.execute(
                select(Stock)
                .options(selectinload(Stock.item))
                .join(Item)
                .where(Item.item_type == ItemType.PRODUCT.value)
                .where(Stock.quantity_on_hand > 0)
            )
            stocks_to_zero = list(result.scalars().unique().all())
            for stock in stocks_to_zero:
                await self._apply_adjustment(
                    item_id=stock.item_id,
                    quantity_delta=-stock.quantity_on_hand,
                    reason="Bulk overwrite: zero stock",
                    reference_type="bulk_upload",
                    reference_id=None,
                    adjusted_by_id=user_id,
                    audit_action="inventory.bulk_overwrite",
                )

        for row_num, row in enumerate(reader, start=2):
            cat = (row.get("category") or "").strip()
            name = (row.get("item_name") or "").strip()
            qty_str = (row.get("quantity") or "").strip()
            sku = (row.get("sku") or "").strip() or None
            unit_cost_str = (row.get("unit_cost") or "").strip()
            if not cat or not name:
                errors.append({"row": row_num, "message": "category and item_name required"})
                continue
            try:
                qty = int(qty_str)
            except ValueError:
                errors.append({"row": row_num, "message": f"invalid quantity: {qty_str!r}"})
                continue
            if qty < 0:
                errors.append({"row": row_num, "message": "quantity must be >= 0"})
                continue

            unit_cost_csv = None
            if unit_cost_str:
                try:
                    unit_cost_csv = round_money(Decimal(unit_cost_str))
                    if unit_cost_csv < 0:
                        errors.append({"row": row_num, "message": "unit_cost must be >= 0"})
                        continue
                except Exception:
                    errors.append({"row": row_num, "message": f"invalid unit_cost: {unit_cost_str!r}"})
                    continue

            try:
                item, created = await item_service.get_or_create_product_item(
                    category_name=cat,
                    item_name=name,
                    sku=sku,
                    created_by_id=user_id,
                )
            except Exception as e:
                errors.append({"row": row_num, "message": str(e)})
                continue

            if created:
                items_created += 1

            stock = await self._get_or_create_stock(item.id)
            target = qty
            delta = target - stock.quantity_on_hand
            if delta == 0:
                rows_processed += 1
                continue
            # When adding stock (delta > 0) and unit_cost in CSV: use receive so average_cost is set/updated
            if delta > 0 and unit_cost_csv is not None:
                await self.receive_stock(
                    ReceiveStockRequest(
                        item_id=item.id,
                        quantity=delta,
                        unit_cost=unit_cost_csv,
                        notes="Bulk upload from CSV",
                    ),
                    received_by_id=user_id,
                    commit=False,
                )
            else:
                await self._apply_adjustment(
                    item_id=item.id,
                    quantity_delta=delta,
                    reason="Bulk upload from CSV",
                    reference_type="bulk_upload",
                    reference_id=None,
                    adjusted_by_id=user_id,
                    audit_action="inventory.bulk_upload",
                )
            rows_processed += 1

        await self.db.commit()
        return {
            "rows_processed": rows_processed,
            "items_created": items_created,
            "errors": errors,
        }
