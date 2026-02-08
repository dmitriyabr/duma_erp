"""Service for Inventory module."""

import csv
import io
from decimal import Decimal

from sqlalchemy import func, select
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
from src.modules.items.models import Item, ItemType
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
                quantity_reserved=0,
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
        if new_total_quantity < stock.quantity_reserved:
            raise ValidationError(
                f"Receipt would result in quantity ({new_total_quantity}) less than reserved ({stock.quantity_reserved})"
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

        if new_quantity < stock.quantity_reserved:
            raise ValidationError(
                f"Adjustment would result in quantity ({new_quantity}) less than reserved ({stock.quantity_reserved})"
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

        # Check available quantity (on_hand minus reserved)
        available = stock.quantity_on_hand - stock.quantity_reserved
        if data.quantity > available:
            raise ValidationError(
                f"Insufficient stock. Available: {available}, requested: {data.quantity}. "
                f"(On hand: {stock.quantity_on_hand}, reserved: {stock.quantity_reserved})"
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

    async def reserve_stock(
        self,
        item_id: int,
        quantity: int,
        reference_type: str,
        reference_id: int,
        reserved_by_id: int,
        commit: bool = True,
    ) -> StockMovement:
        """Reserve stock for pending issuance.

        Increases quantity_reserved without changing quantity_on_hand.
        Will be called from Reservation module when Invoice is paid.
        """
        if quantity <= 0:
            raise ValidationError("Reserve quantity must be positive")

        stock = await self._get_or_create_stock(item_id)

        # Check available quantity
        available = stock.quantity_on_hand - stock.quantity_reserved
        if quantity > available:
            raise ValidationError(
                f"Insufficient stock to reserve. Available: {available}, requested: {quantity}"
            )

        # Store before values
        reserved_before = stock.quantity_reserved

        # Update stock
        stock.quantity_reserved += quantity

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=item_id,
            movement_type=MovementType.RESERVE.value,
            quantity=quantity,
            unit_cost=None,
            quantity_before=stock.quantity_on_hand,  # On hand doesn't change
            quantity_after=stock.quantity_on_hand,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=f"Reserved {quantity} units",
            created_by_id=reserved_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action="inventory.reserve",
            entity_type="Stock",
            entity_id=stock.id,
            user_id=reserved_by_id,
            old_values={"quantity_reserved": reserved_before},
            new_values={
                "quantity_reserved": stock.quantity_reserved,
                "reserved_quantity": quantity,
            },
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
        return movement

    async def unreserve_stock(
        self,
        item_id: int,
        quantity: int,
        reference_type: str,
        reference_id: int,
        unreserved_by_id: int,
        commit: bool = True,
    ) -> StockMovement:
        """Unreserve stock (cancel reservation).

        Decreases quantity_reserved without changing quantity_on_hand.
        Will be called when Invoice is cancelled or reservation is fulfilled.
        """
        if quantity <= 0:
            raise ValidationError("Unreserve quantity must be positive")

        result = await self.db.execute(
            select(Stock).where(Stock.item_id == item_id)
        )
        stock = result.scalar_one_or_none()
        if not stock:
            raise NotFoundError(f"No stock record for item {item_id}")

        if quantity > stock.quantity_reserved:
            raise ValidationError(
                f"Cannot unreserve {quantity} units. Only {stock.quantity_reserved} reserved."
            )

        # Store before values
        reserved_before = stock.quantity_reserved

        # Update stock
        stock.quantity_reserved -= quantity

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=item_id,
            movement_type=MovementType.UNRESERVE.value,
            quantity=-quantity,
            unit_cost=None,
            quantity_before=stock.quantity_on_hand,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=f"Unreserved {quantity} units",
            created_by_id=unreserved_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action="inventory.unreserve",
            entity_type="Stock",
            entity_id=stock.id,
            user_id=unreserved_by_id,
            old_values={"quantity_reserved": reserved_before},
            new_values={
                "quantity_reserved": stock.quantity_reserved,
                "unreserved_quantity": quantity,
            },
        )

        if commit:
            await self.db.commit()
            await self.db.refresh(movement)
        return movement

    async def issue_reserved_stock(
        self,
        item_id: int,
        quantity: int,
        reference_type: str,
        reference_id: int,
        issued_by_id: int,
        commit: bool = True,
    ) -> StockMovement:
        """Issue previously reserved stock.

        Decreases both quantity_on_hand and quantity_reserved.
        Used when fulfilling a reservation (actual issuance to student).
        """
        if quantity <= 0:
            raise ValidationError("Issue quantity must be positive")

        result = await self.db.execute(
            select(Stock).where(Stock.item_id == item_id)
        )
        stock = result.scalar_one_or_none()
        if not stock:
            raise NotFoundError(f"No stock record for item {item_id}")

        if quantity > stock.quantity_reserved:
            raise ValidationError(
                f"Cannot issue {quantity} reserved units. Only {stock.quantity_reserved} reserved."
            )

        # Store before values
        quantity_before = stock.quantity_on_hand
        reserved_before = stock.quantity_reserved

        # Update stock
        stock.quantity_on_hand -= quantity
        stock.quantity_reserved -= quantity

        # Create movement record
        movement = StockMovement(
            stock_id=stock.id,
            item_id=item_id,
            movement_type=MovementType.ISSUE.value,
            quantity=-quantity,
            unit_cost=stock.average_cost,
            quantity_before=quantity_before,
            quantity_after=stock.quantity_on_hand,
            average_cost_before=stock.average_cost,
            average_cost_after=stock.average_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=f"Issued {quantity} reserved units",
            created_by_id=issued_by_id,
        )
        self.db.add(movement)

        await self.audit.log(
            action="inventory.issue_reserved",
            entity_type="Stock",
            entity_id=stock.id,
            user_id=issued_by_id,
            old_values={
                "quantity_on_hand": quantity_before,
                "quantity_reserved": reserved_before,
            },
            new_values={
                "quantity_on_hand": stock.quantity_on_hand,
                "quantity_reserved": stock.quantity_reserved,
                "issued_quantity": quantity,
            },
        )

        if commit:
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
            available = stock.quantity_on_hand - stock.quantity_reserved
            if item_data.quantity > available:
                raise ValidationError(
                    f"Insufficient stock for item {item_data.item_id}. "
                    f"Available: {available}, requested: {item_data.quantity}"
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

        # Update issuance status
        issuance.status = IssuanceStatus.CANCELLED.value

        await self.audit.log(
            action="inventory.issuance.cancel",
            entity_type="Issuance",
            entity_id=issuance.id,
            user_id=cancelled_by_id,
            old_values={"status": IssuanceStatus.COMPLETED.value},
            new_values={"status": IssuanceStatus.CANCELLED.value},
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
            # Zero quantity_on_hand only (do not touch quantity_reserved)
            result = await self.db.execute(
                select(Stock)
                .options(selectinload(Stock.item))
                .join(Item)
                .where(Item.item_type == ItemType.PRODUCT.value)
                .where(Stock.quantity_on_hand > 0)
            )
            stocks_to_zero = list(result.scalars().unique().all())
            for stock in stocks_to_zero:
                if stock.quantity_reserved > 0:
                    raise ValidationError(
                        "Cannot overwrite warehouse while there is reserved stock. "
                        "Cancel or fulfill reservations first."
                    )
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
            if target < stock.quantity_reserved:
                errors.append(
                    {
                        "row": row_num,
                        "message": f"quantity {target} less than reserved {stock.quantity_reserved}",
                    }
                )
                continue

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
