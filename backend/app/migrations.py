"""Numbered migration 003: additive Phase 1 schema and lossless ledger upgrade."""
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn
from .models import metadata


async def phase_one(conn):
    def columns(sync, table):
        return {column["name"] for column in inspect(sync).get_columns(table)}

    ledger_columns = await conn.run_sync(columns, "credit_ledger")
    legacy_ledger = "id" not in ledger_columns
    if legacy_ledger:
        await conn.execute(text("ALTER TABLE credit_ledger RENAME TO legacy_credit_balances"))
    cache_columns = await conn.run_sync(columns, "olostep_cache")
    if "key" in cache_columns:
        await conn.execute(text('ALTER TABLE olostep_cache RENAME COLUMN "key" TO cache_key_sha256'))

    # Existing columns and rows are never dropped or rewritten by create_all.
    await conn.run_sync(metadata.create_all)
    for table in metadata.sorted_tables:
        existing = await conn.run_sync(columns, table.name)
        for column in table.columns:
            if column.name not in existing:
                ddl = str(CreateColumn(column).compile(dialect=conn.dialect))
                await conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_engagement_code ON engagements (code)"))
    await conn.execute(text("UPDATE olostep_cache SET response_json=response, request_url=source_url, created_at=retrieved_at WHERE response_json IS NULL"))
    if legacy_ledger:
        await conn.execute(text("UPDATE engagements SET credits_used=COALESCE((SELECT credits FROM legacy_credit_balances WHERE engagement_id=engagements.id),0)"))
        await conn.execute(text("""INSERT INTO credit_ledger
            (id, engagement_id, endpoint, credits_consumed, cache_hit, mode, outcome, created_at)
            SELECT 'legacy-' || engagement_id, engagement_id, 'legacy', credits, false,
                   'legacy', 'migrated', '1970-01-01T00:00:00+00:00'
            FROM legacy_credit_balances"""))
