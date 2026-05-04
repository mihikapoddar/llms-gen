from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from llms_gen.config import get_settings
from llms_gen.models.db import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _sqlite_migrate_sync(connection) -> None:
    """Add columns SQLite forgot when the DB was created before a model change."""
    insp = inspect(connection)
    tables = insp.get_table_names()
    if "jobs" in tables:
        cols = {c["name"] for c in insp.get_columns("jobs")}
        if "monitored_site_id" not in cols:
            connection.execute(
                text("ALTER TABLE jobs ADD COLUMN monitored_site_id VARCHAR(36)")
            )
    if "monitored_sites" in tables:
        mcols = {c["name"] for c in insp.get_columns("monitored_sites")}
        if "webhook_url" not in mcols:
            connection.execute(
                text("ALTER TABLE monitored_sites ADD COLUMN webhook_url VARCHAR(2048)")
            )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.database_url:
            await conn.run_sync(_sqlite_migrate_sync)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
