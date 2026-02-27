import asyncio
from logging.config import fileConfig

# ruff: noqa: F401

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from src.core.config import settings
from src.core.database.base import Base

# Import all models here so they are registered with Base.metadata
from src.core.auth.models import User
from src.core.attachments.models import Attachment
from src.core.school_settings.models import SchoolSettings
from src.core.audit.models import AuditLog
from src.core.documents.models import DocumentSequence
from src.modules.terms.models import Term, PriceSetting, TransportZone, TransportPricing
from src.modules.items.models import Category, Item, ItemPriceHistory, Kit, KitItem, KitPriceHistory
from src.modules.inventory.models import Stock, StockMovement, Issuance, IssuanceItem
from src.modules.students.models import Grade, Student
from src.modules.invoices.models import Invoice, InvoiceLine
from src.modules.discounts.models import DiscountReason, Discount, StudentDiscount
from src.modules.payments.models import Payment, CreditAllocation
from src.modules.reservations.models import Reservation, ReservationItem
from src.modules.procurement.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceivedNote,
    GoodsReceivedLine,
    PaymentPurpose,
    ProcurementPayment,
)
from src.modules.compensations.models import (
    ExpenseClaim,
    CompensationPayout,
    PayoutAllocation,
    EmployeeBalance,
)
from src.integrations.mpesa.models import MpesaC2BEvent

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
