from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

_settings = get_settings()

# NullPool (the default, db_pool_size=0) opens a fresh connection per session. That's required
# behind Supabase's transaction pooler, and for the Celery worker, which runs each task in a new
# asyncio.run() loop that a pooled asyncpg connection can't survive. A single-loop API process
# on a direct connection can pool instead, which skips the TLS + auth handshake (several round
# trips to a far-away database) on every request.
_pool_args = (
    {"pool_size": _settings.db_pool_size, "max_overflow": _settings.db_pool_size, "pool_recycle": 300}
    if _settings.db_pool_size > 0
    else {"poolclass": NullPool}
)

engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    },
    **_pool_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:

    async with SessionLocal() as session:

        yield session