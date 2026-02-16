#!/bin/bash
# Wrapper для запуска backfill_reservation_issued_from_issuances.py на Railway

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "  RAILWAY: Backfill reservation issued quantities"
echo "════════════════════════════════════════════════════════════════"
echo ""

usage() {
  echo "Usage:"
  echo "  $0 --issuance-id <ID>"
  echo "  $0 --reservation-id <ID>"
  echo ""
  echo "What it does:"
  echo "  1) Runs DRY-RUN on Railway (no DB changes)"
  echo "  2) Asks confirmation"
  echo "  3) Runs APPLY (COMMIT) on Railway"
  echo ""
  echo "Notes:"
  echo "  - Script is idempotent: recomputes quantity_issued from COMPLETED issuances"
  echo "  - CANCELLED issuances are ignored for recomputation"
}

# Parse args (only allow safe, scoped runs by default)
ISSUANCE_ID=""
RESERVATION_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issuance-id)
      ISSUANCE_ID="$2"
      shift 2
      ;;
    --reservation-id)
      RESERVATION_ID="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $1"
      echo ""
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ISSUANCE_ID" && -z "$RESERVATION_ID" ]]; then
  echo "❌ ERROR: you must provide --issuance-id or --reservation-id"
  echo ""
  usage
  exit 1
fi

if [[ -n "$ISSUANCE_ID" && -n "$RESERVATION_ID" ]]; then
  echo "❌ ERROR: choose only one of --issuance-id / --reservation-id"
  echo ""
  usage
  exit 1
fi

FILTER_ARGS=""
if [[ -n "$ISSUANCE_ID" ]]; then
  FILTER_ARGS="--issuance-id $ISSUANCE_ID"
fi
if [[ -n "$RESERVATION_ID" ]]; then
  FILTER_ARGS="--reservation-id $RESERVATION_ID"
fi

# Check Railway CLI
if ! command -v railway &> /dev/null; then
  echo "❌ ОШИБКА: Railway CLI не установлен"
  echo ""
  echo "Установи Railway CLI:"
  echo "  npm install -g @railway/cli"
  echo "  или"
  echo "  brew install railway"
  exit 1
fi

# Check project link
if ! railway status &> /dev/null; then
  echo "❌ ОШИБКА: Проект не подключен к Railway"
  echo ""
  echo "Выполни: railway link"
  exit 1
fi

echo "✅ Railway CLI найден"
echo "✅ Проект подключен"
echo ""

echo "📦 Текущий проект:"
railway status
echo ""

echo "🎯 Filter: $FILTER_ARGS"
echo ""

# Backup warning
echo "⚠️  ⚠️  ⚠️  ВАЖНО! ⚠️  ⚠️  ⚠️"
echo ""
echo "Перед продолжением убедись, что:"
echo "  1. ✅ Создан backup в Railway Dashboard"
echo "     (Database → Backups → Create Backup)"
echo "  2. ✅ Backup успешно завершен"
echo ""
read -p "❓ Backup создан? (yes/no): " backup_confirm

if [[ "$backup_confirm" != "yes" ]]; then
  echo ""
  echo "❌ Отменено. Создай backup и запусти скрипт снова."
  exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 1: DRY-RUN (просмотр без изменений)"
echo "════════════════════════════════════════════════════════════════"
echo ""

railway run python3.11 scripts/backfill_reservation_issued_from_issuances.py --dry-run $FILTER_ARGS

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 2: Подтверждение выполнения"
echo "════════════════════════════════════════════════════════════════"
echo ""
read -p "❓ Применить изменения в БД? (yes/no): " exec_confirm

if [[ "$exec_confirm" != "yes" ]]; then
  echo ""
  echo "❌ Отменено пользователем"
  exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ШАГ 3: APPLY (COMMIT)"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "ℹ️  Внутри Python-скрипта будет дополнительное подтверждение фразой:"
echo "    APPLY RESERVATION BACKFILL"
echo ""

railway run python3.11 scripts/backfill_reservation_issued_from_issuances.py --confirm $FILTER_ARGS

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ ГОТОВО!"
echo "════════════════════════════════════════════════════════════════"
echo ""
