#!/usr/bin/env python3
"""
Скрипт для удаления всех платежей (payments) студентов с продакшена.
Инвойсы (invoices) сохраняются, но возвращаются в статус неоплаченных.
Балансы студентов обнуляются.

ВНИМАНИЕ: Этот скрипт удаляет данные! Используйте с осторожностью.
Рекомендуется сделать backup базы данных перед запуском.

Использование:
    python scripts/reset_payments.py --dry-run  # Просмотр без изменений
    python scripts/reset_payments.py --confirm  # Реальное выполнение
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from src.core.database.session import async_session
from src.core.config import settings
from src.modules.payments.models import Payment, CreditAllocation
from src.modules.students.models import Student
from src.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from src.modules.reservations.models import Reservation, ReservationItem


async def count_records(session: AsyncSession) -> dict:
    """Подсчитывает количество записей в каждой таблице."""
    counts = {}

    # Payments
    result = await session.execute(select(func.count()).select_from(Payment))
    counts['payments'] = result.scalar_one()

    # CreditAllocations
    result = await session.execute(select(func.count()).select_from(CreditAllocation))
    counts['credit_allocations'] = result.scalar_one()

    # Reservations
    result = await session.execute(select(func.count()).select_from(Reservation))
    counts['reservations'] = result.scalar_one()

    # ReservationItems
    result = await session.execute(select(func.count()).select_from(ReservationItem))
    counts['reservation_items'] = result.scalar_one()

    # Students with non-zero balance
    result = await session.execute(
        select(func.count()).select_from(Student).where(Student.cached_credit_balance != 0)
    )
    counts['students_with_balance'] = result.scalar_one()

    # Paid/PartiallyPaid invoices
    result = await session.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.status.in_([InvoiceStatus.PAID.value, InvoiceStatus.PARTIALLY_PAID.value])
        )
    )
    counts['paid_invoices'] = result.scalar_one()

    return counts


async def delete_all_payments(session: AsyncSession, dry_run: bool = True) -> dict:
    """
    Удаляет все payments и связанные записи.

    Порядок удаления:
    1. ReservationItems (cascade от Reservations)
    2. Reservations (связаны с оплаченными invoice_lines)
    3. CreditAllocations (распределение кредита на инвойсы)
    4. Payments (платежи студентов)
    5. Обнуление балансов студентов (Student.cached_credit_balance)
    6. Пересчет инвойсов (paid_total=0, amount_due=total, status=ISSUED)
    7. Пересчет строк инвойсов (paid_amount=0, remaining_amount=net_amount)

    Invoices НЕ удаляются!
    """
    print("\n" + "="*70)
    print("УДАЛЕНИЕ ПЛАТЕЖЕЙ (PAYMENTS)")
    print("="*70)

    # Подсчитываем что есть сейчас
    print("\n📊 Текущее состояние базы данных:")
    counts_before = await count_records(session)
    for table, count in counts_before.items():
        print(f"  - {table}: {count} записей")

    if all(count == 0 for count in counts_before.values()):
        print("\n✅ База данных уже чистая, нечего удалять.")
        return counts_before

    if dry_run:
        print("\n🔍 РЕЖИМ DRY-RUN: изменения НЕ будут применены")
        print("\nБудет удалено:")
        for table, count in counts_before.items():
            if count > 0:
                print(f"  ❌ {table}: {count} записей")
        print("\nБудет обновлено:")
        print(f"  🔄 Все инвойсы: пересчет балансов и статусов")
        print(f"  🔄 Все студенты: обнуление балансов")
        print("\n💡 Для реального выполнения используйте: --confirm")
        return counts_before

    print("\n⚠️  ВНИМАНИЕ: Начинается удаление данных...")
    print("⏳ Это может занять некоторое время...\n")

    try:
        # 1. Удаляем Reservations (ReservationItems удалятся автоматически по cascade)
        print("1️⃣  Удаление Reservations...")
        result = await session.execute(delete(Reservation))
        deleted_reservations = result.rowcount
        print(f"   ✓ Удалено: {deleted_reservations} reservations")

        # 2. Удаляем CreditAllocations
        print("\n2️⃣  Удаление CreditAllocations...")
        result = await session.execute(delete(CreditAllocation))
        deleted_allocations = result.rowcount
        print(f"   ✓ Удалено: {deleted_allocations} credit allocations")

        # 3. Удаляем Payments
        print("\n3️⃣  Удаление Payments...")
        result = await session.execute(delete(Payment))
        deleted_payments = result.rowcount
        print(f"   ✓ Удалено: {deleted_payments} payments")

        # 4. Обнуляем балансы всех студентов
        print("\n4️⃣  Обнуление балансов студентов...")
        result = await session.execute(
            update(Student)
            .where(Student.cached_credit_balance != 0)
            .values(cached_credit_balance=Decimal("0.00"))
        )
        updated_students = result.rowcount
        print(f"   ✓ Обновлено: {updated_students} студентов")

        # 5. Пересчитываем инвойсы (возвращаем в статус неоплаченных)
        print("\n5️⃣  Пересчет инвойсов...")
        # Получаем все инвойсы, которые были оплачены или частично оплачены
        result = await session.execute(
            select(Invoice).where(
                Invoice.status.in_([
                    InvoiceStatus.PAID.value,
                    InvoiceStatus.PARTIALLY_PAID.value
                ])
            )
        )
        invoices_to_reset = list(result.scalars().all())

        for invoice in invoices_to_reset:
            invoice.paid_total = Decimal("0.00")
            invoice.amount_due = invoice.total
            invoice.status = InvoiceStatus.ISSUED.value

        print(f"   ✓ Обновлено: {len(invoices_to_reset)} инвойсов")

        # 6. Пересчитываем строки инвойсов
        print("\n6️⃣  Пересчет строк инвойсов...")
        result = await session.execute(
            update(InvoiceLine)
            .where(InvoiceLine.paid_amount != 0)
            .values(
                paid_amount=Decimal("0.00"),
                remaining_amount=InvoiceLine.net_amount
            )
        )
        updated_lines = result.rowcount
        print(f"   ✓ Обновлено: {updated_lines} строк инвойсов")

        # Коммитим транзакцию
        await session.commit()

        print("\n" + "="*70)
        print("✅ УСПЕШНО УДАЛЕНО")
        print("="*70)

        # Проверяем результат
        counts_after = await count_records(session)
        print("\n📊 Итоговое состояние базы данных:")
        for table, count in counts_after.items():
            print(f"  - {table}: {count} записей")

        if all(count == 0 for count in counts_after.values()):
            print("\n🎉 Все платежи успешно удалены!")
            print("💰 Балансы студентов обнулены")
            print("📄 Инвойсы сохранены и возвращены в статус неоплаченных")
        else:
            print("\n⚠️  Внимание: остались некоторые записи")

        return counts_after

    except Exception as e:
        print(f"\n❌ ОШИБКА при удалении: {e}")
        await session.rollback()
        print("🔄 Транзакция откачена (rollback)")
        raise


async def main():
    """Главная функция."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Удаление всех payments с сохранением invoices"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Режим просмотра без реальных изменений'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Подтверждение реального выполнения (БЕЗ dry-run)'
    )

    args = parser.parse_args()

    # Проверка параметров
    if not args.dry_run and not args.confirm:
        print("❌ ОШИБКА: Необходимо указать --dry-run или --confirm")
        print("\nИспользование:")
        print("  --dry-run   : Просмотр без изменений")
        print("  --confirm   : Реальное выполнение")
        sys.exit(1)

    dry_run = args.dry_run

    # Показываем информацию о подключении
    print("\n" + "="*70)
    print("СКРИПТ УДАЛЕНИЯ ПЛАТЕЖЕЙ (RESET PAYMENTS)")
    print("="*70)
    print(f"\n🌍 Окружение: {settings.app_env}")
    print(f"🗄️  База данных: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'unknown'}")
    print(f"🔧 Режим: {'DRY-RUN (просмотр)' if dry_run else 'РЕАЛЬНОЕ ВЫПОЛНЕНИЕ'}")

    # Финальное подтверждение для production
    if not dry_run:
        print("\n⚠️  ⚠️  ⚠️  ВНИМАНИЕ! ⚠️  ⚠️  ⚠️")
        print("Вы собираетесь УДАЛИТЬ ВСЕ ПЛАТЕЖИ из базы данных!")
        print("Это действие НЕОБРАТИМО!")
        print("\n💡 Рекомендуется сделать backup базы данных перед продолжением.")
        print("\nЧто будет удалено:")
        print("  ❌ Все Payments (во всех статусах)")
        print("  ❌ Все CreditAllocations")
        print("  ❌ Все Reservations и ReservationItems")
        print("\nЧто будет обновлено:")
        print("  🔄 Все студенты: cached_credit_balance = 0")
        print("  🔄 Все оплаченные инвойсы: paid_total = 0, amount_due = total, status = ISSUED")
        print("  🔄 Все строки инвойсов: paid_amount = 0, remaining_amount = net_amount")
        print("\nЧто НЕ будет удалено:")
        print("  ✅ Invoices и InvoiceLines (останутся в статусе ISSUED)")
        print("  ✅ Students, Users, Terms и другие данные")
        print("  ✅ AuditLogs (история операций)")

        response = input("\n❓ Введите 'DELETE ALL PAYMENTS' для продолжения: ")
        if response != 'DELETE ALL PAYMENTS':
            print("\n❌ Отменено пользователем")
            sys.exit(0)

    # Выполняем удаление
    async with async_session() as session:
        try:
            await delete_all_payments(session, dry_run=dry_run)
            print("\n✅ Скрипт завершен успешно")
        except Exception as e:
            print(f"\n❌ Скрипт завершился с ошибкой: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
