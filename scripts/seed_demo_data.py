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

# --- Склад: категории и сотни товаров (реалистичная школа) ---
# Формат: категория -> список (sku, name, price_kes)
ITEMS_BY_CATEGORY: dict[str, list[tuple[str, str, int]]] = {
    "Uniforms": [
        ("SHIRT-PG", "School Shirt Play Group", 650),
        ("SHIRT-PP1", "School Shirt PP1", 700),
        ("SHIRT-PP2", "School Shirt PP2", 750),
        ("SHIRT-G1", "School Shirt Grade 1", 800),
        ("SHIRT-G2", "School Shirt Grade 2", 850),
        ("SHIRT-G3", "School Shirt Grade 3", 900),
        ("SHIRT-G4", "School Shirt Grade 4", 950),
        ("SHIRT-G5", "School Shirt Grade 5", 1000),
        ("SHIRT-G6", "School Shirt Grade 6", 1100),
        ("SHORTS-PG", "School Shorts Play Group", 450),
        ("SHORTS-PP1", "School Shorts PP1", 500),
        ("SHORTS-PP2", "School Shorts PP2", 550),
        ("SHORTS-G1", "School Shorts Grade 1", 600),
        ("SHORTS-G2", "School Shorts Grade 2", 650),
        ("SHORTS-G3", "School Shorts Grade 3", 700),
        ("SHORTS-G4", "School Shorts Grade 4", 750),
        ("SHORTS-G5", "School Shorts Grade 5", 800),
        ("SHORTS-G6", "School Shorts Grade 6", 850),
        ("SWEATER-S", "School Sweater Small", 1200),
        ("SWEATER-M", "School Sweater Medium", 1350),
        ("SWEATER-L", "School Sweater Large", 1500),
        ("SOCKS-P", "School Socks Primary", 250),
        ("TIE", "School Tie", 350),
        ("CAP", "School Cap", 400),
        ("SHOES-28", "School Shoes size 28", 1800),
        ("SHOES-30", "School Shoes size 30", 1900),
        ("SHOES-32", "School Shoes size 32", 2000),
        ("SHOES-34", "School Shoes size 34", 2100),
        ("SHOES-36", "School Shoes size 36", 2200),
    ],
    "Stationery": [
        ("PEN-BLUE", "Ballpen Blue", 25),
        ("PEN-RED", "Ballpen Red", 25),
        ("PEN-BLACK", "Ballpen Black", 25),
        ("PENCIL-HB", "Pencil HB", 15),
        ("PENCIL-2B", "Pencil 2B", 15),
        ("ERASER", "Eraser", 20),
        ("SHARPENER", "Pencil Sharpener", 30),
        ("RULER-30", "Ruler 30cm", 40),
        ("RULER-15", "Ruler 15cm", 25),
        ("NB-72", "Notebook 72 pages", 80),
        ("NB-96", "Notebook 96 pages", 100),
        ("NB-120", "Notebook 120 pages", 120),
        ("EX-BK-SQ", "Exercise book Squared", 45),
        ("EX-BK-LN", "Exercise book Lined", 45),
        ("A4-REAM", "A4 Paper Ream 500 sheets", 450),
        ("FOLDER", "Plastic Folder", 80),
        ("STAPLER", "Stapler", 250),
        ("STAPLES", "Staples box", 80),
        ("GLUE-STICK", "Glue Stick", 60),
        ("SCISSORS", "Scissors", 150),
        ("MARKER-BLUE", "Marker Blue", 120),
        ("MARKER-RED", "Marker Red", 120),
        ("MARKER-BLACK", "Marker Black", 120),
        ("HIGHLIGHTER", "Highlighter Yellow", 100),
        ("CARTRIDGE-B", "Ink Cartridge Blue", 350),
        ("CARTRIDGE-BK", "Ink Cartridge Black", 350),
        ("CHALK-BOX", "Chalk box", 80),
        ("BOARD-MARKER", "Whiteboard Marker", 150),
        ("DUSTER", "Board Duster", 200),
        ("TAPE-DISP", "Tape Dispenser", 180),
        ("TAPE-ROLL", "Cellotape Roll", 100),
        ("CLIP-BOX", "Paper Clips box", 50),
        ("RUBBER-BAND", "Rubber Bands pack", 40),
        ("LABEL-A4", "Labels A4 sheet", 120),
        ("ENVELOPE-A4", "Envelope A4", 15),
        ("FILE-BOX", "File box", 350),
        ("CRAYON-12", "Crayons 12 pcs", 180),
        ("WATER-COLOUR", "Water Colours set", 450),
        ("BRUSH-SET", "Paint Brushes set", 220),
        ("CLAY-PACK", "Modelling Clay", 150),
    ],
    "Cleaning": [
        ("DETERGENT-1L", "Detergent 1L", 280),
        ("DETERGENT-5L", "Detergent 5L", 1200),
        ("SOAP-BAR", "Bar Soap", 80),
        ("SOAP-LIQ", "Liquid Soap 1L", 350),
        ("MOP", "Mop", 650),
        ("BUCKET", "Bucket", 400),
        ("BLEACH-1L", "Bleach 1L", 200),
        ("TOILET-ROLL", "Toilet Roll", 120),
        ("HAND-TOWEL", "Hand Towel pack", 450),
        ("BROOM", "Broom", 350),
        ("DUSTPAN", "Dustpan", 250),
        ("GLOVES", "Cleaning Gloves", 180),
        ("SPRAY-500", "Spray 500ml", 320),
        ("FLOOR-WAX", "Floor Wax 1L", 550),
        ("SPONGE-PACK", "Sponges pack", 150),
    ],
    "Sports": [
        ("BALL-FOOT", "Football", 1200),
        ("BALL-NET", "Netball", 1100),
        ("BALL-RUGBY", "Rugby Ball", 1800),
        ("BALL-VOLLEY", "Volleyball", 950),
        ("CONES-SET", "Cones set 10", 800),
        ("WHISTLE", "Whistle", 150),
        ("FIRST-AID", "First Aid Kit", 1200),
        ("BIB-SET", "Bibs set 10", 600),
        ("SKIP-ROPE", "Skipping Rope", 200),
        ("STOPWATCH", "Stopwatch", 800),
        ("BAT-CRICKET", "Cricket Bat", 2500),
        ("BALL-CRICKET", "Cricket Ball", 450),
        ("STUMPS", "Cricket Stumps", 900),
        ("NET-BADMINTON", "Badminton Net", 1500),
        ("SHUTTLE-PACK", "Shuttlecocks pack", 350),
        ("RACKET", "Badminton Racket", 1200),
    ],
    "Catering": [
        ("RICE-1KG", "Rice 1kg", 180),
        ("RICE-5KG", "Rice 5kg", 850),
        ("BEANS-1KG", "Beans 1kg", 220),
        ("BEANS-5KG", "Beans 5kg", 1000),
        ("OIL-1L", "Cooking Oil 1L", 450),
        ("OIL-5L", "Cooking Oil 5L", 2100),
        ("FLOUR-1KG", "Wheat Flour 1kg", 120),
        ("FLOUR-5KG", "Wheat Flour 5kg", 550),
        ("SUGAR-1KG", "Sugar 1kg", 150),
        ("SUGAR-5KG", "Sugar 5kg", 700),
        ("TEA-500G", "Tea 500g", 350),
        ("MILK-1L", "Milk 1L", 120),
        ("SALT-1KG", "Salt 1kg", 80),
        ("SPICE-MIX", "Spice mix pack", 250),
        ("TOMATO-TIN", "Tomato paste tin", 180),
        ("ONION-1KG", "Onions 1kg", 100),
        ("POTATO-1KG", "Potatoes 1kg", 90),
        ("CABBAGE", "Cabbage", 80),
        ("CARROT-1KG", "Carrots 1kg", 120),
    ],
}

# Поставщики и цели заказов для эмуляции жизни школы
SUPPLIERS = [
    ("Nairobi Office Supplies Ltd", "+254700111222", "Supplies"),
    ("EduStationery Kenya", "+254711222333", "Supplies"),
    ("School Uniforms Co", None, "Uniforms"),
    ("CleanPro Supplies", "+254722333444", "Maintenance"),
    ("Sports Warehouse Nairobi", "+254733444555", "Other"),
    ("Metro Catering Supplies", "+254744555666", "Other"),
    ("Jamia Wholesale", "+254755666777", "Other"),
    ("Guard reimbursement", None, "Other"),
    ("Teacher out-of-pocket", None, "Other"),
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


def _sku_price_list() -> list[tuple[str, Decimal]]:
    """Список (sku, price) для генерации строк заказов."""
    out: list[tuple[str, Decimal]] = []
    for items_list in ITEMS_BY_CATEGORY.values():
        for sku, _name, price_kes in items_list:
            out.append((sku, Decimal(str(price_kes))))
    return out


async def seed_procurement(
    session: AsyncSession,
    num_gen: DocumentNumberGenerator,
    purpose_ids: dict[str, int],
    user_id: int,
    employee_user_id: int,
    item_id_by_sku: dict[str, int],
) -> None:
    """Десятки заказов, GRN, платежей; эмуляция жизни школы (сотни строк, склады)."""
    result = await session.execute(select(PurchaseOrder).limit(1))
    if result.scalar_one_or_none():
        print("  Procurement already exists, skip.")
        return

    sku_price_list = _sku_price_list()
    if not sku_price_list:
        print("  No items for PO lines, skip procurement.")
        return

    purpose_other = purpose_ids["Other"]
    purpose_supplies = purpose_ids["Supplies"]
    purpose_uniforms = purpose_ids.get("Uniforms", purpose_other)
    purpose_maint = purpose_ids.get("Maintenance", purpose_other)

    # Создаём 45+ заказов: разные поставщики, даты, статусы (draft / ordered / received / partially_received)
    po_list: list[tuple[PurchaseOrder, list[PurchaseOrderLine], bool]] = []  # (po, lines, will_receive)
    for i in range(48):
        supplier_name, contact, purpose_name = SUPPLIERS[i % len(SUPPLIERS)]
        purpose_id = purpose_ids.get(purpose_name, purpose_other)
        if supplier_name in ("Guard reimbursement", "Teacher out-of-pocket"):
            purpose_id = purpose_other
        # Статусы: ~12 draft, ~12 ordered, ~24 received/partially_received
        r = i % 4
        if r == 0:
            status = PurchaseOrderStatus.DRAFT.value
            will_receive = False
        elif r == 1:
            status = PurchaseOrderStatus.ORDERED.value
            will_receive = False
        else:
            status = PurchaseOrderStatus.RECEIVED.value if r == 3 else PurchaseOrderStatus.PARTIALLY_RECEIVED.value
            will_receive = True
        order_d = date(CURRENT_YEAR - 1, 2, 1) + timedelta(days=i * 8) if i < 24 else date(CURRENT_YEAR, 1, 1) + timedelta(days=(i - 24) * 5)
        po_number = await num_gen.generate("PO", order_d.year)
        po = PurchaseOrder(
            po_number=po_number,
            supplier_name=supplier_name,
            supplier_contact=contact,
            purpose_id=purpose_id,
            status=status,
            order_date=order_d,
            expected_delivery_date=order_d + timedelta(days=14),
            track_to_warehouse=(purpose_name != "Other"),
            expected_total=Decimal("0.00"),
            received_value=Decimal("0.00"),
            paid_total=Decimal("0.00"),
            debt_amount=Decimal("0.00"),
            created_by_id=user_id,
        )
        session.add(po)
        await session.flush()
        # 3–8 строк на заказ (для не-Other — item_id из склада; для Other — без item)
        num_lines = 3 + (i % 6)
        lines: list[PurchaseOrderLine] = []
        expected_total = Decimal("0.00")
        for ln in range(num_lines):
            sku, price = sku_price_list[(i * 7 + ln) % len(sku_price_list)]
            item_id = item_id_by_sku.get(sku) if supplier_name not in ("Guard reimbursement", "Teacher out-of-pocket") else None
            qty = 10 + (i + ln) % 50 if item_id else 1
            unit_price = price * (Decimal("0.9") + Decimal((i % 20) / 100))
            line_total = round_money(unit_price * qty)
            expected_total += line_total
            pl = PurchaseOrderLine(
                po_id=po.id,
                item_id=item_id,
                description=sku if item_id else ("Out-of-pocket" if "Guard" in supplier_name else "Sundries"),
                quantity_expected=qty,
                quantity_cancelled=0,
                unit_price=unit_price,
                line_total=line_total,
                quantity_received=0,
                line_order=ln + 1,
            )
            session.add(pl)
            await session.flush()
            lines.append(pl)
        po.expected_total = expected_total
        po.received_value = Decimal("0.00")
        po.debt_amount = expected_total
        if will_receive:
            po_list.append((po, lines, True))
        await session.flush()

    # GRN для полученных/частично полученных заказов (~25)
    stock_by_item: dict[int, Stock] = {}
    grn_count = 0
    for po, lines, _ in po_list:
        grn_number = await num_gen.generate("GRN", po.order_date.year)
        received_date = po.order_date + timedelta(days=5)
        grn = GoodsReceivedNote(
            grn_number=grn_number,
            po_id=po.id,
            status=GoodsReceivedStatus.APPROVED.value,
            received_date=received_date,
            received_by_id=user_id,
            approved_by_id=user_id,
            approved_at=received_date,
            notes="Demo receipt",
        )
        session.add(grn)
        await session.flush()
        grn_count += 1
        received_value = Decimal("0.00")
        for pl in lines:
            qty_rec = pl.quantity_expected if po.status == PurchaseOrderStatus.RECEIVED.value else max(1, pl.quantity_expected // 2)
            pl.quantity_received = qty_rec
            received_value += round_money(pl.unit_price * qty_rec)
            grn_line = GoodsReceivedLine(
                grn_id=grn.id,
                po_line_id=pl.id,
                item_id=pl.item_id,
                quantity_received=qty_rec,
            )
            session.add(grn_line)
            await session.flush()
            if pl.item_id and qty_rec > 0:
                if pl.item_id not in stock_by_item:
                    st = Stock(
                        item_id=pl.item_id,
                        quantity_on_hand=0,
                        quantity_reserved=0,
                        average_cost=Decimal("0.00"),
                    )
                    session.add(st)
                    await session.flush()
                    stock_by_item[pl.item_id] = st
                st = stock_by_item[pl.item_id]
                cost = pl.unit_price
                q_before = st.quantity_on_hand
                avg_before = st.average_cost
                total_before = q_before * avg_before
                total_after = total_before + cost * qty_rec
                q_after = q_before + qty_rec
                avg_after = (total_after / q_after) if q_after else Decimal("0.00")
                st.quantity_on_hand = q_after
                st.average_cost = round_money(avg_after)
                session.add(StockMovement(
                    stock_id=st.id,
                    item_id=pl.item_id,
                    movement_type=MovementType.RECEIPT.value,
                    quantity=qty_rec,
                    unit_cost=cost,
                    quantity_before=q_before,
                    quantity_after=q_after,
                    average_cost_before=avg_before,
                    average_cost_after=st.average_cost,
                    reference_type="goods_received_note",
                    reference_id=grn.id,
                    notes=f"GRN {grn.grn_number}",
                    created_by_id=user_id,
                ))
        po.received_value = received_value
        po.debt_amount = po.expected_total - received_value
        await session.flush()

    # Платежи по закупкам: 35+ (часть по PO, часть Other; 5 с employee_paid_id)
    all_po_ids = [t[0].id for t in po_list]
    po_ids_with_po = [pid for pid in all_po_ids]
    payments_for_claims: list[ProcurementPayment] = []
    for j in range(38):
        is_employee = j in (0, 8, 16, 24, 32)
        if is_employee:
            payee_name = "Security Guard" if j % 2 == 0 else "Jane Teacher"
            po_for_emp = None
            purpose_id = purpose_other
            amt = Decimal("2500.00") + Decimal((j * 100) % 2000)
        else:
            if not po_ids_with_po:
                continue
            po_id = po_ids_with_po[j % len(po_ids_with_po)]
            po_row = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))).scalar_one()
            po_for_emp = po_id
            purpose_id = po_row.purpose_id
            amt = min(po_row.debt_amount, Decimal("50000.00") + Decimal((j * 1000) % 30000))
            if amt <= 0:
                continue
            payee_name = po_row.supplier_name
        pay_d = date(CURRENT_YEAR, 1, 15) + timedelta(days=j % 45)
        ppay_number = await num_gen.generate("PPAY", pay_d.year)
        ppay = ProcurementPayment(
            payment_number=ppay_number,
            po_id=po_for_emp,
            purpose_id=purpose_id,
            payee_name=payee_name,
            payment_date=pay_d,
            amount=amt,
            payment_method=ProcurementPaymentMethod.MPESA.value if j % 3 != 0 else ProcurementPaymentMethod.BANK.value,
            company_paid=not is_employee,
            employee_paid_id=employee_user_id if is_employee else None,
            status=ProcurementPaymentStatus.POSTED.value,
            created_by_id=user_id,
        )
        session.add(ppay)
        await session.flush()
        if is_employee:
            payments_for_claims.append(ppay)
        else:
            po_row.paid_total += amt
            po_row.debt_amount -= amt
        await session.flush()

    # Expense claims и payouts по employee payments
    claim_ids_and_amounts: list[tuple[int, Decimal]] = []
    for ppay in payments_for_claims:
        claim_number = await num_gen.generate("CLM", ppay.payment_date.year)
        claim = ExpenseClaim(
            claim_number=claim_number,
            payment_id=ppay.id,
            employee_id=ppay.employee_paid_id,
            purpose_id=ppay.purpose_id,
            amount=ppay.amount,
            description=f"Reimbursement {ppay.payment_number}",
            expense_date=ppay.payment_date,
            status=ExpenseClaimStatus.APPROVED.value,
            paid_amount=Decimal("0.00"),
            remaining_amount=ppay.amount,
            auto_created_from_payment=True,
            related_procurement_payment_id=ppay.id,
        )
        session.add(claim)
        await session.flush()
        claim_ids_and_amounts.append((claim.id, claim.amount))

    total_approved = sum(a for _, a in claim_ids_and_amounts)
    paid_so_far = Decimal("0.00")
    for idx, (claim_id, amount) in enumerate(claim_ids_and_amounts):
        payout_number = await num_gen.generate("PAY", date(CURRENT_YEAR, 2, 1).year)
        payout = CompensationPayout(
            payout_number=payout_number,
            employee_id=employee_user_id,
            payout_date=date(CURRENT_YEAR, 2, 1) + timedelta(days=idx * 3),
            amount=amount,
            payment_method=PayoutMethod.CASH.value,
        )
        session.add(payout)
        await session.flush()
        session.add(PayoutAllocation(payout_id=payout.id, claim_id=claim_id, allocated_amount=amount))
        claim_row = (await session.execute(select(ExpenseClaim).where(ExpenseClaim.id == claim_id))).scalar_one()
        claim_row.paid_amount = amount
        claim_row.remaining_amount = Decimal("0.00")
        claim_row.status = ExpenseClaimStatus.PAID.value
        paid_so_far += amount
        await session.flush()

    eb = EmployeeBalance(
        employee_id=employee_user_id,
        total_approved=total_approved,
        total_paid=paid_so_far,
        balance=Decimal("0.00"),
    )
    session.add(eb)
    await session.flush()

    print(f"  Created 48 POs, {grn_count} GRNs, 38 procurement payments, {len(payments_for_claims)} claims/payouts, stock for {len(stock_by_item)} items.")


async def seed_inventory_categories_and_items(session: AsyncSession) -> dict[str, int]:
    """Создаёт категории склада и сотни товаров (форма, канцтовары, уборка, спорт, питание). Возвращает sku -> item_id."""
    result = await session.execute(select(Item).limit(1))
    if result.scalar_one_or_none():
        print("  Inventory items already exist, loading sku -> id.")
        r = await session.execute(select(Item.sku_code, Item.id))
        return {row[0]: row[1] for row in r.all()}

    category_ids: dict[str, int] = {}
    for cat_name in ITEMS_BY_CATEGORY:
        c = Category(name=cat_name, is_active=True)
        session.add(c)
        await session.flush()
        category_ids[cat_name] = c.id

    item_id_by_sku: dict[str, int] = {}
    for cat_name, items_list in ITEMS_BY_CATEGORY.items():
        cat_id = category_ids[cat_name]
        for sku, name, price_kes in items_list:
            it = Item(
                category_id=cat_id,
                sku_code=sku,
                name=name,
                item_type=ItemType.PRODUCT.value,
                price_type="standard",
                price=Decimal(str(price_kes)),
                requires_full_payment=True,
                is_active=True,
            )
            session.add(it)
            await session.flush()
            item_id_by_sku[sku] = it.id
    total = sum(len(v) for v in ITEMS_BY_CATEGORY.values())
    print(f"  Created {len(ITEMS_BY_CATEGORY)} categories and {total} items.")
    return item_id_by_sku


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
    item_id_by_sku = await seed_inventory_categories_and_items(session)
    await seed_procurement(session, num_gen, purpose_ids, user_id, employee_user_id or user_id, item_id_by_sku)

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
