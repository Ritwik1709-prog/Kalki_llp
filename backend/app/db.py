from sqlalchemy import (MetaData, Table, Column, String, Integer, JSON, Text,
                        ForeignKey, CheckConstraint, text, event)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

metadata = MetaData()
engagements = Table("engagements", metadata,
    Column("id", String, primary_key=True), Column("status", String, nullable=False),
    Column("version", Integer, nullable=False, default=1), Column("data", JSON))
olostep_cache = Table("olostep_cache", metadata,
    Column("key", String(64), primary_key=True), Column("retrieved_at", String, nullable=False),
    Column("source_url", Text, nullable=False), Column("response", JSON, nullable=False))
credit_ledger = Table("credit_ledger", metadata,
    Column("engagement_id", String, ForeignKey("engagements.id"), primary_key=True),
    Column("credits", Integer, nullable=False, default=0),
    CheckConstraint("credits >= 0 AND credits <= 25"))
findings = Table("findings", metadata,
    Column("id", String, primary_key=True),
    Column("engagement_id", String, ForeignKey("engagements.id"), nullable=False),
    Column("severity", String, nullable=False), Column("citations", JSON, nullable=False),
    Column("data", JSON))
approval_gates = Table("approval_gates", metadata,
    Column("id", String, primary_key=True),
    Column("engagement_id", String, ForeignKey("engagements.id"), nullable=False),
    Column("status", String, nullable=False), Column("reviewer", String),
    Column("reviewed_version", Integer), Column("reviewed_at", String), Column("rationale", Text))
audit_logs = Table("audit_logs", metadata,
    Column("id", String, primary_key=True),
    Column("engagement_id", String, ForeignKey("engagements.id")),
    Column("created_at", String, nullable=False), Column("event", JSON, nullable=False),
    Column("issuer", String, nullable=False, server_default="Kalki LLP"))


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
    engine = create_async_engine(url, **options)
    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


async def migrate(engine):
    # Append numbered migrations here; create_all does not alter existing tables.
    async with engine.begin() as conn:
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
