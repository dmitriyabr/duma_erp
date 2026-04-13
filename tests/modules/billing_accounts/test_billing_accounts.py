"""Tests for family billing accounts."""

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import UserRole
from src.core.auth.service import AuthService
from src.modules.billing_accounts.models import BillingAccount
from src.modules.billing_accounts.models import BillingAccountType
from src.modules.billing_accounts.schemas import (
    BillingAccountAddMembersRequest,
    BillingAccountCreate,
    BillingAccountListFilters,
)
from src.modules.billing_accounts.service import BillingAccountService
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.items.models import Category, ItemType, Kit, PriceType
from src.modules.payments.models import PaymentMethod
from src.modules.payments.schemas import AutoAllocateRequest, PaymentCreate
from src.modules.payments.service import PaymentService
from src.modules.students.models import Gender, Grade, Student, StudentStatus


class TestBillingAccountService:
    async def _setup_data(self, db_session: AsyncSession) -> dict:
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="family-billing@test.com",
            password="Test123!",
            full_name="Family Billing Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.flush()

        grade = Grade(code="FAM", name="Family Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        category = Category(name="Family Billing", is_active=True)
        db_session.add(category)
        await db_session.flush()

        kit = Kit(
            category_id=category.id,
            sku_code="FAMILY-KIT",
            name="Family Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("1000.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(kit)
        await db_session.flush()

        student_one = Student(
            student_number="STU-FAM-001",
            first_name="Amina",
            last_name="Otieno",
            gender=Gender.FEMALE.value,
            grade_id=grade.id,
            guardian_name="Rose Otieno",
            guardian_phone="+254700000001",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        student_two = Student(
            student_number="STU-FAM-002",
            first_name="Brian",
            last_name="Otieno",
            gender=Gender.MALE.value,
            grade_id=grade.id,
            guardian_name="Rose Otieno",
            guardian_phone="+254700000001",
            status=StudentStatus.ACTIVE.value,
            created_by_id=user.id,
        )
        db_session.add_all([student_one, student_two])
        await db_session.flush()
        await db_session.commit()

        return {
            "user": user,
            "kit": kit,
            "students": [student_one, student_two],
        }

    async def test_create_family_account_moves_existing_credit_and_allocates_across_students(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        payment_service = PaymentService(db_session)
        account_service = BillingAccountService(db_session)

        payment = await payment_service.create_payment(
            PaymentCreate(
                student_id=student_one.id,
                amount=Decimal("1000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="FAMILY-CREDIT-1",
            ),
            received_by_id=data["user"].id,
        )
        await payment_service.complete_payment(payment.id, data["user"].id)

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id, student_two.id],
            ),
            created_by_id=data["user"].id,
        )
        await db_session.refresh(student_one)
        await db_session.refresh(student_two)

        invoice = Invoice(
            invoice_number="INV-FAM-001",
            student_id=student_two.id,
            billing_account_id=family.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("1000.00"),
            created_by_id=data["user"].id,
        )
        db_session.add(invoice)
        await db_session.flush()
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                kit_id=data["kit"].id,
                description="Family Fee",
                quantity=1,
                unit_price=Decimal("1000.00"),
                line_total=Decimal("1000.00"),
                discount_amount=Decimal("0.00"),
                net_amount=Decimal("1000.00"),
                paid_amount=Decimal("0.00"),
                remaining_amount=Decimal("1000.00"),
            )
        )
        await db_session.commit()

        result = await payment_service.allocate_auto(
            AutoAllocateRequest(student_id=student_one.id),
            allocated_by_id=data["user"].id,
        )

        await db_session.refresh(invoice)
        family_detail = await account_service.get_billing_account_detail(family.id)

        assert family.account_type == BillingAccountType.FAMILY.value
        assert result.total_allocated == Decimal("1000.00")
        assert invoice.amount_due == Decimal("0.00")
        assert family_detail.available_balance == Decimal("0.00")
        assert family_detail.member_count == 2

    async def test_get_student_balance_returns_family_context(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        account_service = BillingAccountService(db_session)
        payment_service = PaymentService(db_session)

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id, student_two.id],
            ),
            created_by_id=data["user"].id,
        )

        payment = await payment_service.create_payment(
            PaymentCreate(
                billing_account_id=family.id,
                amount=Decimal("500.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date.today(),
                reference="FAMILY-BALANCE-1",
            ),
            received_by_id=data["user"].id,
        )
        await payment_service.complete_payment(payment.id, data["user"].id)

        balance = await payment_service.get_student_balance(student_two.id)

        assert balance.billing_account_id == family.id
        assert balance.billing_account_name == "Otieno Family"
        assert balance.available_balance == Decimal("500.00")

    async def test_create_family_account_auto_allocates_existing_credit_to_existing_debt(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        payment_service = PaymentService(db_session)
        account_service = BillingAccountService(db_session)

        payment = await payment_service.create_payment(
            PaymentCreate(
                student_id=student_one.id,
                amount=Decimal("1000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="FAMILY-AUTO-CREATE",
            ),
            received_by_id=data["user"].id,
        )
        await payment_service.complete_payment(payment.id, data["user"].id)

        credit_allocations = (
            await db_session.execute(
                select(CreditAllocation).where(CreditAllocation.student_id == student_one.id)
            )
        ).scalars().all()
        for allocation in credit_allocations:
            await payment_service.delete_allocation(allocation.id, data["user"].id, "Reset credit")

        invoice = Invoice(
            invoice_number="INV-FAM-CREATE-001",
            student_id=student_two.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("1000.00"),
            created_by_id=data["user"].id,
        )
        db_session.add(invoice)
        await db_session.flush()
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                kit_id=data["kit"].id,
                description="Family Fee",
                quantity=1,
                unit_price=Decimal("1000.00"),
                line_total=Decimal("1000.00"),
                discount_amount=Decimal("0.00"),
                net_amount=Decimal("1000.00"),
                paid_amount=Decimal("0.00"),
                remaining_amount=Decimal("1000.00"),
            )
        )
        await db_session.commit()

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id, student_two.id],
            ),
            created_by_id=data["user"].id,
        )

        await db_session.refresh(invoice)
        family_detail = await account_service.get_billing_account_detail(family.id)

        assert invoice.amount_due == Decimal("0.00")
        assert family_detail.available_balance == Decimal("0.00")

    async def test_add_member_auto_allocates_existing_family_credit_to_new_member_debt(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        payment_service = PaymentService(db_session)
        account_service = BillingAccountService(db_session)

        student_three = Student(
            student_number="STU-FAM-003",
            first_name="Cynthia",
            last_name="Otieno",
            gender=Gender.FEMALE.value,
            grade_id=student_one.grade_id,
            guardian_name="Rose Otieno",
            guardian_phone="+254700000001",
            status=StudentStatus.ACTIVE.value,
            created_by_id=data["user"].id,
        )
        db_session.add(student_three)
        await db_session.flush()
        await account_service.ensure_student_billing_account(student_three.id)
        await db_session.commit()

        payment = await payment_service.create_payment(
            PaymentCreate(
                student_id=student_one.id,
                amount=Decimal("1000.00"),
                payment_method=PaymentMethod.MPESA,
                payment_date=date.today(),
                reference="FAMILY-AUTO-ADD",
            ),
            received_by_id=data["user"].id,
        )
        await payment_service.complete_payment(payment.id, data["user"].id)

        credit_allocations = (
            await db_session.execute(
                select(CreditAllocation).where(CreditAllocation.student_id == student_one.id)
            )
        ).scalars().all()
        for allocation in credit_allocations:
            await payment_service.delete_allocation(allocation.id, data["user"].id, "Reset credit")

        invoice = Invoice(
            invoice_number="INV-FAM-ADD-001",
            student_id=student_three.id,
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("1000.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("1000.00"),
            created_by_id=data["user"].id,
        )
        db_session.add(invoice)
        await db_session.flush()
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                kit_id=data["kit"].id,
                description="Family Fee",
                quantity=1,
                unit_price=Decimal("1000.00"),
                line_total=Decimal("1000.00"),
                discount_amount=Decimal("0.00"),
                net_amount=Decimal("1000.00"),
                paid_amount=Decimal("0.00"),
                remaining_amount=Decimal("1000.00"),
            )
        )
        await db_session.commit()

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id, student_two.id],
            ),
            created_by_id=data["user"].id,
        )

        updated_family = await account_service.add_members(
            family.id,
            BillingAccountAddMembersRequest(student_ids=[student_three.id]),
            added_by_id=data["user"].id,
        )

        await db_session.refresh(invoice)

        assert invoice.amount_due == Decimal("0.00")
        assert updated_family.available_balance == Decimal("0.00")

    async def test_create_family_account_removes_empty_individual_accounts(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        account_service = BillingAccountService(db_session)

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id, student_two.id],
            ),
            created_by_id=data["user"].id,
        )

        accounts = list((await db_session.execute(select(BillingAccount))).scalars().all())

        assert len(accounts) == 1
        assert accounts[0].id == family.id
        assert accounts[0].account_type == BillingAccountType.FAMILY.value

    async def test_create_family_account_with_new_children_only_keeps_family_type(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        account_service = BillingAccountService(db_session)
        grade_id = data["students"][0].grade_id

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Solo Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                new_children=[
                    {
                        "first_name": "Solo",
                        "last_name": "Otieno",
                        "gender": Gender.MALE,
                        "grade_id": grade_id,
                    }
                ],
            ),
            created_by_id=data["user"].id,
        )

        detail = await account_service.get_billing_account_detail(family.id)
        assert detail.account_type == BillingAccountType.FAMILY.value
        assert detail.member_count == 1
        assert detail.members[0].student_name == "Solo Otieno"

    async def test_create_family_account_with_existing_and_new_children(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        account_service = BillingAccountService(db_session)
        student_one = data["students"][0]

        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Mixed Family",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                primary_guardian_email=None,
                notes=None,
                student_ids=[student_one.id],
                new_children=[
                    {
                        "first_name": "Daisy",
                        "last_name": "Otieno",
                        "gender": Gender.FEMALE,
                        "grade_id": student_one.grade_id,
                    }
                ],
            ),
            created_by_id=data["user"].id,
        )

        detail = await account_service.get_billing_account_detail(family.id)
        member_names = {member.student_name for member in detail.members}
        assert detail.account_type == BillingAccountType.FAMILY.value
        assert detail.member_count == 2
        assert member_names == {"Amina Otieno", "Daisy Otieno"}

    async def test_list_billing_accounts_default_includes_individual_and_family(
        self,
        db_session: AsyncSession,
    ):
        data = await self._setup_data(db_session)
        student_one, student_two = data["students"]
        account_service = BillingAccountService(db_session)

        individual = await account_service.ensure_student_billing_account(student_one.id)
        family = await account_service.create_family_account(
            BillingAccountCreate(
                display_name="Otieno Admission",
                primary_guardian_name="Rose Otieno",
                primary_guardian_phone="+254700000001",
                student_ids=[student_two.id],
            ),
            created_by_id=data["user"].id,
        )

        rows, total = await account_service.list_billing_accounts(BillingAccountListFilters())
        returned_ids = {row.id for row in rows}

        assert total == 2
        assert individual.id in returned_ids
        assert family.id in returned_ids


class TestBillingAccountEndpoints:
    async def _create_family_context(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> dict:
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="family-api@test.com",
            password="Test123!",
            full_name="Family API Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()
        _, access_token, _ = await auth_service.authenticate("family-api@test.com", "Test123!")

        grade = Grade(code="FAMAPI", name="Family API Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.flush()

        category = Category(name="Family API Category", is_active=True)
        db_session.add(category)
        await db_session.flush()

        kit = Kit(
            category_id=category.id,
            sku_code="FAMILY-API-KIT",
            name="Family API Fee",
            item_type=ItemType.SERVICE.value,
            price_type=PriceType.STANDARD.value,
            price=Decimal("200.00"),
            requires_full_payment=False,
            is_active=True,
        )
        db_session.add(kit)
        await db_session.flush()

        students = []
        for idx in (1, 2):
            student = Student(
                student_number=f"STU-FAMAPI-00{idx}",
                first_name=f"Child{idx}",
                last_name="Kamau",
                gender=Gender.MALE.value,
                grade_id=grade.id,
                guardian_name="Jane Kamau",
                guardian_phone="+254711111111",
                status=StudentStatus.ACTIVE.value,
                created_by_id=user.id,
            )
            db_session.add(student)
            students.append(student)
        await db_session.commit()

        create_response = await client.post(
            "/api/v1/billing-accounts",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "display_name": "Kamau Family",
                "primary_guardian_name": "Jane Kamau",
                "primary_guardian_phone": "+254711111111",
                "student_ids": [student.id for student in students],
            },
        )
        assert create_response.status_code == 201
        family = create_response.json()["data"]

        return {
            "access_token": access_token,
            "user": user,
            "grade": grade,
            "kit": kit,
            "students": students,
            "family": family,
        }

    async def test_create_and_list_family_accounts(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        context = await self._create_family_context(client, db_session)
        access_token = context["access_token"]
        created = context["family"]
        assert created["display_name"] == "Kamau Family"
        assert len(created["members"]) == 2

        list_response = await client.get(
            "/api/v1/billing-accounts",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.status_code == 200
        listed = list_response.json()["data"]["items"]
        assert listed[0]["display_name"] == "Kamau Family"

    async def test_create_family_account_with_new_child_only_via_api(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        auth_service = AuthService(db_session)
        user = await auth_service.create_user(
            email="family-new-child@test.com",
            password="Test123!",
            full_name="Family API Admin",
            role=UserRole.SUPER_ADMIN,
        )
        await db_session.commit()
        _, access_token, _ = await auth_service.authenticate("family-new-child@test.com", "Test123!")

        grade = Grade(code="FAMNEW", name="Family New Grade", display_order=1, is_active=True)
        db_session.add(grade)
        await db_session.commit()

        response = await client.post(
            "/api/v1/billing-accounts",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "display_name": "Single Child Family",
                "primary_guardian_name": "Grace Njeri",
                "primary_guardian_phone": "+254733333333",
                "new_children": [
                    {
                        "first_name": "Hope",
                        "last_name": "Njeri",
                        "gender": "female",
                        "grade_id": grade.id,
                    }
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["account_type"] == BillingAccountType.FAMILY.value
        assert data["member_count"] == 1
        assert data["members"][0]["student_name"] == "Hope Njeri"

        list_response = await client.get(
            "/api/v1/billing-accounts",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.status_code == 200
        items = list_response.json()["data"]["items"]
        assert any(item["id"] == data["id"] for item in items)

    async def test_add_child_to_family_via_api(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        context = await self._create_family_context(client, db_session)
        access_token = context["access_token"]
        grade = context["grade"]
        family = context["family"]

        response = await client.post(
            f"/api/v1/billing-accounts/{family['id']}/children",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "first_name": "Child3",
                "last_name": "Kamau",
                "gender": "female",
                "grade_id": grade.id,
            },
        )

        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["member_count"] == 3
        assert any(member["student_name"] == "Child3 Kamau" for member in detail["members"])

    async def test_student_balance_and_students_list_show_student_debt_not_sibling_debt(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        context = await self._create_family_context(client, db_session)
        access_token = context["access_token"]
        user = context["user"]
        kit = context["kit"]
        student_one, student_two = context["students"]
        family = context["family"]

        payment_service = PaymentService(db_session)
        payment = await payment_service.create_payment(
            PaymentCreate(
                billing_account_id=family["id"],
                amount=Decimal("500.00"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_date=date.today(),
                reference="FAMILY-STUDENT-VIEW",
            ),
            received_by_id=user.id,
        )
        await payment_service.complete_payment(payment.id, user.id)

        invoice = Invoice(
            invoice_number="INV-FAMILY-STUDENT-001",
            student_id=student_two.id,
            billing_account_id=family["id"],
            invoice_type=InvoiceType.ADHOC.value,
            status=InvoiceStatus.ISSUED.value,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("200.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("200.00"),
            paid_total=Decimal("0.00"),
            amount_due=Decimal("200.00"),
            created_by_id=user.id,
        )
        db_session.add(invoice)
        await db_session.flush()
        db_session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                kit_id=kit.id,
                description="Family API Fee",
                quantity=1,
                unit_price=Decimal("200.00"),
                line_total=Decimal("200.00"),
                discount_amount=Decimal("0.00"),
                net_amount=Decimal("200.00"),
                paid_amount=Decimal("0.00"),
                remaining_amount=Decimal("200.00"),
            )
        )
        await db_session.commit()

        student_one_balance_response = await client.get(
            f"/api/v1/payments/students/{student_one.id}/balance",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert student_one_balance_response.status_code == 200
        student_one_balance = student_one_balance_response.json()["data"]
        assert Decimal(student_one_balance["available_balance"]) == Decimal("500.00")
        assert Decimal(student_one_balance["outstanding_debt"]) == Decimal("0.00")
        assert Decimal(student_one_balance["balance"]) == Decimal("0.00")

        student_two_balance_response = await client.get(
            f"/api/v1/payments/students/{student_two.id}/balance",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert student_two_balance_response.status_code == 200
        student_two_balance = student_two_balance_response.json()["data"]
        assert Decimal(student_two_balance["available_balance"]) == Decimal("500.00")
        assert Decimal(student_two_balance["outstanding_debt"]) == Decimal("200.00")
        assert Decimal(student_two_balance["balance"]) == Decimal("-200.00")

        students_response = await client.get(
            "/api/v1/students?include_balance=true",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert students_response.status_code == 200
        rows = {row["id"]: row for row in students_response.json()["data"]["items"]}
        assert Decimal(str(rows[student_one.id]["outstanding_debt"])) == Decimal("0.0")
        assert Decimal(str(rows[student_one.id]["balance"])) == Decimal("0.0")
        assert Decimal(str(rows[student_two.id]["outstanding_debt"])) == Decimal("200.0")
        assert Decimal(str(rows[student_two.id]["balance"])) == Decimal("-200.0")
