import pytest
from decimal import Decimal
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.core.exceptions import NotFoundError, ValidationError
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
    StudentDiscountCreate,
)
from src.modules.discounts.service import DiscountService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.students.models import Gender, Grade, Student, StudentStatus
from src.modules.terms.models import PriceSetting, Term, TermStatus


class TestDiscountReasonService:
    """Tests for discount reason management."""

    async def test_create_reason(self, db_session: AsyncSession):
        """Test creating a discount reason."""
        service = DiscountService(db_session)

        reason = await service.create_reason(
            DiscountReasonCreate(code="scholarship", name="Scholarship"),
            created_by_id=1,
        )

        assert reason.id is not None
        assert reason.code == "scholarship"
        assert reason.name == "Scholarship"
        assert reason.is_active is True

    async def test_create_duplicate_reason(self, db_session: AsyncSession):
        """Test that duplicate reason codes raise error."""
        service = DiscountService(db_session)

        await service.create_reason(
            DiscountReasonCreate(code="test", name="Test"),
            created_by_id=1,
        )

        from src.core.exceptions import DuplicateError

        with pytest.raises(DuplicateError):
            await service.create_reason(
                DiscountReasonCreate(code="test", name="Another Test"),
                created_by_id=1,
            )

    async def test_list_reasons(self, db_session: AsyncSession):
        """Test listing discount reasons."""
        service = DiscountService(db_session)

        await service.create_reason(
            DiscountReasonCreate(code="r1", name="Reason 1"),
            created_by_id=1,
        )
        await service.create_reason(
            DiscountReasonCreate(code="r2", name="Reason 2"),
            created_by_id=1,
        )

        reasons = await service.list_reasons()
        assert len(reasons) >= 2


class TestDiscountService:
    """Tests for discount application."""

    async def _setup_test_data(self, db_session: AsyncSession) -> dict:
        """Create test data for discount tests."""
        # Create category and kit
        category = Category(name="Test Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        kit = Kit(
            category_id=category.id,
            sku_code="TST-ITEM",
            name="Test Item",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(kit)
        await db_session.flush()

        # Create grade and student
        grade = Grade(code="DTST", name="Discount Test", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-DSC-000001",
            first_name="Discount",
            last_name="Test",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=1,
        )
        db_session.add(student)
        await db_session.flush()

        # Create invoice
        invoice = Invoice(
            invoice_number="INV-DSC-000001",
            student_id=student.id,
            term_id=None,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.DRAFT.value,
            created_by_id=1,
        )
        db_session.add(invoice)
        await db_session.flush()

        # Create invoice line
        line = InvoiceLine(
            invoice_id=invoice.id,
            kit_id=kit.id,
            description="Test Item",
            quantity=1,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            net_amount=Decimal("1000.00"),
            paid_amount=Decimal("0.00"),
            remaining_amount=Decimal("1000.00"),
        )
        db_session.add(line)
        await db_session.flush()

        # Create discount reason
        reason = DiscountReason(code="test_reason", name="Test Reason", is_active=True)
        db_session.add(reason)
        await db_session.flush()

        await db_session.commit()

        return {
            "kit": kit,
            "student": student,
            "invoice": invoice,
            "line": line,
            "reason": reason,
        }

    async def test_apply_fixed_discount(self, db_session: AsyncSession):
        """Test applying a fixed discount."""
        data = await self._setup_test_data(db_session)
        service = DiscountService(db_session)

        discount = await service.apply_discount(
            DiscountApply(
                invoice_line_id=data["line"].id,
                value_type=DiscountValueType.FIXED,
                value=Decimal("200.00"),
                reason_id=data["reason"].id,
            ),
            applied_by_id=1,
        )

        assert discount.id is not None
        assert discount.value_type == DiscountValueType.FIXED.value
        assert discount.value == Decimal("200.00")
        assert discount.calculated_amount == Decimal("200.00")

        # Check line was updated
        await db_session.refresh(data["line"])
        assert data["line"].discount_amount == Decimal("200.00")
        assert data["line"].net_amount == Decimal("800.00")

    async def test_apply_percentage_discount(self, db_session: AsyncSession):
        """Test applying a percentage discount."""
        data = await self._setup_test_data(db_session)
        service = DiscountService(db_session)

        discount = await service.apply_discount(
            DiscountApply(
                invoice_line_id=data["line"].id,
                value_type=DiscountValueType.PERCENTAGE,
                value=Decimal("15.00"),  # 15%
                reason_text="Custom reason",
            ),
            applied_by_id=1,
        )

        assert discount.calculated_amount == Decimal("150.00")  # 15% of 1000

        await db_session.refresh(data["line"])
        assert data["line"].discount_amount == Decimal("150.00")
        assert data["line"].net_amount == Decimal("850.00")

    async def test_remove_discount(self, db_session: AsyncSession):
        """Test removing a discount."""
        data = await self._setup_test_data(db_session)
        service = DiscountService(db_session)

        # Apply discount
        discount = await service.apply_discount(
            DiscountApply(
                invoice_line_id=data["line"].id,
                value_type=DiscountValueType.FIXED,
                value=Decimal("300.00"),
            ),
            applied_by_id=1,
        )

        # Remove it
        await service.remove_discount(discount.id, removed_by_id=1)

        # Check line was updated
        await db_session.refresh(data["line"])
        assert data["line"].discount_amount == Decimal("0.00")
        assert data["line"].net_amount == Decimal("1000.00")

    async def test_discount_cannot_exceed_line_total(self, db_session: AsyncSession):
        """Test that discount cannot exceed line total."""
        data = await self._setup_test_data(db_session)
        service = DiscountService(db_session)

        # Apply first discount of 800
        await service.apply_discount(
            DiscountApply(
                invoice_line_id=data["line"].id,
                value_type=DiscountValueType.FIXED,
                value=Decimal("800.00"),
            ),
            applied_by_id=1,
        )

        # Try to apply another discount of 300 (would exceed 1000 total)
        with pytest.raises(ValidationError):
            await service.apply_discount(
                DiscountApply(
                    invoice_line_id=data["line"].id,
                    value_type=DiscountValueType.FIXED,
                    value=Decimal("300.00"),
                ),
                applied_by_id=1,
            )


class TestStudentDiscountService:
    """Tests for student discount management."""

    async def _setup_student(self, db_session: AsyncSession) -> Student:
        """Create a test student."""
        grade = Grade(code="SDTST", name="Student Discount Test", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-SD-000001",
            first_name="Student",
            last_name="Discount",
            gender=Gender.FEMALE.value,
            grade_id=grade.id,
            guardian_name="Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=1,
        )
        db_session.add(student)
        await db_session.flush()
        await db_session.commit()
        return student

    async def test_create_student_discount(self, db_session: AsyncSession):
        """Test creating a student discount."""
        student = await self._setup_student(db_session)
        service = DiscountService(db_session)

        discount = await service.create_student_discount(
            StudentDiscountCreate(
                student_id=student.id,
                applies_to=StudentDiscountAppliesTo.SCHOOL_FEE,
                value_type=DiscountValueType.PERCENTAGE,
                value=Decimal("10.00"),
                reason_text="Sibling discount",
            ),
            created_by_id=1,
        )

        assert discount.id is not None
        assert discount.student_id == student.id
        assert discount.applies_to == StudentDiscountAppliesTo.SCHOOL_FEE.value
        assert discount.value_type == DiscountValueType.PERCENTAGE.value
        assert discount.value == Decimal("10.00")
        assert discount.is_active is True

    async def test_list_student_discounts(self, db_session: AsyncSession):
        """Test listing student discounts."""
        student = await self._setup_student(db_session)
        service = DiscountService(db_session)

        await service.create_student_discount(
            StudentDiscountCreate(
                student_id=student.id,
                value_type=DiscountValueType.FIXED,
                value=Decimal("500.00"),
            ),
            created_by_id=1,
        )

        discounts, total = await service.list_student_discounts(student_id=student.id)
        assert total >= 1

    async def test_update_student_discount(self, db_session: AsyncSession):
        """Test updating a student discount."""
        student = await self._setup_student(db_session)
        service = DiscountService(db_session)

        discount = await service.create_student_discount(
            StudentDiscountCreate(
                student_id=student.id,
                value_type=DiscountValueType.FIXED,
                value=Decimal("500.00"),
            ),
            created_by_id=1,
        )

        from src.modules.discounts.schemas import StudentDiscountUpdate

        updated = await service.update_student_discount(
            discount.id,
            StudentDiscountUpdate(value=Decimal("600.00"), is_active=False),
            updated_by_id=1,
        )

        assert updated.value == Decimal("600.00")
        assert updated.is_active is False


class TestDiscountEndpoints:
    """Tests for discount API endpoints."""

    async def _setup_auth_and_data(
        self, db_session: AsyncSession
    ) -> tuple[str, int, dict]:
        """Create super admin and test data."""
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="discountadmin@school.com",
            password="Admin123",
            full_name="Discount Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()

        _, access_token, _ = await auth_service.authenticate(
            "discountadmin@school.com", "Admin123"
        )

        # Create test data
        grade = Grade(code="APIDSC", name="API Discount", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        student = Student(
            student_number="STU-APIDSC-001",
            first_name="API",
            last_name="Discount",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Guardian",
            guardian_phone="+254712345678",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(student)
        await db_session.flush()
        await db_session.commit()

        return access_token, user.id, {"student": student}

    async def test_create_reason_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a discount reason via API."""
        token, _, _ = await self._setup_auth_and_data(db_session)

        response = await client.post(
            "/api/v1/discounts/reasons",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "api_test", "name": "API Test Reason"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["code"] == "api_test"

    async def test_list_reasons_api(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing discount reasons via API."""
        token, _, _ = await self._setup_auth_and_data(db_session)

        response = await client.get(
            "/api/v1/discounts/reasons",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    async def test_create_student_discount_api(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test creating a student discount via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        response = await client.post(
            "/api/v1/discounts/student",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "applies_to": "school_fee",
                "value_type": "percentage",
                "value": "15.00",
                "reason_text": "Staff child",
            },
        )

        assert response.status_code == 201
        result = response.json()
        assert result["success"] is True
        assert result["data"]["value_type"] == "percentage"
        assert float(result["data"]["value"]) == 15.0

    async def test_list_student_discounts_api(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test listing student discounts via API."""
        token, _, data = await self._setup_auth_and_data(db_session)

        # Create a discount first
        await client.post(
            "/api/v1/discounts/student",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "student_id": data["student"].id,
                "value_type": "fixed",
                "value": "500.00",
            },
        )

        response = await client.get(
            f"/api/v1/discounts/student?student_id={data['student'].id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["total"] >= 1
