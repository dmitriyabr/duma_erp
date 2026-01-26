from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import DuplicateError, ValidationError
from src.modules.students.models import Grade
from src.modules.terms.models import TermStatus
from src.modules.terms.schemas import (
    PriceSettingCreate,
    TermCreate,
    TransportPricingCreate,
    TransportZoneCreate,
)
from src.modules.terms.service import TermService


async def _seed_grades(db_session: AsyncSession, grades: list[tuple[str, str, int]]) -> None:
    for code, name, order in grades:
        db_session.add(
            Grade(code=code, name=name, display_order=order, is_active=True)
        )
    await db_session.flush()


class TestTermService:
    """Tests for TermService."""

    async def _create_super_admin(self, db_session: AsyncSession) -> int:
        """Helper to create super admin."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        return user.id

    async def test_create_term(self, db_session: AsyncSession):
        """Test creating a new term."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        term = await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )

        assert term.id is not None
        assert term.year == 2026
        assert term.term_number == 1
        assert term.display_name == "2026-T1"
        assert term.status == TermStatus.DRAFT.value

    async def test_create_term_duplicate(self, db_session: AsyncSession):
        """Test that duplicate term raises error."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )

        with pytest.raises(DuplicateError):
            await service.create_term(
                TermCreate(year=2026, term_number=1),
                created_by_id=admin_id,
            )

    async def test_activate_term_closes_previous(self, db_session: AsyncSession):
        """Test that activating a term closes the previous active term."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        # Create and activate first term
        term1 = await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )
        term1 = await service.activate_term(term1.id, activated_by_id=admin_id)
        assert term1.status == TermStatus.ACTIVE.value

        # Create and activate second term
        term2 = await service.create_term(
            TermCreate(year=2026, term_number=2),
            created_by_id=admin_id,
        )
        term2 = await service.activate_term(term2.id, activated_by_id=admin_id)

        # Refresh term1
        term1 = await service.get_term_by_id(term1.id)

        assert term1.status == TermStatus.CLOSED.value
        assert term2.status == TermStatus.ACTIVE.value

    async def test_cannot_activate_closed_term(self, db_session: AsyncSession):
        """Test that closed term cannot be activated."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        term = await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )
        await service.activate_term(term.id, activated_by_id=admin_id)
        await service.close_term(term.id, closed_by_id=admin_id)

        with pytest.raises(ValidationError):
            await service.activate_term(term.id, activated_by_id=admin_id)

    async def test_copy_pricing_from_previous_term(self, db_session: AsyncSession):
        """Test that pricing is copied from previous term."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        await _seed_grades(
            db_session,
            [("G1", "Grade 1", 1), ("G2", "Grade 2", 2)],
        )

        # Create first term with pricing
        term1 = await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )
        await service.update_price_settings(
            term1.id,
            [
                PriceSettingCreate(grade="G1", school_fee_amount=Decimal("10000.00")),
                PriceSettingCreate(grade="G2", school_fee_amount=Decimal("11000.00")),
            ],
            updated_by_id=admin_id,
        )

        # Create second term - should copy pricing
        term2 = await service.create_term(
            TermCreate(year=2026, term_number=2),
            created_by_id=admin_id,
        )

        term2 = await service.get_term_by_id(term2.id, with_pricing=True)

        assert len(term2.price_settings) == 2
        grades = {ps.grade for ps in term2.price_settings}
        assert grades == {"G1", "G2"}

    async def test_transport_zones(self, db_session: AsyncSession):
        """Test transport zone CRUD."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        # Create zone
        zone = await service.create_transport_zone(
            TransportZoneCreate(zone_name="Test Zone", zone_code="TZ"),
            created_by_id=admin_id,
        )

        assert zone.id is not None
        assert zone.zone_name == "Test Zone"
        assert zone.is_active is True

        # List zones
        zones = await service.list_transport_zones()
        assert len(zones) == 1

    async def test_transport_pricing(self, db_session: AsyncSession):
        """Test transport pricing update."""
        admin_id = await self._create_super_admin(db_session)
        service = TermService(db_session)

        # Create term and zone
        term = await service.create_term(
            TermCreate(year=2026, term_number=1),
            created_by_id=admin_id,
        )
        zone = await service.create_transport_zone(
            TransportZoneCreate(zone_name="Zone A", zone_code="ZA"),
            created_by_id=admin_id,
        )

        # Set pricing
        pricings = await service.update_transport_pricing(
            term.id,
            [TransportPricingCreate(zone_id=zone.id, transport_fee_amount=Decimal("5000.00"))],
            updated_by_id=admin_id,
        )

        assert len(pricings) == 1
        assert pricings[0].transport_fee_amount == Decimal("5000.00")


class TestTermEndpoints:
    """Tests for term API endpoints."""

    async def _get_admin_token(self, client: AsyncClient, db_session: AsyncSession) -> str:
        """Helper to get admin token."""
        auth_service = AuthService(db_session)
        await auth_service.create_user(
            email="admin@test.com",
            password="Password123",
            full_name="Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Password123"},
        )
        return response.json()["data"]["access_token"]

    async def test_create_term(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a term via API."""
        token = await self._get_admin_token(client, db_session)

        response = await client.post(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
            json={"year": 2026, "term_number": 1},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["year"] == 2026
        assert data["data"]["term_number"] == 1
        assert data["data"]["status"] == "Draft"

    async def test_activate_term(self, client: AsyncClient, db_session: AsyncSession):
        """Test activating a term via API."""
        token = await self._get_admin_token(client, db_session)

        # Create term
        create_response = await client.post(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
            json={"year": 2026, "term_number": 1},
        )
        term_id = create_response.json()["data"]["id"]

        # Activate term
        response = await client.post(
            f"/api/v1/terms/{term_id}/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "Active"

    async def test_update_price_settings(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating price settings via API."""
        token = await self._get_admin_token(client, db_session)

        await _seed_grades(
            db_session,
            [("PP1", "Pre-Primary 1", 1), ("G1", "Grade 1", 2)],
        )

        # Create term
        create_response = await client.post(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
            json={"year": 2026, "term_number": 1},
        )
        term_id = create_response.json()["data"]["id"]

        # Update price settings
        response = await client.put(
            f"/api/v1/terms/{term_id}/price-settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "price_settings": [
                    {"grade": "PP1", "school_fee_amount": "8000.00"},
                    {"grade": "G1", "school_fee_amount": "10000.00"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    async def test_list_terms(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing terms via API."""
        token = await self._get_admin_token(client, db_session)

        # Create terms
        await client.post(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
            json={"year": 2026, "term_number": 1},
        )
        await client.post(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
            json={"year": 2026, "term_number": 2},
        )

        # List
        response = await client.get(
            "/api/v1/terms",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
