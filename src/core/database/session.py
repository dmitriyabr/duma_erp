from collections.abc import AsyncGenerator
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# Debug: print database URL (without password) on startup
try:
    if settings.database_url:
        # Hide password in logs
        url_for_log = settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url[:30]
        print(f"[Database] Connecting to: ...@{url_for_log}", file=sys.stderr)
    else:
        print("[Database] ERROR: DATABASE_URL is empty!", file=sys.stderr)
        raise ValueError("DATABASE_URL environment variable is not set")
except Exception as e:
    print(f"[Database] ERROR: {e}", file=sys.stderr)
    raise

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
