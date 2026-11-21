# Attest LLP

Attest LLP is an autonomous vendor due-diligence and compliance firm that cross-examines vendor security claims against live web evidence, pauses at a Managing Partner judgment gate, and delivers signed compliance dossiers.

Track A2: **The full-stack AI firm**.

## Who it serves, its one task, and when it is finished

**For:** procurement teams, security and compliance leads, and Managing Partners who must decide whether a vendor's security claims withstand scrutiny.

**One task:** audit a vendor's security claims against attributable web evidence and turn the discrepancies into a reviewable compliance decision.

**Finished means:** a versioned dossier includes the vendor claims, evidence, findings with verbatim quotations and source URLs, unresolved gaps, and a recorded human approval. HIGH/CRITICAL contradictions have passed mandatory Human-in-the-Loop Partner Review, and the approving Managing Partner's sign-off accompanies the delivered dossier. A pending or rejected review is not a completed engagement.

## AI tools, models, and libraries

| Tool / library | Role |
| --- | --- |
| Astra | AI development assistant for implementation and review |
| Gemini `gemini-3.8-flash` | Our LLM model for claim extraction, cross-examination, and dossier drafting |
| Olostep API | Discover and retrieve web evidence through `OlostepGateway` |
| FastAPI + Pydantic v2 | Backend API and validated data contracts |
| SQLite | Engagement state, evidence cache, credit ledger, and review records |
| React + Vite + TypeScript | Frontend application |
| Tailwind CSS | Dark-mode styling |
| pytest | Automated verification with mocked or replayed services |
| python-dotenv | Load local smoke-test configuration without modifying `.env` |

This initialization provides project rules and a connectivity script; the application and its approval/signing workflow are still to be built.

## First-weekend milestone

Ship **one rough end-to-end audit-to-approval-to-dossier slice**: submit one vendor and a small set of claims, collect bounded evidence, generate cited findings, pause on a HIGH/CRITICAL contradiction, let a human Managing Partner approve or reject it, and export a dossier with recorded sign-off only after approval. Demonstrate the workflow using replayed evidence, including a blocked export before approval.

## Credit and evidence discipline

`AGENTS.md` defines the mandatory implementation rules: replay by default, a SQLite SHA-256 evidence cache with `max_age: 604800`, a persistent 25-credit engagement cap, no `/v1/crawls`, isolated `<UNTRUSTED_WEB_EVIDENCE>` context, verbatim citations on every finding, and mandatory Partner review.

## Smoke test

Requires Python 3.10+ and `python-dotenv`:

```powershell
python -m pip install python-dotenv
python scripts/smoke_test.py --live
```

The script loads the repository's `.env` without overwriting existing process variables or editing the file. It reads `OLOSTEP_API_KEY` and `LLM_API_KEY`. `LLM_PROVIDER` defaults to `gemini` and `LLM_MODEL` defaults to `gemini-3.8-flash`; optional environment overrides do not require editing `.env`.

`--live` explicitly enables the two connectivity checks even when `.env` says `OLOSTEP_MODE=replay`. After configuration validation, it attempts exactly one [Olostep Maps request](https://docs.olostep.com/api-reference/maps/create) (`https://example.com`, `top_n: 5`, budgeted at one credit) and one small [Gemini generateContent request](https://ai.google.dev/gemini-api/docs/get-started), with no retries, redirects, pagination, or model fallback. An exhausted budget prevents the Olostep request. Each check prints PASS/FAIL; exit status is nonzero if either fails. Provider errors are reported only as HTTP status codes, never response bodies or credentials.

Without `--live` (or explicit `OLOSTEP_MODE=live`), no network calls are made: Olostep checks the replay cache and the LLM check reports FAIL because live mode is required. Replay is not a connectivity PASS. The smoke cache and persistent credit ledger live outside the repository at `~/.attest_llp/smoke.sqlite3`; `ATTEST_SMOKE_DB` can override this path. A live run deliberately refreshes the cached map; replay accepts it for 604800 seconds. Failed/uncertain live attempts retain their one-credit reservation. Maps has no `max_age` request field, so its cache age is enforced locally.

No paid connectivity checks are part of repository initialization. Run the live command when ready to spend one Olostep credit plus the minimal LLM usage.

If Olostep has already passed, retry only Gemini without another Olostep charge:

```powershell
python scripts/smoke_test.py --live --llm-only
```

This makes one LLM request, never opens the Olostep cache, and requires only `LLM_API_KEY`. The default Gemini 3.8 Flash request uses the supported `low` thinking level and a 256-token output cap (including thinking tokens). See [Gemini thinking levels](https://aistudio.google.com/docs/thinking). `--llm-only` still requires live mode; it does not enable network access by itself.
