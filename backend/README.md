# Kalki LLP backend — Phase 1

Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy and httpx. From the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
python -m pytest -q
python scripts/verify_deploy_ready.py
```

Configuration reads process environment. An explicit `--env-file .env` can be added to uvicorn; the application never edits environment files.

| Variable | Default |
| --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./kalki_local.db` |
| `OLOSTEP_MODE` | `replay` |
| `OLOSTEP_API_KEY`, `LLM_API_KEY` | Empty, masked in settings |
| `LLM_MODEL` | `gemini-3.8-flash` |
| `LLM_FAST_MODEL` | `gemini-3.5-flash-lite` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` (comma-separated) |

`APP_ENV=production` or `RENDER=true` requires PostgreSQL. Cloud URLs normalize to asyncpg, remove `sslmode`/`channel_binding`, and enable TLS. Pools use pre-ping, 300-second recycling, five connections plus five overflow connections. Run one worker. Lifespan applies migrations 001–003; migration 003 preserves old cache records and converts cumulative credit balances to per-request entries without resetting spending. `legacy_credit_balances` remains as a historical archive, not an active budget store.

## Base endpoints

- `GET /health`: database probe, mode, local 5,000-credit allowance and remaining amount.
- `GET /api/presets`: four strictly validated synthetic questionnaires and expected outcomes.
- `GET /api/metrics/firm`: persisted engagement/finding/review counts and reserved credit totals.

Budget telemetry is explicitly `local_ledger_not_provider_balance`. No provider balance or model-discovery calls occur. The allowance does not assert an actual account balance and does not reset monthly.

## Gateway contract

Construct `OlostepGateway(engine, settings, engagement_id)` for an existing engagement. Only `map_site`, `scrape_url`, and `search_adverse_media` dispatch requests. Maps are bounded to 50 URLs, include filters to 10, searches to three results, and retries to three attempts. Scrapes request Markdown with `max_age=604800` and 30-day provider storage. [Scrape request documentation](https://docs.olostep.com/api-reference/scrapes/create).

Replay reads PostgreSQL/SQLite cache records only. Missing, invalid, future-dated or older-than-seven-day records raise `ReplayMiss`, never dispatch HTTP. `record` and `live` explicitly permit cache misses to dispatch and save validated results in the database; neither writes live evidence to disk. Both require an API key. Synthetic cache entries are eligible only in replay mode.

Every paid attempt atomically increments `engagements.credits_used` and inserts a ledger reservation **before** sending HTTP. The SQL conditional update enforces the 25-credit ceiling across concurrent callers and restarts. Reservations survive errors, timeouts and cancellation; no refunds are guessed. Standard Maps and Markdown Scrapes reserve one credit. Standard web Search conservatively reserves 10 credits, matching the larger charge in the [Search response example](https://docs.olostep.com/api-reference/searches/create); this exceeds the [published five-credit standard search price](https://www.olostep.com/searches-endpoint). Unknown endpoint costs fail closed. No people/company search, automatic content fetching, crawl, or pagination is available.

429/5xx responses use bounded exponential delays (0.25s, 0.5s); each retry needs its own reservation. Timeouts and 404s return typed partial-evidence results with `timeout`/`not_found`, no manufactured evidence, and no retry. Invalid bodies, redirects and other failures return `unavailable`. Provider error bodies and exception messages are discarded. Successful scrapes preserve original Markdown separately from prompt-safe encoding, with SHA-256, retrieval time, provenance, cache key and an immutable evidence ID. No endpoint updates evidence records.

SSRF validation rejects non-HTTP(S), credentials, nonstandard ports, localhost and nonpublic IPs, and resolves all target addresses before every live attempt. HTTP redirects from the Olostep API are not followed. Olostep itself performs the remote page retrieval: DNS rebinding or redirects inside the provider remain a provider-side security boundary, not something local DNS preflight can guarantee.

## Synthetic replay fixtures

The only packaged data files are read-only `fixtures/olostep_cassettes/*.json`. They contain the questionnaires and matching map/scrape/search cassettes. Lifespan imports them in replay mode using insert-if-absent; existing records and timestamps are never refreshed by startup.

Their declared synthetic retrieval time is **2026-11-22 00:00 UTC**. They intentionally expire after seven days; tests use a controlled clock. To demonstrate later, author a new explicitly dated synthetic fixture version rather than silently extending old evidence freshness.

- `veridian_clean`: consistent encryption/access claims; LOW-risk control clearance is eligible, but final Partner approval is still mandatory.
- `novapay_deceptive`: residency and AI-sharing contradictions; expected CRITICAL Partner review.
- `phantomgrid_injection`: preserves hostile hidden instructions; the prompt encoder escapes embedded delimiters.
- `broken_vendor_404`: security timeout, subprocessor 404, available privacy page; unresolved evidence remains unresolved.

This phase provides schemas and ingestion, not the investigation/LLM runner, authenticated approval workflow, or signed dossier release. Expected fixture outcomes do not themselves approve an engagement. No signing or download route is exposed. LLM model names are configurable defaults, not a claim that availability was tested live. Tests use mock transport and forbid real HTTP dispatch.
