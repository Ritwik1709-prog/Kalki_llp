import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from app.config import Settings
from app.db import normalize_database_url, build_engine, migrate, metadata
from app.main import create_app
from app.streaming import heartbeat_stream, pdf_response, sse_response
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

@pytest.mark.parametrize("raw,driver,ssl", [
 ("sqlite+aiosqlite:///:memory:", "sqlite+aiosqlite", False),
 ("postgresql://user:pass@ep-test.neon.tech/db?sslmode=require&channel_binding=require", "postgresql+asyncpg", True),
 ("postgres://user:pass@service.aivencloud.com:1234/db?sslmode=require", "postgresql+asyncpg", True),
 ("postgresql://user:pass@localhost/db?sslmode=disable", "postgresql+asyncpg", False)])
def test_urls(raw, driver, ssl):
    url, options = normalize_database_url(raw)
    assert url.drivername == driver
    assert "sslmode" not in url.query and "channel_binding" not in url.query
    assert options.get("connect_args", {}).get("ssl", False) == ssl
    if ssl:
        assert options["pool_size"] == options["max_overflow"] == 5
    assert options["pool_pre_ping"] and options["pool_recycle"] == 300

async def test_migration_and_persistence(tmp_path):
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", render=False, app_env="test")
    engine = build_engine(settings)
    await migrate(engine)
    await migrate(engine)
    async with engine.begin() as conn:
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert set(metadata.tables) <= set(names)
        await conn.execute(text("INSERT INTO engagements (id,status,version) VALUES ('e','PENDING_PARTNER_REVIEW',1)"))
        await conn.execute(metadata.tables['olostep_cache'].insert().values(
            cache_key_sha256='a'*64, retrieved_at='2026-11-21T00:00:00Z', source_url='https://example.com', response={'text':'evidence'}))
        await conn.execute(metadata.tables['credit_ledger'].insert().values(engagement_id='e', endpoint='/v1/maps', credits_consumed=25, cache_hit=False, mode='live'))
        await conn.execute(text("UPDATE engagements SET credits_used=25 WHERE id='e'"))
    await engine.dispose()
    engine = build_engine(settings)
    await migrate(engine)
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT status FROM engagements WHERE id='e'"))).scalar() == "PENDING_PARTNER_REVIEW"
        assert (await conn.execute(metadata.tables['olostep_cache'].select())).mappings().one()['response'] == {'text':'evidence'}
        assert (await conn.execute(text("SELECT credits_consumed FROM credit_ledger"))).scalar() == 25
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE engagements SET credits_used=26"))
    await engine.dispose()

def test_health_cors_and_production_guard():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", render=False, app_env="test")
    with TestClient(create_app(settings)) as client:
        response = client.get('/health', headers={'Origin':'http://localhost:5173'})
        assert response.json() == {"status":"ok", "db":"connected", "olostep_mode":"replay", "budget_total":5000, "budget_remaining":5000, "budget_source":"local_ledger_not_provider_balance"}
        assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
        assert 'access-control-allow-origin' not in client.get('/health', headers={'Origin':'https://evil.example'}).headers
        with patch.object(type(client.app.state.engine), 'connect', side_effect=RuntimeError('secret')):
            failure = client.get('/health')
            assert failure.status_code == 503
            assert 'secret' not in failure.text
    with pytest.raises(ValueError):
        build_engine(Settings(database_url="sqlite+aiosqlite:///:memory:", app_env="production"))

async def test_streams():
    async def source():
        await asyncio.sleep(.03)
        yield 'data: ok\n\n'
    chunks = [chunk async for chunk in heartbeat_stream(source(), .01)]
    assert ': keep-alive\n\n' in chunks and chunks[-1] == 'data: ok\n\n'
    assert sse_response(source()).headers['x-accel-buffering'] == 'no'
    response = pdf_response(['Test dossier'])
    content = b''.join([chunk async for chunk in response.body_iterator])
    assert content.startswith(b'%PDF-')


def test_postgresql_ddl_and_credentials():
    for table in metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))
    url, _ = normalize_database_url('postgres://u:p%40ss@host/db?sslmode=require&channel_binding=require')
    assert url.password == 'p@ss'


async def test_stream_cancellation():
    closed = asyncio.Event()
    async def source():
        try:
            await asyncio.sleep(60)
            yield 'data: late\n\n'
        finally:
            closed.set()
    stream = heartbeat_stream(source(), .001)
    assert await anext(stream) == ': keep-alive\n\n'
    await stream.aclose()
    assert closed.is_set()
