"""Read-only synthetic data; imports never refresh expired retrieval timestamps."""
from pathlib import Path
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from .models import olostep_cache
from .schemas import Fixture
from .services.olostep_gateway import canonical_key

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "olostep_cassettes"

def load_fixtures():
    return [Fixture.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(FIXTURES.glob("*.json"))]

async def seed_replay_cache(engine):
    async with engine.begin() as conn:
        insert = postgres_insert if conn.dialect.name == "postgresql" else sqlite_insert
        for fixture in load_fixtures():
            for cassette in fixture.cassettes:
                source = cassette.parameters.get("url", cassette.parameters.get("url_to_scrape", ""))
                data = cassette.response.model_dump()
                statement = insert(olostep_cache).values(
                    cache_key_sha256=canonical_key(cassette.endpoint, cassette.parameters), endpoint=cassette.endpoint,
                    request_url=source, source_url=source, response=data, response_json=data,
                    retrieved_at=cassette.retrieved_at, created_at=cassette.retrieved_at, provenance="synthetic")
                await conn.execute(statement.on_conflict_do_nothing(index_elements=["cache_key_sha256"]))
