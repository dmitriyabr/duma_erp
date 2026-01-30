#!/bin/bash
# Запуск скрипта локально с подключением к Railway БД

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  Запуск локально с подключением к Railway БД"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Проверка Railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ ОШИБКА: Railway CLI не установлен"
    exit 1
fi

# Получаем DATABASE_URL из Railway
echo "🔗 Получаем DATABASE_URL из Railway..."
echo ""
echo "Выполняем: railway run env | grep DATABASE_URL"
echo "Скопируй DATABASE_URL и вставь ниже когда попросит"
echo ""

railway run env | grep DATABASE_URL

echo ""
read -p "❓ Введи DATABASE_URL (или нажми Ctrl+C для отмены): " DATABASE_URL

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL не может быть пустым"
    exit 1
fi

export DATABASE_URL

echo "✅ DATABASE_URL получен"
echo ""

# Предупреждение о backup
echo "⚠️  ⚠️  ⚠️  ВАЖНО! ⚠️  ⚠️  ⚠️"
echo ""
echo "Создан backup в Railway Dashboard?"
echo "  (Database → Backups → Create Backup)"
echo ""
read -p "❓ Backup создан? (yes/no): " backup_confirm

if [ "$backup_confirm" != "yes" ]; then
    echo "❌ Отменено. Создай backup и запусти снова."
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 1: DRY-RUN (просмотр без изменений)"
echo "════════════════════════════════════════════════════════════════"
echo ""

python3.11 scripts/reset_invoices.py --dry-run

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 2: Подтверждение выполнения"
echo "════════════════════════════════════════════════════════════════"
echo ""
read -p "❓ Продолжить с реальным удалением? (yes/no): " exec_confirm

if [ "$exec_confirm" != "yes" ]; then
    echo "❌ Отменено"
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 3: РЕАЛЬНОЕ ВЫПОЛНЕНИЕ"
echo "════════════════════════════════════════════════════════════════"
echo ""

python3.11 scripts/reset_invoices.py --confirm

echo ""
echo "✅ ГОТОВО!"
