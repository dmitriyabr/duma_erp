#!/usr/bin/env python3
"""
Скрипт для удаления всех счетов (invoices) с продакшена.
Платежи (payments) сохраняются и становятся балансом студентов.

ВНИМАНИЕ: Этот скрипт удаляет данные! Используйте с осторожностью.
Рекомендуется сделать backup базы данных перед запуском.

Использование:
    python scripts/reset_invoices.py --dry-run  # Просмотр без изменений
    python scripts/reset_invoices.py --confirm  # Реальное выполнение
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.session import async_session
from src.core.config import settings
from src.modules.invoices.models import Invoice, InvoiceLine
from src.modules.payments.models import CreditAllocation
from src.modules.reservations.models import Reservation, ReservationItem


async def count_records(session: AsyncSession) -> dict:
    """Подсчитывает количество записей в каждой таблице."""
    counts = {}

    # Invoices
    result = await session.execute(select(func.count()).select_from(Invoice))
    counts['invoices'] = result.scalar_one()

    # InvoiceLines
    result = await session.execute(select(func.count()).select_from(InvoiceLine))
    counts['invoice_lines'] = result.scalar_one()

    # CreditAllocations
    result = await session.execute(select(func.count()).select_from(CreditAllocation))
    counts['credit_allocations'] = result.scalar_one()

    # Reservations
    result = await session.execute(select(func.count()).select_from(Reservation))
    counts['reservations'] = result.scalar_one()

    # ReservationItems
    result = await session.execute(select(func.count()).select_from(ReservationItem))
    counts['reservation_items'] = result.scalar_one()

    return counts


async def delete_all_invoices(session: AsyncSession, dry_run: bool = True) -> dict:
    """
    Удаляет все invoices и связанные записи.

    Порядок удаления:
    1. ReservationItems (cascade от Reservations)
    2. Reservations
    3. CreditAllocations
    4. InvoiceLines (cascade от Invoices)
    5. Invoices

    Payments НЕ удаляются!
    """
    print("\n" + "="*70)
    print("УДАЛЕНИЕ СЧЕТОВ (INVOICES)")
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

        # 3. Удаляем Invoices (InvoiceLines удалятся автоматически по cascade)
        print("\n3️⃣  Удаление Invoices...")
        result = await session.execute(delete(Invoice))
        deleted_invoices = result.rowcount
        print(f"   ✓ Удалено: {deleted_invoices} invoices")

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
            print("\n🎉 Все счета успешно удалены!")
            print("💰 Все payments сохранены и теперь являются балансом студентов")
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
        description="Удаление всех invoices с сохранением payments"
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
    print("СКРИПТ УДАЛЕНИЯ СЧЕТОВ (RESET INVOICES)")
    print("="*70)
    print(f"\n🌍 Окружение: {settings.app_env}")
    print(f"🗄️  База данных: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'unknown'}")
    print(f"🔧 Режим: {'DRY-RUN (просмотр)' if dry_run else 'РЕАЛЬНОЕ ВЫПОЛНЕНИЕ'}")

    # Финальное подтверждение для production
    if not dry_run:
        print("\n⚠️  ⚠️  ⚠️  ВНИМАНИЕ! ⚠️  ⚠️  ⚠️")
        print("Вы собираетесь УДАЛИТЬ ВСЕ СЧЕТА из базы данных!")
        print("Это действие НЕОБРАТИМО!")
        print("\n💡 Рекомендуется сделать backup базы данных перед продолжением.")
        print("\nЧто будет удалено:")
        print("  ❌ Все Invoices и InvoiceLines")
        print("  ❌ Все Reservations и ReservationItems")
        print("  ❌ Все CreditAllocations")
        print("\nЧто НЕ будет удалено:")
        print("  ✅ Payments (останутся как баланс студентов)")
        print("  ✅ Students, Users, Terms и другие данные")
        print("  ✅ AuditLogs (история операций)")

        response = input("\n❓ Введите 'DELETE ALL INVOICES' для продолжения: ")
        if response != 'DELETE ALL INVOICES':
            print("\n❌ Отменено пользователем")
            sys.exit(0)

    # Выполняем удаление
    async with async_session() as session:
        try:
            await delete_all_invoices(session, dry_run=dry_run)
            print("\n✅ Скрипт завершен успешно")
        except Exception as e:
            print(f"\n❌ Скрипт завершился с ошибкой: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
