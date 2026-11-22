# Kalki LLP backend — Phases 1 and 2

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

## Autonomous engine and Gemini

`LLM_MODE=auto` is the default: a present `LLM_API_KEY` selects Gemini; no key selects the deterministic mock analyzer. `LLM_MODE=mock` forces offline analysis, including in CI. Live request failures are reported as incomplete investigations, never silently converted into successful mock results. The mock analyzer is intentionally narrow; unfamiliar assertions stay unresolved. Model names are configurable defaults, not a claim that their availability was tested live.

The `google-genai` async client uses the fast model for URL ranking and the main model for cross-examination and redlines. Pydantic validates JSON strictly; a schema failure allows exactly one new generation. SDK transport retries are disabled and requests have bounded timeouts. Trusted system instructions are separate from escaped untrusted claims, evidence and metadata. Models have no tools or review authority.

The five agents run INTAKE → DISCOVERY → EVIDENCE_COLLECTION → CROSS_EXAMINATION → REDLINE_DRAFTING. Discovery selects only supplied same-host compliance URLs, at most five; scraping uses a semaphore of three and one adverse-media search. Search snippets are uncorroborated leads, never findings. Suspicious pages are preserved and quarantined before model use. Injection alerts have application-assigned CRITICAL severity.

The citation gate matches case/whitespace-normalized text, then stores the **exact original substring**, source URL, evidence ID, retrieval timestamp and content/cache hashes. Contradictions additionally cite the original questionnaire claim/version. Missing or invalid quotations become unresolved entries, not accepted findings. Redline originals must also match the cited source.

Risk weights are LOW=0, MEDIUM=30, HIGH=65, CRITICAL=90. The maximum weight plus five per additional non-LOW finding is capped at 100; unresolved gaps impose a floor of 30. Any HIGH/CRITICAL finding or redline creates a PENDING gate and ends in `AWAITING_PARTNER_REVIEW`. Incomplete investigations end in `FAILED_GRACEFULLY`. Only wholly verified LOW-risk results end in `DELIVERED`.

**DELIVERED means unsigned analysis available, not a signed dossier or approval.** Every result explicitly retains `signed=false` and `release_authorized=false`. Authenticated Partner decisions and signed downloads remain outside this phase; no unguarded release route exists.

## Execution and reconnection

- `POST /api/engagements` accepts `{"preset_id":"veridian_clean"}` or custom `vendor_name`, `target_url`, `framework`, and `questionnaire` (1–30 atomic `{control_id,text,source_url}` claims). It returns HTTP 202 with an ID and stream URL. Framework names normalize to uppercase.
- `GET /api/engagements?limit=20&offset=0` returns the queue and status counts.
- `GET /api/engagements/{id}` returns the engagement, steps, original evidence, cited findings, approval gate and audit log.
- `GET /api/engagements/{id}/stream` replays ordered persisted events, then follows new ones. SSE event `agent_step` has a monotonically increasing per-engagement `id`. Reconnect with `Last-Event-ID`; omit it to restore the complete trace. Clients should close their EventSource on a terminal event.

`mode_override` is accepted only when the server has `OLOSTEP_MODE=live`; synthetic presets always use replay. No request can change the 25-credit cap. For a completely offline preset run use both `OLOSTEP_MODE=replay` and `LLM_MODE=mock`.

Migration 004 adds durable sequence counters and a unique event order. Event persistence, state transitions, findings/gates and hash-chained audit entries share transactions. Queue notifications are bounded hints; the database is authoritative and periodically reconciled. All streams use the common SSE helper with 15-second comment heartbeats and no-cache/keep-alive/proxy-buffering headers.

Background tasks are retained and cancelled cleanly on shutdown. Atomic run claiming prevents duplicate execution. Startup marks interrupted investigations incomplete (or paused when HIGH/CRITICAL findings already exist), rather than replaying potentially paid requests. This is a single-worker service, not a durable distributed job scheduler. Restarts restore the trace, not in-flight execution.

Tests use mocked transports and a controlled fixture clock, forbid real HTTP dispatch, and exercise all four presets through execution and reconnecting SSE. No live Gemini or Olostep validation is part of the test suite.
