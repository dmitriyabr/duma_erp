#!/bin/bash
# Wrapper для запуска reset_invoices.py на Railway с проверками

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "  RAILWAY: Скрипт удаления счетов (Reset Invoices)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Проверка Railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ ОШИБКА: Railway CLI не установлен"
    echo ""
    echo "Установи Railway CLI:"
    echo "  npm install -g @railway/cli"
    echo "  или"
    echo "  brew install railway"
    exit 1
fi

# Проверка что проект подключен
if ! railway status &> /dev/null; then
    echo "❌ ОШИБКА: Проект не подключен к Railway"
    echo ""
    echo "Выполни: railway link"
    exit 1
fi

echo "✅ Railway CLI найден"
echo "✅ Проект подключен"
echo ""

# Показываем текущий проект
echo "📦 Текущий проект:"
railway status
echo ""

# Предупреждение о backup
echo "⚠️  ⚠️  ⚠️  ВАЖНО! ⚠️  ⚠️  ⚠️"
echo ""
echo "Перед продолжением убедись, что:"
echo "  1. ✅ Создан backup в Railway Dashboard"
echo "     (Database → Backups → Create Backup)"
echo "  2. ✅ Backup успешно завершен"
echo ""
read -p "❓ Backup создан? (yes/no): " backup_confirm

if [ "$backup_confirm" != "yes" ]; then
    echo ""
    echo "❌ Отменено. Создай backup и запусти скрипт снова."
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 1: DRY-RUN (просмотр без изменений)"
echo "════════════════════════════════════════════════════════════════"
echo ""

railway run python scripts/reset_invoices.py --dry-run

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 2: Подтверждение выполнения"
echo "════════════════════════════════════════════════════════════════"
echo ""
read -p "❓ Продолжить с реальным удалением? (yes/no): " exec_confirm

if [ "$exec_confirm" != "yes" ]; then
    echo ""
    echo "❌ Отменено пользователем"
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 3: РЕАЛЬНОЕ ВЫПОЛНЕНИЕ"
echo "════════════════════════════════════════════════════════════════"
echo ""

railway run python scripts/reset_invoices.py --confirm

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ ГОТОВО!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Что произошло:"
echo "  ✅ Все invoices удалены"
echo "  ✅ Все payments сохранены (на балансе студентов)"
echo ""
echo "Если нужно откатить изменения:"
echo "  1. Зайди в Railway Dashboard → Database → Backups"
echo "  2. Найди backup созданный до запуска"
echo "  3. Нажми Restore"
echo ""
