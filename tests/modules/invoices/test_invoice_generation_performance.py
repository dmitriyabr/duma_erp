"""Performance tests for Invoice Generation."""
import time
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from src.modules.invoices.service import InvoiceService
from src.modules.students.models import Student, StudentStatus, Gender
from src.modules.terms.models import Term, TermStatus, PriceSetting, TransportZone, TransportPricing
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.students.models import Grade
from sqlalchemy import select


class TestInvoiceGenerationPerformance:
    """Performance tests for invoice generation."""

    async def test_generate_term_invoices_performance(
        self, db_session: AsyncSession
    ):
        """Test that invoice generation uses batch queries efficiently."""
        # Setup: Create test data
        from src.core.auth.service import AuthService
        from src.core.auth.models import UserRole
        
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="perf@test.com",
            password="Test123!",
            full_name="Perf Test User",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        # Create category
        category = Category(name="Perf Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        # Create kits
        school_fee_kit = Kit(
            category_id=category.id,
            sku_code="SCH-FEE",
            name="School Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_GRADE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        transport_fee_kit = Kit(
            category_id=category.id,
            sku_code="TRN-FEE",
            name="Transport Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.BY_ZONE.value,
            price=None,
            requires_full_payment=False,
            is_active=True,
        )
        admission_fee_kit = Kit(
            category_id=category.id,
            sku_code="ADMISSION-FEE",
            name="Admission Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("5000.00"),
            requires_full_payment=True,
            is_active=True,
        )
        interview_fee_kit = Kit(
            category_id=category.id,
            sku_code="INTERVIEW-FEE",
            name="Interview Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("500.00"),
            requires_full_payment=True,
            is_active=True,
        )
        db_session.add_all([school_fee_kit, transport_fee_kit, admission_fee_kit, interview_fee_kit])
        await db_session.flush()

        # Create grade
        grade = Grade(code="G1", name="Grade 1", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        # Create transport zone
        zone = TransportZone(zone_name="Zone A", zone_code="ZA", is_active=True)
        db_session.add(zone)
        await db_session.flush()

        # Create term
        from datetime import date
        term = Term(
            year=2026,
            term_number=1,
            display_name="Term 1 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            status=TermStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add(term)
        await db_session.flush()

        # Create price setting
        price_setting = PriceSetting(
            term_id=term.id,
            grade="G1",
            school_fee_amount=Decimal("10000.00"),
        )
        db_session.add(price_setting)

        # Create transport pricing
        transport_pricing = TransportPricing(
            term_id=term.id,
            zone_id=zone.id,
            transport_fee_amount=Decimal("2000.00"),
        )
        db_session.add(transport_pricing)
        await db_session.flush()

        # Create multiple students (simulate batch scenario)
        students = []
        for i in range(10):  # Create 10 students for performance test
            student = Student(
                student_number=f"STU-2026-{i+1:06d}",
                first_name=f"Student{i+1}",
                last_name="Test",
                gender=Gender.MALE.value,
                grade_id=grade.id,
                transport_zone_id=zone.id if i % 2 == 0 else None,  # Half with transport
                guardian_name=f"Guardian {i+1}",
                guardian_phone=f"+25471234567{i}",
                status=StudentStatus.ACTIVE.value,
                created_by_id=user.id,
            )
            db_session.add(student)
            students.append(student)
        await db_session.flush()
        await db_session.commit()

        # Test generation performance
        service = InvoiceService(db_session)
        
        start_time = time.time()
        result = await service.generate_term_invoices(term.id, user.id)
        elapsed = time.time() - start_time

        # With batch queries, should be fast even with multiple students
        # Old version: ~0.1s per student (10 students = 1s+)
        # New version: ~0.01-0.02s per student (10 students = 0.2-0.5s)
        expected_max_time = len(students) * 0.05  # 50ms per student max
        assert elapsed < max(expected_max_time, 1.0), (
            f"Generation took {elapsed:.3f}s for {len(students)} students, "
            f"expected < {max(expected_max_time, 1.0):.3f}s"
        )
        
        print(
            f"\n✓ Generated invoices for {result.total_students_processed} "
            f"students in {elapsed:.3f}s "
            f"({result.school_fee_invoices_created} school fees, "
            f"{result.transport_invoices_created} transport)"
        )

