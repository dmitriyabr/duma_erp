from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.audit import AuditAction, create_audit_log
from src.core.exceptions import DuplicateError, NotFoundError, ValidationError
from src.modules.terms.models import (
    PriceSetting,
    Term,
    TermStatus,
    TransportPricing,
    TransportZone,
)
from src.modules.items.models import Kit, Category
from src.modules.students.models import Grade
from src.modules.terms.schemas import (
    FixedFeeCreate,
    FixedFeeUpdate,
    PriceSettingCreate,
    TermCreate,
    TermUpdate,
    TransportPricingCreate,
    TransportZoneCreate,
    TransportZoneUpdate,
)


class TermService:
    """Service for term and pricing management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Term Methods ---

    async def get_term_by_id(self, term_id: int, with_pricing: bool = False) -> Term | None:
        """Get term by ID, optionally with pricing data."""
        stmt = select(Term).where(Term.id == term_id)
        if with_pricing:
            stmt = stmt.options(
                selectinload(Term.price_settings),
                selectinload(Term.transport_pricings).selectinload(TransportPricing.zone),
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_term(self) -> Term | None:
        """Get the currently active term."""
        stmt = select(Term).where(Term.status == TermStatus.ACTIVE.value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_term(self) -> Term | None:
        """Get the most recent term (by year and term_number)."""
        stmt = select(Term).order_by(Term.year.desc(), Term.term_number.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_terms(self, year: int | None = None) -> list[Term]:
        """List all terms, optionally filtered by year."""
        stmt = select(Term).order_by(Term.year.desc(), Term.term_number.desc())
        if year:
            stmt = stmt.where(Term.year == year)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_term(self, data: TermCreate, created_by_id: int) -> Term:
        """
        Create a new term.

        Automatically copies pricing from the previous term if available.
        """
        # Check for duplicate
        stmt = select(Term).where(Term.year == data.year, Term.term_number == data.term_number)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise DuplicateError("Term", "year/term_number", f"{data.year}-T{data.term_number}")

        # Generate display name if not provided
        display_name = data.display_name or f"{data.year}-T{data.term_number}"

        # Create term
        term = Term(
            year=data.year,
            term_number=data.term_number,
            display_name=display_name,
            status=TermStatus.DRAFT.value,
            start_date=data.start_date,
            end_date=data.end_date,
            created_by_id=created_by_id,
        )
        self.session.add(term)
        await self.session.flush()

        # Copy pricing from previous term
        await self._copy_pricing_from_previous_term(term)

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.CREATE,
            entity_type="Term",
            entity_id=term.id,
            user_id=created_by_id,
            entity_identifier=term.display_name,
            new_values={
                "year": term.year,
                "term_number": term.term_number,
                "status": term.status,
            },
        )

        return term

    async def _copy_pricing_from_previous_term(self, term: Term) -> None:
        """Copy pricing from the previous term."""
        # Find previous term
        stmt = (
            select(Term)
            .where(Term.id != term.id)
            .order_by(Term.year.desc(), Term.term_number.desc())
            .limit(1)
            .options(
                selectinload(Term.price_settings),
                selectinload(Term.transport_pricings),
            )
        )
        result = await self.session.execute(stmt)
        previous_term = result.scalar_one_or_none()

        if not previous_term:
            return

        # Copy price settings
        for ps in previous_term.price_settings:
            new_ps = PriceSetting(
                term_id=term.id,
                grade=ps.grade,
                school_fee_amount=ps.school_fee_amount,
            )
            self.session.add(new_ps)

        # Copy transport pricing
        for tp in previous_term.transport_pricings:
            new_tp = TransportPricing(
                term_id=term.id,
                zone_id=tp.zone_id,
                transport_fee_amount=tp.transport_fee_amount,
            )
            self.session.add(new_tp)

        await self.session.flush()

    async def update_term(self, term_id: int, data: TermUpdate, updated_by_id: int) -> Term:
        """Update term data (not status)."""
        term = await self.get_term_by_id(term_id)
        if not term:
            raise NotFoundError("Term", term_id)

        old_values = {
            "display_name": term.display_name,
            "start_date": str(term.start_date) if term.start_date else None,
            "end_date": str(term.end_date) if term.end_date else None,
        }

        if data.display_name is not None:
            term.display_name = data.display_name
        if data.start_date is not None:
            term.start_date = data.start_date
        if data.end_date is not None:
            term.end_date = data.end_date

        await self.session.flush()

        new_values = {
            "display_name": term.display_name,
            "start_date": str(term.start_date) if term.start_date else None,
            "end_date": str(term.end_date) if term.end_date else None,
        }

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="Term",
            entity_id=term.id,
            user_id=updated_by_id,
            entity_identifier=term.display_name,
            old_values=old_values,
            new_values=new_values,
        )

        return term

    async def activate_term(self, term_id: int, activated_by_id: int) -> Term:
        """
        Activate a term.

        Automatically closes the currently active term.
        """
        term = await self.get_term_by_id(term_id)
        if not term:
            raise NotFoundError("Term", term_id)

        if term.is_active:
            raise ValidationError("Term is already active")

        if term.is_closed:
            raise ValidationError("Cannot activate a closed term")

        # Close currently active term
        current_active = await self.get_active_term()
        if current_active:
            current_active.status = TermStatus.CLOSED.value
            await create_audit_log(
                session=self.session,
                action=AuditAction.UPDATE,
                entity_type="Term",
                entity_id=current_active.id,
                user_id=activated_by_id,
                entity_identifier=current_active.display_name,
                old_values={"status": TermStatus.ACTIVE.value},
                new_values={"status": TermStatus.CLOSED.value},
                comment=f"Auto-closed when activating {term.display_name}",
            )

        # Activate new term
        old_status = term.status
        term.status = TermStatus.ACTIVE.value
        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="Term",
            entity_id=term.id,
            user_id=activated_by_id,
            entity_identifier=term.display_name,
            old_values={"status": old_status},
            new_values={"status": term.status},
            comment="Term activated",
        )

        return term

    async def close_term(self, term_id: int, closed_by_id: int) -> Term:
        """Close a term manually."""
        term = await self.get_term_by_id(term_id)
        if not term:
            raise NotFoundError("Term", term_id)

        if term.is_closed:
            raise ValidationError("Term is already closed")

        old_status = term.status
        term.status = TermStatus.CLOSED.value
        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="Term",
            entity_id=term.id,
            user_id=closed_by_id,
            entity_identifier=term.display_name,
            old_values={"status": old_status},
            new_values={"status": term.status},
            comment="Term closed manually",
        )

        return term

    # --- Price Settings Methods ---

    async def update_price_settings(
        self,
        term_id: int,
        settings: list[PriceSettingCreate],
        updated_by_id: int,
    ) -> list[PriceSetting]:
        """Bulk update price settings for a term."""
        term = await self.get_term_by_id(term_id)
        if not term:
            raise NotFoundError("Term", term_id)

        grade_codes = {s.grade for s in settings}
        if grade_codes:
            result = await self.session.execute(
                select(Grade.code).where(Grade.code.in_(grade_codes))
            )
            existing_codes = set(result.scalars().all())
            missing = sorted(grade_codes - existing_codes)
            if missing:
                raise ValidationError(
                    f"Unknown grade codes in price settings: {', '.join(missing)}"
                )

        # Delete existing settings
        stmt = select(PriceSetting).where(PriceSetting.term_id == term_id)
        result = await self.session.execute(stmt)
        for ps in result.scalars().all():
            await self.session.delete(ps)
        await self.session.flush()  # Commit deletions before inserting new ones

        # Create new settings
        new_settings = []
        for s in settings:
            ps = PriceSetting(
                term_id=term_id,
                grade=s.grade,
                school_fee_amount=s.school_fee_amount,
            )
            self.session.add(ps)
            new_settings.append(ps)

        await self.session.flush()

        # Audit log
        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="PriceSetting",
            entity_id=term_id,
            user_id=updated_by_id,
            entity_identifier=term.display_name,
            new_values={"grades": [s.grade for s in settings]},
            comment="Price settings updated",
        )

        return new_settings

    # --- Transport Zone Methods ---

    async def list_transport_zones(self, include_inactive: bool = False) -> list[TransportZone]:
        """List all transport zones."""
        stmt = select(TransportZone).order_by(TransportZone.zone_name)
        if not include_inactive:
            stmt = stmt.where(TransportZone.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_transport_zone(
        self, data: TransportZoneCreate, created_by_id: int
    ) -> TransportZone:
        """Create a new transport zone."""
        # Check for duplicate
        stmt = select(TransportZone).where(
            (TransportZone.zone_name == data.zone_name) | (TransportZone.zone_code == data.zone_code)
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise DuplicateError("TransportZone", "zone_name/zone_code", data.zone_name)

        zone = TransportZone(
            zone_name=data.zone_name,
            zone_code=data.zone_code,
            is_active=True,
        )
        self.session.add(zone)
        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.CREATE,
            entity_type="TransportZone",
            entity_id=zone.id,
            user_id=created_by_id,
            entity_identifier=zone.zone_name,
        )

        return zone

    async def update_transport_zone(
        self, zone_id: int, data: TransportZoneUpdate, updated_by_id: int
    ) -> TransportZone:
        """Update a transport zone."""
        stmt = select(TransportZone).where(TransportZone.id == zone_id)
        result = await self.session.execute(stmt)
        zone = result.scalar_one_or_none()

        if not zone:
            raise NotFoundError("TransportZone", zone_id)

        if data.zone_name is not None:
            zone.zone_name = data.zone_name
        if data.zone_code is not None:
            zone.zone_code = data.zone_code
        if data.is_active is not None:
            zone.is_active = data.is_active

        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="TransportZone",
            entity_id=zone.id,
            user_id=updated_by_id,
            entity_identifier=zone.zone_name,
        )

        return zone

    # --- Transport Pricing Methods ---

    async def update_transport_pricing(
        self,
        term_id: int,
        pricings: list[TransportPricingCreate],
        updated_by_id: int,
    ) -> list[TransportPricing]:
        """Bulk update transport pricing for a term."""
        term = await self.get_term_by_id(term_id)
        if not term:
            raise NotFoundError("Term", term_id)

        # Delete existing pricing
        stmt = select(TransportPricing).where(TransportPricing.term_id == term_id)
        result = await self.session.execute(stmt)
        for tp in result.scalars().all():
            await self.session.delete(tp)
        await self.session.flush()  # Commit deletions before inserting new ones

        # Create new pricing
        new_pricings = []
        for p in pricings:
            tp = TransportPricing(
                term_id=term_id,
                zone_id=p.zone_id,
                transport_fee_amount=p.transport_fee_amount,
            )
            self.session.add(tp)
            new_pricings.append(tp)

        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="TransportPricing",
            entity_id=term_id,
            user_id=updated_by_id,
            entity_identifier=term.display_name,
            comment="Transport pricing updated",
        )

        return new_pricings

    # --- Fixed Fee Methods (using Kits from "Fixed Fees" category) ---

    async def _get_fixed_fees_category_id(self) -> int:
        """Get the ID of the 'Fixed Fees' category."""
        stmt = select(Category.id).where(Category.name == "Fixed Fees")
        result = await self.session.execute(stmt)
        category_id = result.scalar_one_or_none()
        if not category_id:
            raise ValidationError("'Fixed Fees' category not found in database")
        return category_id

    async def list_fixed_fees(self, include_inactive: bool = False) -> list[Kit]:
        """List all fixed fees (kits from 'Fixed Fees' category)."""
        category_id = await self._get_fixed_fees_category_id()
        stmt = select(Kit).where(Kit.category_id == category_id).order_by(Kit.name)
        if not include_inactive:
            stmt = stmt.where(Kit.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_fixed_fee(self, kit_id: int) -> Kit | None:
        """Get a fixed fee kit by ID."""
        category_id = await self._get_fixed_fees_category_id()
        stmt = select(Kit).where(Kit.id == kit_id, Kit.category_id == category_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_fixed_fee(self, data: FixedFeeCreate, created_by_id: int) -> Kit:
        """Create a new fixed fee (as a kit in 'Fixed Fees' category)."""
        category_id = await self._get_fixed_fees_category_id()

        # Check if sku_code already exists
        stmt = select(Kit).where(Kit.sku_code == data.fee_type)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise DuplicateError("Kit", "sku_code", data.fee_type)

        kit = Kit(
            category_id=category_id,
            sku_code=data.fee_type,
            name=data.display_name,
            item_type="service",
            price_type="standard",
            price=data.amount,
            requires_full_payment=True,
            is_active=True,
        )
        self.session.add(kit)
        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.CREATE,
            entity_type="Kit",
            entity_id=kit.id,
            user_id=created_by_id,
            entity_identifier=kit.sku_code,
            new_values={"name": kit.name, "price": str(kit.price)},
        )

        return kit

    async def update_fixed_fee(
        self, fee_id: int, data: FixedFeeUpdate, updated_by_id: int
    ) -> Kit:
        """Update a fixed fee (kit in 'Fixed Fees' category)."""
        kit = await self.get_fixed_fee(fee_id)
        if not kit:
            raise NotFoundError("Kit", fee_id)

        old_values = {"name": kit.name, "price": str(kit.price), "is_active": kit.is_active}

        if data.display_name is not None:
            kit.name = data.display_name
        if data.amount is not None:
            kit.price = data.amount
        if data.is_active is not None:
            kit.is_active = data.is_active

        await self.session.flush()

        await create_audit_log(
            session=self.session,
            action=AuditAction.UPDATE,
            entity_type="Kit",
            entity_id=kit.id,
            user_id=updated_by_id,
            entity_identifier=kit.sku_code,
            old_values=old_values,
            new_values={"name": kit.name, "price": str(kit.price), "is_active": kit.is_active},
        )

        return kit
