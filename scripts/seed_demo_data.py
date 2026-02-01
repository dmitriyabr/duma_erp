#!/usr/bin/env python3
"""
Скрипт наполнения базы реалистичными демо-данными школьной жизни (Kenya).

Данные не случайные: имена, классы, суммы сборов, термы, поставщики и т.д.
подобраны так, чтобы отчёты и дашборд выглядели осмысленно.

Использование:
    uv run python scripts/seed_demo_data.py --dry-run   # без записи в БД
    uv run python scripts/seed_demo_data.py --confirm  # записать в БД

Требования: миграции применены (alembic upgrade head), БД доступна.
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth.models import User, UserRole
from src.core.auth.password import hash_password
from src.core.database.session import async_session
from src.core.documents.number_generator import DocumentNumberGenerator
from src.core.config import settings
from src.modules.students.models import Grade, Student, StudentStatus, Gender
from src.modules.terms.models import (
    Term,
    TermStatus,
    PriceSetting,
    TransportZone,
    TransportPricing,
)
from src.modules.items.models import Category, Item, Kit, KitItem, ItemType, PriceType
from src.modules.discounts.models import DiscountReason, StudentDiscount, DiscountValueType, StudentDiscountAppliesTo
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus, InvoiceType
from src.modules.payments.models import Payment, CreditAllocation, PaymentStatus, PaymentMethod
from src.modules.procurement.models import (
    PaymentPurpose,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    GoodsReceivedNote,
    GoodsReceivedLine,
    GoodsReceivedStatus,
    ProcurementPayment,
    ProcurementPaymentStatus,
    ProcurementPaymentMethod,
)
from src.modules.compensations.models import (
    ExpenseClaim,
    ExpenseClaimStatus,
    CompensationPayout,
    PayoutAllocation,
    PayoutMethod,
    EmployeeBalance,
)
from src.modules.inventory.models import Stock, StockMovement, MovementType
from src.modules.reservations.models import Reservation  # noqa: F401 - needed for InvoiceLine relationship
from src.shared.utils.money import round_money

# --- Реалистичные константы (школа в Кении) ---

DEMO_PASSWORD = "demo123"
CURRENT_YEAR = 2026

# Ученики: имя, фамилия, пол, год рождения (для возраста класса)
STUDENTS_DATA = [
    ("Grace", "Wanjiku", Gender.FEMALE, 2019),
    ("James", "Ochieng", Gender.MALE, 2019),
    ("Faith", "Njeri", Gender.FEMALE, 2018),
    ("Brian", "Kamau", Gender.MALE, 2018),
    ("Mary", "Akinyi", Gender.FEMALE, 2018),
    ("David", "Mwangi", Gender.MALE, 2017),
    ("Lucy", "Wambui", Gender.FEMALE, 2017),
    ("Peter", "Kipchoge", Gender.MALE, 2017),
    ("Anne", "Nyambura", Gender.FEMALE, 2016),
    ("Joseph", "Otieno", Gender.MALE, 2016),
    ("Catherine", "Adhiambo", Gender.FEMALE, 2016),
    ("Samuel", "Kibet", Gender.MALE, 2015),
    ("Elizabeth", "Chebet", Gender.FEMALE, 2015),
    ("Daniel", "Korir", Gender.MALE, 2015),
    ("Jane", "Jepchumba", Gender.FEMALE, 2014),
    ("Michael", "Kipruto", Gender.MALE, 2014),
    ("Sarah", "Chepngetich", Gender.FEMALE, 2014),
    ("John", "Kiplagat", Gender.MALE, 2013),
    ("Ruth", "Jepkorir", Gender.FEMALE, 2013),
    ("Paul", "Komen", Gender.MALE, 2013),
    ("Mercy", "Jerono", Gender.FEMALE, 2012),
    ("Simon", "Kiprop", Gender.MALE, 2012),
    ("Joy", "Chepkoech", Gender.FEMALE, 2012),
    ("Thomas", "Kiprotich", Gender.MALE, 2011),
    ("Nancy", "Jepkosgei", Gender.FEMALE, 2011),
]

# Опекуны: имя, телефон (+254...), email (опционально)
GUARDIANS = [
    ("Margaret Wanjiru", "+254712345601", "m.wanjiru@example.com"),
    ("Robert Omondi", "+254723456712", None),
    ("Alice Muthoni", "+254734567823", "a.muthoni@example.com"),
    ("Charles Kariuki", "+254745678934", None),
    ("Helen Wambui", "+254756789045", "h.wambui@example.com"),
    ("George Ndung'u", "+254767890156", None),
    ("Susan Njoki", "+254778901267", "s.njoki@example.com"),
    ("Francis Mutua", "+254789012378", None),
    ("Dorothy Achieng", "+254790123489", "d.achieng@example.com"),
    ("Patrick Odhiambo", "+254701234590", None),
    ("Grace Wanjiku", "+254712345601", None),
    ("Joseph Owino", "+254723456712", "j.owino@example.com"),
    ("Mary Akinyi", "+254734567823", None),
    ("David Okoth", "+254745678934", "d.okoth@example.com"),
    ("Lucy Adhiambo", "+254756789045", None),
    ("Peter Ochieng", "+254767890156", None),
    ("Anne Atieno", "+254778901267", "a.atieno@example.com"),
    ("Samuel Otieno", "+254789012378", None),
    ("Catherine Odongo", "+254790123489", None),
    ("Daniel Omondi", "+254701234590", "d.omondi@example.com"),
    ("Elizabeth Awino", "+254712345601", None),
    ("James Okello", "+254723456712", None),
    ("Faith Akello", "+254734567823", "f.akello@example.com"),
    ("Brian Oluoch", "+254745678934", None),
    ("Jane Aoko", "+254756789045", None),
    ("Michael Ouma", "+254767890156", None),
]

# Школьные сборы по классам (KES) — младшие дешевле, старшие дороже
FEES_BY_GRADE = {
    "PG": Decimal("45000.00"),
    "PP1": Decimal("55000.00"),
    "PP2": Decimal("60000.00"),
    "G1": Decimal("75000.00"),
    "G2": Decimal("78000.00"),
    "G3": Decimal("82000.00"),
    "G4": Decimal("86000.00"),
    "G5": Decimal("90000.00"),
    "G6": Decimal("95000.00"),
}

# Транспорт по зонам (KES за терм)
TRANSPORT_BY_ZONE = {
    "WL": Decimal("12000.00"),
    "KR": Decimal("15000.00"),
    "RU": Decimal("18000.00"),
    "LV": Decimal("14000.00"),
}


async def seed_users(session: AsyncSession) -> dict[str, int]:
    """Создаёт пользователей (SuperAdmin, Admin, User, Accountant). Возвращает id по роли."""
    result = await session.execute(select(User).where(User.email == "admin@school.demo"))
    if result.scalar_one_or_none():
        print("  Users already exist, skip.")
        out = {}
        for r in await session.execute(select(User)):
            u = r.scalar_one()
            out[u.role] = u.id
        return out

    pw = hash_password(DEMO_PASSWORD)
    users = [
        User(
            email="admin@school.demo",
            password_hash=pw,
            full_name="School Admin",
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
        ),
        User(
            email="manager@school.demo",
            password_hash=pw,
            full_name="Deputy Head",
            role=UserRole.ADMIN.value,
            is_active=True,
        ),
        User(
            email="teacher@school.demo",
            password_hash=pw,
            full_name="Jane Teacher",
            role=UserRole.USER.value,
            is_active=True,
        ),
        User(
            email="accountant@school.demo",
            password_hash=pw,
            full_name="Finance Officer",
            role=UserRole.ACCOUNTANT.value,
            is_active=True,
        ),
        User(
            email="guard@school.demo",
            password_hash=None,
            full_name="Security Guard",
            role=UserRole.USER.value,
            is_active=True,
        ),
    ]
    for u in users:
        session.add(u)
    await session.flush()
    role_to_id = {u.role: u.id for u in users}
    print(f"  Created {len(users)} users.")
    return role_to_id


async def seed_grades(session: AsyncSession) -> dict[str, int]:
    """Классы: PG, PP1, PP2, G1..G6. Возвращает code -> id."""
    result = await session.execute(select(Grade).limit(1))
    if result.scalar_one_or_none():
        print("  Grades already exist, skip.")
        return {r.code: r.id for r in (await session.execute(select(Grade))).scalars().all()}

    grades_data = [
        ("PG", "Play Group", 0),
        ("PP1", "Pre-Primary 1", 1),
        ("PP2", "Pre-Primary 2", 2),
        ("G1", "Grade 1", 3),
        ("G2", "Grade 2", 4),
        ("G3", "Grade 3", 5),
        ("G4", "Grade 4", 6),
        ("G5", "Grade 5", 7),
        ("G6", "Grade 6", 8),
    ]
    code_to_id = {}
    for code, name, order in grades_data:
        g = Grade(code=code, name=name, display_order=order, is_active=True)
        session.add(g)
        await session.flush()
        code_to_id[code] = g.id
    print(f"  Created {len(code_to_id)} grades.")
    return code_to_id


async def seed_transport_zones(session: AsyncSession) -> dict[str, int]:
    """Зоны транспорта. Возвращает zone_code -> id."""
    result = await session.execute(select(TransportZone).limit(1))
    if result.scalar_one_or_none():
        print("  Transport zones already exist, skip.")
        return {r.zone_code: r.id for r in (await session.execute(select(TransportZone))).scalars().all()}

    zones = [
        ("Westlands", "WL"),
        ("Karen", "KR"),
        ("Runda", "RU"),
        ("Lavington", "LV"),
    ]
    code_to_id = {}
    for name, code in zones:
        z = TransportZone(zone_name=name, zone_code=code, is_active=True)
        session.add(z)
        await session.flush()
        code_to_id[code] = z.id
    print(f"  Created {len(code_to_id)} transport zones.")
    return code_to_id


async def seed_terms(session: AsyncSession, user_id: int, grade_codes: list[str], zone_codes: list[str]) -> dict[str, int]:
    """Термы 2025-T1, 2025-T2, 2026-T1 + price_settings и transport_pricings. key = display_name -> term_id."""
    result = await session.execute(select(Term).limit(1))
    if result.scalar_one_or_none():
        print("  Terms already exist, skip.")
        name_to_id = {}
        for t in (await session.execute(select(Term))).scalars().all():
            name_to_id[t.display_name] = t.id
        return name_to_id

    # Даты термов (примерно: T1 Jan–Apr, T2 May–Aug, T3 Sep–Dec)
    terms_config = [
        (2025, 1, "2025-T1", TermStatus.CLOSED.value, date(2025, 1, 13), date(2025, 4, 4)),
        (2025, 2, "2025-T2", TermStatus.CLOSED.value, date(2025, 5, 5), date(2025, 8, 8)),
        (2026, 1, "2026-T1", TermStatus.ACTIVE.value, date(2026, 1, 12), date(2026, 4, 3)),
    ]
    name_to_id = {}
    for year, num, display_name, status, start, end in terms_config:
        t = Term(
            year=year,
            term_number=num,
            display_name=display_name,
            status=status,
            start_date=start,
            end_date=end,
            created_by_id=user_id,
        )
        session.add(t)
        await session.flush()
        name_to_id[display_name] = t.id

        for code in grade_codes:
            amount = FEES_BY_GRADE.get(code, Decimal("70000.00"))
            ps = PriceSetting(term_id=t.id, grade=code, school_fee_amount=amount)
            session.add(ps)
        for zid in zone_codes:
            z = (await session.execute(select(TransportZone).where(TransportZone.zone_code == zid))).scalar_one()
            amount = TRANSPORT_BY_ZONE.get(zid, Decimal("15000.00"))
            tp = TransportPricing(term_id=t.id, zone_id=z.id, transport_fee_amount=amount)
            session.add(tp)
    await session.flush()
    print(f"  Created {len(terms_config)} terms with price_settings and transport_pricings.")
    return name_to_id


async def seed_categories_and_kits(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Категории и киты: Fixed Fees (ADMISSION-FEE, INTERVIEW-FEE), School Fees (by_grade), Transport (by_zone). Возвращает sku_code -> kit_id."""
    result = await session.execute(select(Category).limit(1))
    if result.scalar_one_or_none():
        print("  Categories/Kits already exist, skip.")
        return {r.sku_code: r.id for r in (await session.execute(select(Kit))).scalars().all()}

    cat_fixed = Category(name="Fixed Fees", is_active=True)
    cat_school = Category(name="School Fees", is_active=True)
    cat_transport = Category(name="Transport", is_active=True)
    session.add(cat_fixed)
    session.add(cat_school)
    session.add(cat_transport)
    await session.flush()

    kits = [
        Kit(
            category_id=cat_fixed.id,
            sku_code="ADMISSION-FEE",
            name="Admission Fee",
            item_type="service",
            price_type="standard",
            price=Decimal("5000.00"),
            requires_full_payment=True,
            is_active=True,
        ),
        Kit(
            category_id=cat_fixed.id,
            sku_code="INTERVIEW-FEE",
            name="Interview Fee",
            item_type="service",
            price_type="standard",
            price=Decimal("2000.00"),
            requires_full_payment=True,
            is_active=True,
        ),
        Kit(
            category_id=cat_school.id,
            sku_code="SCHOOL-FEE",
            name="School Fee",
            item_type="service",
            price_type="by_grade",
            price=None,
            requires_full_payment=False,
            is_active=True,
        ),
        Kit(
            category_id=cat_transport.id,
            sku_code="TRANSPORT",
            name="Transport",
            item_type="service",
            price_type="by_zone",
            price=None,
            requires_full_payment=False,
            is_active=True,
        ),
    ]
    for k in kits:
        session.add(k)
    await session.flush()
    sku_to_id = {k.sku_code: k.id for k in kits}
    print(f"  Created categories and {len(kits)} kits.")
    return sku_to_id


async def seed_payment_purposes(session: AsyncSession) -> dict[str, int]:
    """Цели закупок. name -> id."""
    result = await session.execute(select(PaymentPurpose).limit(1))
    if result.scalar_one_or_none():
        print("  Payment purposes already exist, skip.")
        return {r.name: r.id for r in (await session.execute(select(PaymentPurpose))).scalars().all()}

    names = ["Supplies", "Uniforms", "Transport", "Maintenance", "Other"]
    name_to_id = {}
    for n in names:
        p = PaymentPurpose(name=n, is_active=True)
        session.add(p)
        await session.flush()
        name_to_id[n] = p.id
    print(f"  Created {len(name_to_id)} payment purposes.")
    return name_to_id


async def seed_discount_reasons(session: AsyncSession) -> dict[str, int]:
    """Причины скидок. code -> id."""
    result = await session.execute(select(DiscountReason).limit(1))
    if result.scalar_one_or_none():
        print("  Discount reasons already exist, skip.")
        return {r.code: r.id for r in (await session.execute(select(DiscountReason))).scalars().all()}

    items = [("SIBLING", "Sibling discount"), ("STAFF", "Staff child"), ("BURSARY", "Bursary")]
    code_to_id = {}
    for code, name in items:
        r = DiscountReason(code=code, name=name, is_active=True)
        session.add(r)
        await session.flush()
        code_to_id[code] = r.id
    print(f"  Created {len(code_to_id)} discount reasons.")
    return code_to_id


async def seed_students(
    session: AsyncSession,
    num_gen: DocumentNumberGenerator,
    grade_code_to_id: dict[str, int],
    zone_code_to_id: dict[str, int],
    user_id: int,
) -> list[tuple[int, str, int | None]]:
    """Студенты с реалистичными именами и опекунами. Возвращает [(student_id, grade_code, zone_id or None), ...]."""
    result = await session.execute(select(Student).limit(1))
    if result.scalar_one_or_none():
        print("  Students already exist, skip.")
        students = []
        for s in (await session.execute(select(Student).options(selectinload(Student.grade)))).scalars().all():
            students.append((s.id, s.grade.code, s.transport_zone_id))
        return students

    grade_codes = list(grade_code_to_id.keys())
    zone_codes = list(zone_code_to_id.keys())
    students_out = []
    for i, (first, last, gender, yob) in enumerate(STUDENTS_DATA):
        student_number = await num_gen.generate("STU", CURRENT_YEAR)
        g_code = grade_codes[i % len(grade_codes)]
        grade_id = grade_code_to_id[g_code]
        # Примерно треть с транспортом
        zone_id = zone_code_to_id[zone_codes[i % 3]] if i % 3 == 0 else None
        guardian_name, guardian_phone, guardian_email = GUARDIANS[i % len(GUARDIANS)]
        enrollment = date(yob + 3, 1, 15) if yob + 3 < CURRENT_YEAR else date(CURRENT_YEAR, 1, 10)
        s = Student(
            student_number=student_number,
            first_name=first,
            last_name=last,
            date_of_birth=date(yob, 6, 1),
            gender=gender.value,
            grade_id=grade_id,
            transport_zone_id=zone_id,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            guardian_email=guardian_email,
            status=StudentStatus.ACTIVE.value,
            enrollment_date=enrollment,
            created_by_id=user_id,
        )
        session.add(s)
        await session.flush()
        students_out.append((s.id, g_code, zone_id))
    print(f"  Created {len(students_out)} students.")
    return students_out


async def seed_invoices(
    session: AsyncSession,
    num_gen: DocumentNumberGenerator,
    term_name_to_id: dict[str, int],
    grade_code_to_id: dict[str, int],
    zone_code_to_id: dict[str, int],
    sku_to_kit_id: dict[str, int],
    students: list[tuple[int, str, int | None]],
    user_id: int,
) -> list[tuple[int, Decimal, Decimal]]:
    """
    Счета за 2025-T1 и 2026-T1: school_fee + transport (если zone есть).
    Реалистичное распределение: часть полностью оплачена, часть частично, часть только выставлена.
    Возвращает [(invoice_id, total, paid_total), ...] для последующих платежей/аллокаций.
    """
    result = await session.execute(select(Invoice).limit(1))
    if result.scalar_one_or_none():
        print("  Invoices already exist, skip.")
        return []

    school_kit_id = sku_to_kit_id["SCHOOL-FEE"]
    transport_kit_id = sku_to_kit_id["TRANSPORT"]
    term_ids = [term_name_to_id["2025-T1"], term_name_to_id["2026-T1"]]
    invoice_totals = []

    for term_id in term_ids:
        term = (await session.execute(select(Term).where(Term.id == term_id))).scalar_one()
        # PriceSetting по grade
        ps_result = await session.execute(select(PriceSetting).where(PriceSetting.term_id == term_id))
        fee_by_grade = {ps.grade: ps.school_fee_amount for ps in ps_result.scalars().all()}
        # TransportPricing по zone_id
        tp_result = await session.execute(select(TransportPricing).where(TransportPricing.term_id == term_id))
        transport_by_zone = {tp.zone_id: tp.transport_fee_amount for tp in tp_result.scalars().all()}

        for idx, (student_id, g_code, zone_id) in enumerate(students):
            inv_number = await num_gen.generate("INV", term.year)
            school_fee = fee_by_grade.get(g_code, Decimal("70000.00"))
            transport_fee = transport_by_zone.get(zone_id, Decimal("0.00")) if zone_id else Decimal("0.00")
            total_inv = school_fee + transport_fee
            # Распределение: ~40% paid, ~35% partially_paid, ~25% issued
            r = idx % 10
            if r < 4:
                status = InvoiceStatus.PAID.value
                paid_total = total_inv
            elif r < 7:
                status = InvoiceStatus.PARTIALLY_PAID.value
                paid_total = round_money(total_inv * Decimal("0.5"))
            else:
                status = InvoiceStatus.ISSUED.value
                paid_total = Decimal("0.00")
            amount_due = total_inv - paid_total

            inv = Invoice(
                invoice_number=inv_number,
                student_id=student_id,
                term_id=term_id,
                invoice_type=InvoiceType.SCHOOL_FEE.value,
                status=status,
                issue_date=term.start_date and term.start_date + timedelta(days=5),
                due_date=term.end_date,
                subtotal=total_inv,
                discount_total=Decimal("0.00"),
                total=total_inv,
                paid_total=paid_total,
                amount_due=amount_due,
                created_by_id=user_id,
            )
            session.add(inv)
            await session.flush()

            # Line 1: School Fee
            line_total_s = school_fee
            paid_s = round_money(paid_total * (school_fee / total_inv)) if total_inv else Decimal("0.00")
            rem_s = line_total_s - paid_s
            line1 = InvoiceLine(
                invoice_id=inv.id,
                kit_id=school_kit_id,
                description="School Fee",
                quantity=1,
                unit_price=school_fee,
                line_total=line_total_s,
                discount_amount=Decimal("0.00"),
                net_amount=line_total_s,
                paid_amount=paid_s,
                remaining_amount=rem_s,
            )
            session.add(line1)
            await session.flush()

            if transport_fee > 0:
                paid_t = paid_total - paid_s
                rem_t = transport_fee - paid_t
                line2 = InvoiceLine(
                    invoice_id=inv.id,
                    kit_id=transport_kit_id,
                    description="Transport",
                    quantity=1,
                    unit_price=transport_fee,
                    line_total=transport_fee,
                    discount_amount=Decimal("0.00"),
                    net_amount=transport_fee,
                    paid_amount=paid_t,
                    remaining_amount=rem_t,
                )
                session.add(line2)

            invoice_totals.append((inv.id, total_inv, paid_total))

    await session.flush()
    print(f"  Created {len(invoice_totals)} invoices.")
    return invoice_totals


async def seed_payments_and_allocations(
    session: AsyncSession,
    num_gen: DocumentNumberGenerator,
    students: list[tuple[int, str, int | None]],
    invoice_totals: list[tuple[int, Decimal, Decimal]],
    user_id: int,
) -> None:
    """Платежи и аллокации по студентам, чтобы paid_total по счетам совпадал."""
    if not invoice_totals:
        return
    result = await session.execute(select(Payment).limit(1))
    if result.scalar_one_or_none():
        print("  Payments already exist, skip.")
        return

    from collections import defaultdict
    student_invoices = defaultdict(list)
    for inv_id, total, paid in invoice_totals:
        inv = (await session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
        student_invoices[inv.student_id].append((inv_id, total, paid))

    for student_id, inv_list in student_invoices.items():
        total_paid_by_student = sum(paid for _, _, paid in inv_list)
        if total_paid_by_student == 0:
            continue
        pay_number = await num_gen.generate("PAY", CURRENT_YEAR)
        pay = Payment(
            payment_number=pay_number,
            receipt_number=await num_gen.generate("RCP", CURRENT_YEAR),
            student_id=student_id,
            amount=total_paid_by_student,
            payment_method=PaymentMethod.MPESA.value,
            payment_date=date(CURRENT_YEAR, 2, 1) + timedelta(days=hash(student_id) % 30),
            reference="M-Pesa",
            status=PaymentStatus.COMPLETED.value,
            received_by_id=user_id,
        )
        session.add(pay)
        await session.flush()
        for inv_id, _total, paid in inv_list:
            if paid <= 0:
                continue
            session.add(CreditAllocation(
                student_id=student_id,
                invoice_id=inv_id,
                invoice_line_id=None,
                amount=paid,
                allocated_by_id=user_id,
            ))
    await session.flush()
    print("  Created payments and credit allocations.")


async def seed_procurement(
    session: AsyncSession,
    num_gen: DocumentNumberGenerator,
    purpose_ids: dict[str, int],
    user_id: int,
    employee_user_id: int,
) -> tuple[list[int], int | None]:
    """Заказы, один GRN, один PPAY с employee_paid_id. Возвращает (list of PO ids, procurement_payment_id with employee)."""
    result = await session.execute(select(PurchaseOrder).limit(1))
    if result.scalar_one_or_none():
        print("  Procurement already exists, skip.")
        return [], None

    purpose_supplies = purpose_ids["Supplies"]
    purpose_other = purpose_ids["Other"]

    # PO 1: поставка канцтоваров
    po_number1 = await num_gen.generate("PO", CURRENT_YEAR)
    po1 = PurchaseOrder(
        po_number=po_number1,
        supplier_name="Nairobi Office Supplies Ltd",
        supplier_contact="+254700111222",
        purpose_id=purpose_supplies,
        status=PurchaseOrderStatus.ORDERED.value,
        order_date=date(CURRENT_YEAR, 1, 20),
        expected_delivery_date=date(CURRENT_YEAR, 2, 5),
        track_to_warehouse=False,
        expected_total=Decimal("25000.00"),
        received_value=Decimal("0.00"),
        paid_total=Decimal("0.00"),
        debt_amount=Decimal("25000.00"),
        created_by_id=user_id,
    )
    session.add(po1)
    await session.flush()
    session.add(PurchaseOrderLine(
        po_id=po1.id,
        item_id=None,
        description="A4 paper, pens, folders",
        quantity_expected=50,
        quantity_cancelled=0,
        unit_price=Decimal("500.00"),
        line_total=Decimal("25000.00"),
        quantity_received=0,
        line_order=1,
    ))
    await session.flush()

    # PO 2: оплата охранником (employee) — создаст ExpenseClaim
    po_number2 = await num_gen.generate("PO", CURRENT_YEAR)
    po2 = PurchaseOrder(
        po_number=po_number2,
        supplier_name="Guard reimbursement",
        supplier_contact=None,
        purpose_id=purpose_other,
        status=PurchaseOrderStatus.RECEIVED.value,
        order_date=date(CURRENT_YEAR, 1, 15),
        expected_delivery_date=None,
        track_to_warehouse=False,
        expected_total=Decimal("3000.00"),
        received_value=Decimal("3000.00"),
        paid_total=Decimal("3000.00"),
        debt_amount=Decimal("0.00"),
        created_by_id=user_id,
    )
    session.add(po2)
    await session.flush()
    session.add(PurchaseOrderLine(
        po_id=po2.id,
        item_id=None,
        description="Out-of-pocket (guard)",
        quantity_expected=1,
        quantity_cancelled=0,
        unit_price=Decimal("3000.00"),
        line_total=Decimal("3000.00"),
        quantity_received=1,
        line_order=1,
    ))
    await session.flush()

    # PPAY по PO2 от имени сотрудника (guard)
    ppay_number = await num_gen.generate("PPAY", CURRENT_YEAR)
    ppay = ProcurementPayment(
        payment_number=ppay_number,
        po_id=po2.id,
        purpose_id=purpose_other,
        payee_name="Security Guard",
        payment_date=date(CURRENT_YEAR, 1, 25),
        amount=Decimal("3000.00"),
        payment_method=ProcurementPaymentMethod.CASH.value,
        company_paid=False,
        employee_paid_id=employee_user_id,
        status=ProcurementPaymentStatus.POSTED.value,
        created_by_id=user_id,
    )
    session.add(ppay)
    await session.flush()
    emp_payment_id = ppay.id

    # ExpenseClaim от этого платежа (вручную, как в create_from_payment)
    claim_number = await num_gen.generate("CLM", CURRENT_YEAR)
    claim = ExpenseClaim(
        claim_number=claim_number,
        payment_id=ppay.id,
        employee_id=employee_user_id,
        purpose_id=purpose_other,
        amount=Decimal("3000.00"),
        description=f"Reimbursement {ppay.payment_number}",
        expense_date=ppay.payment_date,
        status=ExpenseClaimStatus.APPROVED.value,
        paid_amount=Decimal("3000.00"),
        remaining_amount=Decimal("0.00"),
        auto_created_from_payment=True,
        related_procurement_payment_id=ppay.id,
    )
    session.add(claim)
    await session.flush()

    # Compensation payout и аллокация на claim
    payout_number = await num_gen.generate("PAY", CURRENT_YEAR)
    payout = CompensationPayout(
        payout_number=payout_number,
        employee_id=employee_user_id,
        payout_date=date(CURRENT_YEAR, 2, 1),
        amount=Decimal("3000.00"),
        payment_method=PayoutMethod.CASH.value,
    )
    session.add(payout)
    await session.flush()
    session.add(PayoutAllocation(payout_id=payout.id, claim_id=claim.id, allocated_amount=Decimal("3000.00")))
    # EmployeeBalance для отчётов
    eb = EmployeeBalance(
        employee_id=employee_user_id,
        total_approved=Decimal("3000.00"),
        total_paid=Decimal("3000.00"),
        balance=Decimal("0.00"),
    )
    session.add(eb)
    await session.flush()

    print("  Created POs, procurement payment, expense claim, payout, employee balance.")
    return [po1.id, po2.id], emp_payment_id


async def seed_inventory_items_and_stock(session: AsyncSession, user_id: int) -> None:
    """Пара товаров (форма) и остатки для отчётов по складу."""
    result = await session.execute(select(Item).limit(1))
    if result.scalar_one_or_none():
        print("  Inventory items/stock already exist, skip.")
        return

    cat = Category(name="Uniforms", is_active=True)
    session.add(cat)
    await session.flush()
    items = [
        Item(
            category_id=cat.id,
            sku_code="SHIRT-P",
            name="School Shirt (Primary)",
            item_type=ItemType.PRODUCT.value,
            price_type="standard",
            price=Decimal("1200.00"),
            requires_full_payment=True,
            is_active=True,
        ),
        Item(
            category_id=cat.id,
            sku_code="SHORTS-P",
            name="School Shorts (Primary)",
            item_type=ItemType.PRODUCT.value,
            price_type="standard",
            price=Decimal("800.00"),
            requires_full_payment=True,
            is_active=True,
        ),
    ]
    for it in items:
        session.add(it)
    await session.flush()
    for it in items:
        st = Stock(
            item_id=it.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            average_cost=Decimal("600.00"),
        )
        session.add(st)
        await session.flush()
        session.add(StockMovement(
            stock_id=st.id,
            item_id=it.id,
            movement_type=MovementType.RECEIPT.value,
            quantity=100,
            unit_cost=Decimal("600.00"),
            quantity_before=0,
            quantity_after=100,
            average_cost_before=Decimal("0.00"),
            average_cost_after=Decimal("600.00"),
            reference_type="adjustment",
            reference_id=None,
            notes="Opening balance (demo)",
            created_by_id=user_id,
        ))
    await session.flush()
    print("  Created Uniforms category, 2 items, stock and movements.")


async def run_seed(session: AsyncSession, dry_run: bool) -> None:
    user_ids = await seed_users(session)
    admin_id = user_ids.get(UserRole.SUPER_ADMIN.value) or user_ids.get(UserRole.ADMIN.value)
    user_id = admin_id or list(user_ids.values())[0]
    employee_user_id = user_ids.get(UserRole.USER.value)  # guard/teacher for expense claim

    grade_code_to_id = await seed_grades(session)
    zone_code_to_id = await seed_transport_zones(session)
    term_name_to_id = await seed_terms(
        session, user_id, list(grade_code_to_id.keys()), list(zone_code_to_id.keys())
    )
    sku_to_kit_id = await seed_categories_and_kits(session, user_id)
    purpose_ids = await seed_payment_purposes(session)
    await seed_discount_reasons(session)

    num_gen = DocumentNumberGenerator(session)
    students = await seed_students(session, num_gen, grade_code_to_id, zone_code_to_id, user_id)
    invoice_totals = await seed_invoices(
        session, num_gen, term_name_to_id, grade_code_to_id, zone_code_to_id,
        sku_to_kit_id, students, user_id,
    )
    await seed_payments_and_allocations(session, num_gen, students, invoice_totals, user_id)
    await seed_procurement(session, num_gen, purpose_ids, user_id, employee_user_id or user_id)
    await seed_inventory_items_and_stock(session, user_id)

    if dry_run:
        await session.rollback()
        print("\n[DRY-RUN] Rolled back, no data written.")
    else:
        await session.commit()
        print("\nSeed completed successfully.")


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Seed database with realistic school demo data")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit")
    parser.add_argument("--confirm", action="store_true", help="Commit changes")
    args = parser.parse_args()
    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm")
        sys.exit(1)

    print("Database:", settings.database_url.split("@")[-1] if "@" in settings.database_url else "?")
    print("Mode:", "DRY-RUN" if args.dry_run else "CONFIRM")
    async with async_session() as session:
        await run_seed(session, dry_run=args.dry_run)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
