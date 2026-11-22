"""Bounded Olostep/Gemini connectivity checks; no secrets in diagnostics."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_AGE = 604800
CREDIT_CAP = 25
ROOT = Path(__file__).resolve().parents[1]


class CheckFailure(Exception):
    """Only fixed, safe diagnostic messages may be passed here."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url, headers, payload):
    """One attempt, with neither automatic retries nor redirects."""
    request = Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with build_opener(NoRedirects()).open(request, timeout=45) as response:
            if not 200 <= response.status < 300:
                raise CheckFailure("unexpected HTTP status")
            result = json.load(response)
        if not isinstance(result, dict):
            raise CheckFailure("invalid JSON response shape")
        return result
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise CheckFailure(f"HTTP {code}") from None


def validate_map(result):
    urls = result.get("urls")
    if not isinstance(urls, list) or not urls or not all(
        isinstance(url, str) and url.startswith(("https://", "http://"))
        for url in urls
    ):
        raise CheckFailure("missing or invalid map URLs")


class OlostepGateway:
    """Smoke-only gateway: one fixed endpoint and a persistent smoke budget."""

    def __init__(self, db, mode, api_key):
        self.db, self.mode, self.api_key = db, mode, api_key
        self.called = False
        db.execute("CREATE TABLE IF NOT EXISTS cache "
                   "(key TEXT PRIMARY KEY, fetched REAL NOT NULL, body TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS budget "
                   "(engagement TEXT PRIMARY KEY, credits INTEGER NOT NULL)")
        db.commit()

    def check_map(self):
        if self.called:
            raise CheckFailure("one-map-per-run limit reached")
        self.called = True
        if self.mode not in {"live", "replay"}:
            raise CheckFailure("invalid Olostep mode")
        endpoint = "https://api.olostep.com/v1/maps"
        payload = {"url": "https://example.com", "top_n": 5}
        canonical = json.dumps(["POST", endpoint, payload], sort_keys=True,
                               separators=(",", ":"))
        key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if self.mode == "replay":
            row = self.db.execute("SELECT fetched, body FROM cache WHERE key = ?",
                                  (key,)).fetchone()
            if row is None or not 0 <= time.time() - row[0] <= MAX_AGE:
                raise CheckFailure("replay cache missing or expired; no network call")
            validate_map(json.loads(row[1]))
            return "cached evidence only; connectivity not checked"

        # Reserve before dispatch, serializing competing processes. Never refund
        # timeouts/errors: the provider may already have charged for the request.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT OR IGNORE INTO budget VALUES ('smoke', 0)")
            changed = self.db.execute(
                "UPDATE budget SET credits = credits + 1 "
                "WHERE engagement = 'smoke' AND credits < ?", (CREDIT_CAP,),
            ).rowcount
            if changed != 1:
                raise CheckFailure("25-credit smoke engagement cap reached")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        result = post_json(endpoint, {"Authorization": f"Bearer {self.api_key}"}, payload)
        validate_map(result)
        self.db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                        (key, time.time(), json.dumps(result)))
        self.db.commit()
        return "one live map request"


def check_llm(api_key, model):
    result = post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"x-goog-api-key": api_key},
        {"contents": [{"role": "user", "parts": [{"text": "Reply only OK."}]}],
         "generationConfig": {"maxOutputTokens": 256,
                              "thinkingConfig": {"thinkingLevel": "low"}}},
    )
    candidates = result.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    if not any(isinstance(part.get("text"), str) and part["text"].strip()
               and not part.get("thought", False) for part in parts):
        raise CheckFailure("no generated text")
    return "one live LLM request"


def report(label, check):
    try:
        detail = check()
        print(f"PASS {label}: {detail}")
        return True
    except CheckFailure as exc:
        print(f"FAIL {label}: {exc}")
    except Exception:
        # Never print arbitrary exceptions: URLs, bodies, and headers may contain secrets.
        print(f"FAIL {label}: request, response, or local storage error")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="enable live checks (one Olostep credit unless --llm-only)")
    parser.add_argument("--llm-only", action="store_true",
                        help="check only Gemini; never call Olostep or open its cache")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False, interpolate=False)
    except ImportError:
        print("FAIL configuration: install python-dotenv")
        return 1
    except Exception:
        print("FAIL configuration: unable to load .env")
        return 1

    mode = "live" if args.live else os.getenv("OLOSTEP_MODE", "replay").strip().lower()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    model = os.getenv("LLM_MODEL", "gemini-3.8-flash").strip()
    olostep_key = os.getenv("OLOSTEP_API_KEY", "").strip()
    llm_key = os.getenv("LLM_API_KEY", "").strip()
    if mode not in {"live", "replay"} or provider != "gemini" or not re.fullmatch(
        r"gemini-[A-Za-z0-9.-]+", model
    ):
        print("FAIL configuration: invalid mode, provider, or Gemini model ID")
        return 1
    if mode == "live" and (not llm_key or (not args.llm_only and not olostep_key)):
        print("FAIL configuration: API keys for selected checks are required")
        return 1

    if args.llm_only:
        if mode != "live":
            print("FAIL LLM: live mode required; no network call")
            return 1
        return 0 if report("LLM", lambda: check_llm(llm_key, model)) else 1

    def map_check():
        configured_path = os.getenv("KALKI_SMOKE_DB")
        path = Path(configured_path) if configured_path else Path.home() / ".kalki_llp" / "smoke.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10)
        try:
            return OlostepGateway(db, mode, olostep_key).check_map()
        finally:
            db.close()

    map_ok = report(f"Olostep ({mode})", map_check)
    if mode != "live":
        print("FAIL LLM: live mode required; no network call")
        return 1
    llm_ok = report("LLM", lambda: check_llm(llm_key, model))
    return 0 if map_ok and llm_ok else 1


if __name__ == "__main__":
    sys.exit(main())
