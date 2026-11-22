from sqlalchemy import text, event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .models import metadata, engagements, olostep_cache, credit_ledger, findings, approval_gates, audit_logs


def normalize_database_url(value):
    url = make_url(value)
    options = {"pool_pre_ping": True, "pool_recycle": 300}
    if url.drivername in {"postgres", "postgresql", "postgresql+asyncpg"}:
        url = url.set(drivername="postgresql+asyncpg").difference_update_query(["sslmode", "channel_binding"])
        options.update(pool_size=5, max_overflow=5)
        if url.host not in {None, "localhost", "127.0.0.1", "::1"}:
            options["connect_args"] = {"ssl": True}
    elif url.drivername in {"sqlite", "sqlite+aiosqlite"}:
        url = url.set(drivername="sqlite+aiosqlite")
    else:
        raise ValueError("Only SQLite and PostgreSQL are supported")
    return url, options


def build_engine(settings):
    url, options = normalize_database_url(settings.database_url)
    if (settings.render or settings.app_env == "production") and url.get_backend_name() != "postgresql":
        raise ValueError("Production requires PostgreSQL DATABASE_URL")
    engine = create_async_engine(url, hide_parameters=True, **options)
    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
    return engine


async def migrate(engine):
    # Append numbered migrations here; create_all does not alter existing tables.
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            await conn.exec_driver_sql("BEGIN IMMEDIATE")
        if engine.dialect.name == "postgresql":
            await conn.execute(text("SELECT pg_advisory_xact_lock(7281942)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"))
        versions = set((await conn.execute(text("SELECT version FROM schema_migrations"))).scalars())
        if 1 not in versions:
            await conn.run_sync(metadata.create_all)
            await conn.execute(text("INSERT INTO schema_migrations (version) VALUES (1)"))
        if 2 not in versions:
            from sqlalchemy import inspect
            columns = await conn.run_sync(lambda c: {x['name'] for x in inspect(c).get_columns('audit_logs')})
            if "issuer" not in columns:
                await conn.execute(text("ALTER TABLE audit_logs ADD COLUMN issuer VARCHAR NOT NULL DEFAULT 'Kalki LLP'"))
            await conn.execute(text("INSERT INTO schema_migrations (version) VALUES (2)"))

        if 3 not in versions:
            from .migrations import phase_one
            await phase_one(conn)
            await conn.execute(text("INSERT INTO schema_migrations (version) VALUES (3)"))


def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)
