# School ERP

ERP-система для частной школы в Кении. Управление биллингом студентов, складом, закупками и компенсациями сотрудникам.

## Технологии

**Backend:**
- Python 3.11+
- FastAPI
- SQLAlchemy (async) + asyncpg
- PostgreSQL 16
- Alembic (миграции)
- JWT аутентификация

**Frontend:**
- React 18 + TypeScript
- Vite
- MUI (Material UI)
- React Router

## Быстрый старт

### 1. Клонирование и настройка окружения

```bash
# Клонировать репозиторий
git clone <repo-url>
cd claude_duma_erp

# Создать .env файл
cp .env.example .env
```

### 2. Запуск базы данных

```bash
docker-compose up -d
```

### 3. Backend

```bash
# Установить uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Создать виртуальное окружение и установить зависимости
uv sync

# Применить миграции
uv run alembic upgrade head

# Запустить сервер
uv run uvicorn src.main:app --reload
```

Backend доступен на http://localhost:8000

**API документация:** http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev-сервер
npm run dev
```

Frontend доступен на http://localhost:5173

### 5. Вход в систему

```
Email: admin@school.com
Password: Admin123!
```

## Структура проекта

```
claude_duma_erp/
├── src/                    # Backend код
│   ├── core/               # Ядро (auth, database, utils)
│   │   ├── auth/           # JWT, роли, middleware
│   │   ├── database/       # SQLAlchemy настройка
│   │   └── utils/          # round_money, doc_numbers, exceptions
│   └── modules/            # Бизнес-модули
│       ├── users/          # Пользователи
│       ├── terms/          # Триместры и цены
│       ├── items/          # Складские позиции (Items) и каталог продаж (Kits)
│       ├── students/       # Студенты и классы
│       ├── invoices/       # Счета
│       ├── discounts/      # Скидки
│       ├── payments/       # Платежи и аллокации
│       ├── inventory/      # Склад
│       ├── reservations/   # Резервирования
│       ├── procurement/    # Закупки (PO, GRN, платежи)
│       └── compensations/  # Компенсации сотрудникам
├── tests/                  # Тесты
├── alembic/                # Миграции БД
├── frontend/               # React приложение
│   └── src/
│       └── app/
│           ├── auth/       # Аутентификация
│           ├── layout/     # Sidebar, TopBar
│           ├── pages/      # Страницы
│           └── services/   # API клиент
└── docs (в корне)          # Документация (*.md файлы)
```

## Каталог и счета (важно)

- **Items** — складские позиции (inventory).
- **Kits** — товары для продажи (catalog). Все продажи идут через `kit_id`.
- **InvoiceLine** больше не ссылается на `item_id`.
- `sku_code` для Kit можно не передавать — генерируется автоматически.

## Документация

| Файл | Описание |
|------|----------|
| `TASKS.md` | Задачи и прогресс разработки |
| `erp_spec.md` | Полная спецификация системы (на русском) |
| `BACKEND_API.md` | Документация всех API endpoints |
| `BACKEND_OVERVIEW.md` | Обзор архитектуры и бизнес-процессов |
| `CLAUDE.md` | Инструкции для Claude Code (AI-ассистент) |

## Работа с TASKS.md

`TASKS.md` — главный файл отслеживания прогресса проекта.

> **Важно:** Решения в `TASKS.md` (блоки `> Решения:`) имеют приоритет над оригинальным ТЗ (`erp_spec.md`). В процессе разработки многие требования были уточнены или изменены — актуальная версия всегда в TASKS.md.

### Структура

- **Фазы** (0-11) — логические блоки функциональности
- **Секции** внутри фаз — отдельные модули/функции
- **Чекбоксы** — конкретные задачи

### Статусы задач

```
[ ] — не начато
[~] — в работе
[x] — готово
```

### Маркеры

- `[ОБСУДИТЬ]` — требует обсуждения перед реализацией
- `> Решения:` — блок с принятыми решениями (для справки)

### Правила ведения

1. **Перед началом работы** — найти задачу, поменять `[ ]` на `[~]`
2. **После завершения** — поменять `[~]` на `[x]`
3. **При обсуждении** — добавить `> Решения:` блок с итогами
4. **Новые задачи** — добавлять в соответствующую фазу/секцию
5. **Не удалять** завершённые задачи — они служат документацией

### Текущий статус

- Фазы 0-7: Backend готов (160 тестов)
- Фаза 9: UI частично готов (Students, Inventory, Settings)
- Фаза 10.2: PDF счёта и квитанции готовы (GET /invoices/{id}/pdf, GET /payments/{id}/receipt/pdf)
- Фазы 8, 11: Не начаты (Отчёты, CRM)

## Команды

### Backend

```bash
# Запуск сервера
uv run uvicorn src.main:app --reload

# Тесты
uv run pytest

# Тесты с покрытием
uv run pytest --cov=src

# Линтер
uv run ruff check src tests

# Форматирование
uv run ruff format src tests

# Новая миграция
uv run alembic revision --autogenerate -m "description"

# Применить миграции
uv run alembic upgrade head

# Откатить миграцию
uv run alembic downgrade -1
```

**PDF (счета и квитанции):** Генерация через WeasyPrint. Python-зависимости (weasyprint, jinja2, num2words) ставятся через `uv sync`. На macOS дополнительно нужны системные библиотеки: `brew install pango glib`. После установки при запуске бэкенда задайте путь к ним, иначе WeasyPrint не найдёт библиотеки:
```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/glib/lib:/opt/homebrew/opt/pango/lib:/opt/homebrew/lib
uv run uvicorn src.main:app --reload
```
В Docker и на Linux зависимости уже добавлены в Dockerfile. Тесты PDF работают без WeasyPrint (мок).

### Frontend

```bash
cd frontend

# Dev сервер
npm run dev

# Сборка
npm run build

# Линтер
npm run lint

# Type check
npm run type-check
```

## Роли пользователей

| Роль | Возможности |
|------|-------------|
| SuperAdmin | Всё: управление пользователями, термами, одобрение claims, отмена платежей |
| Admin | CRUD студентов/счетов/PO, одобрение GRN, выдача со склада |
| User | Создание своих claims/requests, просмотр своих данных |
| Accountant | Read-only доступ ко всем данным и отчётам |

## Переменные окружения

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/school_erp

# JWT
JWT_SECRET_KEY=your-secret-key      # Обязательно сменить в production!
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# App
APP_ENV=development                  # development | production
DEBUG=true
```

## API

Все endpoints возвращают единый формат:

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message"
}
```

Списки используют пагинацию:

```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "limit": 20
  }
}
```

Полная документация API: `BACKEND_API.md` или http://localhost:8000/docs

## Деплой

См. [DEPLOY.md](DEPLOY.md) для инструкций по деплою на Railway.

**Быстрый старт Railway:**
1. Push код на GitHub
2. Создать проект на Railway из GitHub repo
3. Добавить PostgreSQL database
4. Установить переменные окружения (`JWT_SECRET_KEY`, `APP_ENV=production`)
5. Deploy автоматически запустится

## Лицензия

Проприетарный код. Все права защищены.
