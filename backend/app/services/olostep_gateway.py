"""Only production entry point for Olostep. No pagination, crawling, or refunds."""
import asyncio
import hashlib
import html
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
import httpx
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from ..models import engagements, olostep_cache, credit_ledger, evidence_items, identifier, utcnow
from ..schemas import WebData, GatewayResult, SearchHit

MAX_AGE = 604800
CREDIT_CAP = 25
API_BASE = "https://api.olostep.com"
# Bounded standard operations only. Search reserves the larger documented example
# charge (10), conservatively above the published 5-credit standard search price.
COSTS = {"/v1/maps": 1, "/v1/scrapes": 1, "/v1/searches": 10}

class GatewayError(Exception):
    """Fixed, secret-free public diagnostics only."""

class ReplayMiss(GatewayError):
    pass

class BudgetExceeded(GatewayError):
    pass

class UnsafeURL(GatewayError):
    pass

def canonical_key(endpoint, parameters):
    canonical = json.dumps(["POST", API_BASE + endpoint, parameters], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()

def url_host(url):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        if (parsed.scheme not in {"http", "https"} or not host or parsed.username is not None
                or parsed.password is not None or parsed.port not in {None, 80, 443}
                or any(c.isspace() for c in url) or "\\" in url or "%" in host
                or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (not address.is_global or address.is_multicast or
                (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped)):
            raise ValueError
        return host
    except (ValueError, TypeError):
        raise UnsafeURL("Target URL is not permitted") from None

async def resolve_addresses(host):
    records = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [record[4][0] for record in records]

async def validate_live_url(url, resolver=resolve_addresses):
    host = url_host(url)
    try:
        addresses = await resolver(host)
        if not addresses:
            raise ValueError
        for value in addresses:
            address = ipaddress.ip_address(value)
            if not address.is_global or address.is_multicast or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped):
                raise ValueError
    except (OSError, ValueError):
        raise UnsafeURL("Target DNS resolution is not public") from None

def prompt_safe_evidence(original):
    # Original remains untouched in evidence_items for exact quotation checks.
    return "<UNTRUSTED_WEB_EVIDENCE>" + html.escape(original, quote=True) + "</UNTRUSTED_WEB_EVIDENCE>"

def injection_detected(original):
    return bool(re.search(r"ignore\s+(all\s+)?previous\s+instructions|set\s+risk_score|system\s*prompt", original, re.I))

async def store_cache(conn, key, endpoint, source, data, retrieved_at, provenance):
    insert = postgres_insert if conn.dialect.name == "postgresql" else sqlite_insert
    values = dict(cache_key_sha256=key, endpoint=endpoint, request_url=source, source_url=source,
                  response=data, response_json=data, retrieved_at=retrieved_at,
                  created_at=retrieved_at, provenance=provenance)
    statement = insert(olostep_cache).values(**values)
    await conn.execute(statement.on_conflict_do_update(index_elements=["cache_key_sha256"], set_=values))

class OlostepGateway:
    def __init__(self, engine, settings, engagement_id, *, transport=None, resolver=resolve_addresses,
                 sleep=asyncio.sleep, clock=None):
        self.engine, self.settings, self.engagement_id = engine, settings, engagement_id
        self.transport, self.resolver, self.sleep = transport, resolver, sleep
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    async def map_site(self, url, include_urls=None, top_n=50):
        if type(top_n) is not int or not 1 <= top_n <= 50:
            raise GatewayError("Map limit must be between 1 and 50")
        if include_urls is not None and (not isinstance(include_urls, list) or len(include_urls) > 10 or
                any(not isinstance(item, str) or len(item) > 200 for item in include_urls)):
            raise GatewayError("Invalid map URL filters")
        parameters = {"url": url, "top_n": top_n}
        if include_urls:
            parameters["include_urls"] = include_urls
        return await self._request("/v1/maps", parameters, url)

    async def scrape_url(self, url, max_age=MAX_AGE):
        if type(max_age) is not int or max_age != MAX_AGE:
            raise GatewayError("Scrapes require the seven-day cache policy")
        return await self._request("/v1/scrapes", {"url_to_scrape": url, "formats": ["markdown"],
            "max_age": MAX_AGE, "storage": {"expires_in": "30d"}}, url)

    async def search_adverse_media(self, query, limit=3):
        if not isinstance(query, str) or not query.strip() or len(query) > 500 or type(limit) is not int or not 1 <= limit <= 3:
            raise GatewayError("Invalid bounded search")
        # No search-result content fetching, people search, or companies search.
        return await self._request("/v1/searches", {"query": query, "limit": limit, "type": "any"}, "")

    async def _reserve(self, endpoint, cost, cache_hit=False):
        if type(cost) is not int or cost < 0 or (not cache_hit and cost == 0):
            raise GatewayError("Unknown operation cost; dispatch blocked")
        entry_id = identifier()
        async with self.engine.begin() as conn:
            changed = await conn.execute(update(engagements).where(
                engagements.c.id == self.engagement_id, engagements.c.credits_used + cost <= CREDIT_CAP
            ).values(credits_used=engagements.c.credits_used + cost, updated_at=utcnow()).returning(engagements.c.id))
            if changed.scalar_one_or_none() is None:
                raise BudgetExceeded("Engagement missing or 25-credit cap exceeded")
            await conn.execute(credit_ledger.insert().values(id=entry_id, engagement_id=self.engagement_id,
                endpoint=endpoint, credits_consumed=cost, cache_hit=cache_hit, mode=self.settings.olostep_mode,
                outcome="cache_hit" if cache_hit else "reserved"))
        # Commit before dispatch; crashes/cancellation leave the reservation spent.
        return entry_id

    async def _complete(self, entry_id, outcome, status_code, start):
        async with self.engine.begin() as conn:
            await conn.execute(update(credit_ledger).where(credit_ledger.c.id == entry_id).values(
                outcome=outcome, status_code=status_code, latency_ms=max(0, int((time.monotonic()-start)*1000))))

    async def _result(self, data, key, source, retrieved_at, provenance, cache_hit, credits):
        evidence_id = None
        if data.status == "ok" and data.markdown_content is not None:
            evidence_id = identifier()
            async with self.engine.begin() as conn:
                await conn.execute(evidence_items.insert().values(id=evidence_id, engagement_id=self.engagement_id,
                    source_url=source, page_type=urlsplit(source).path.strip("/") or "home",
                    markdown_content=data.markdown_content,
                    content_sha256=hashlib.sha256(data.markdown_content.encode()).hexdigest(),
                    injection_detected=injection_detected(data.markdown_content), cache_hit=cache_hit,
                    cache_key_sha256=key, retrieved_at=retrieved_at, provenance=provenance))
        return GatewayResult(**data.model_dump(), cache_hit=cache_hit, credits_consumed=credits,
            cache_key_sha256=key, retrieved_at=retrieved_at, provenance=provenance, evidence_id=evidence_id)

    async def _request(self, endpoint, parameters, source):
        if endpoint not in COSTS:
            raise GatewayError("Endpoint not permitted")
        if source:
            url_host(source)
        key = canonical_key(endpoint, parameters)
        async with self.engine.connect() as conn:
            row = (await conn.execute(select(olostep_cache).where(olostep_cache.c.cache_key_sha256 == key))).mappings().first()
        if row is not None:
            try:
                age = (self.clock() - datetime.fromisoformat(row["retrieved_at"])).total_seconds()
                data = WebData.model_validate(row["response_json"])
                # Synthetic records must never masquerade as live evidence.
                allowed = self.settings.olostep_mode == "replay" or row["provenance"] != "synthetic"
                if 0 <= age <= MAX_AGE and allowed:
                    await self._reserve(endpoint, 0, True)
                    return await self._result(data, key, source, row["retrieved_at"], row["provenance"], True, 0)
            except (ValueError, TypeError, ValidationError):
                pass
        if self.settings.olostep_mode == "replay":
            raise ReplayMiss("Replay entry missing, invalid or expired; network disabled")
        if self.settings.olostep_mode not in {"live", "record"} or not self.settings.olostep_api_key.get_secret_value():
            raise GatewayError("Explicit live/record mode and API key required")

        credits = 0
        for attempt in range(3):
            if source:
                await validate_live_url(source, self.resolver)
            cost = COSTS.get(endpoint)
            entry = await self._reserve(endpoint, cost)
            credits += cost
            start, status_code, retry = time.monotonic(), None, False
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=30, follow_redirects=False, trust_env=False) as client:
                    async with client.stream("POST", API_BASE + endpoint, json=parameters,
                        headers={"Authorization": "Bearer " + self.settings.olostep_api_key.get_secret_value()}) as response:
                        status_code = response.status_code
                        if status_code == 404:
                            data = WebData(status="not_found")
                        elif status_code == 429 or status_code >= 500:
                            data, retry = WebData(status="unavailable"), True
                        elif status_code != 200:
                            data = WebData(status="unavailable")
                        else:
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > 2_000_000:
                                    raise ValueError
                            data = self._parse(endpoint, json.loads(body), parameters)
            except httpx.TimeoutException:
                data = WebData(status="timeout")  # Billing uncertain: never retry timeout.
            except (httpx.HTTPError, ValueError, TypeError, KeyError, ValidationError):
                data = WebData(status="unavailable")
            await self._complete(entry, data.status, status_code, start)
            if retry and attempt < 2:
                await self.sleep(0.25 * 2 ** attempt)
                continue
            retrieved_at = self.clock().isoformat()
            async with self.engine.begin() as conn:
                await store_cache(conn, key, endpoint, source, data.model_dump(), retrieved_at, "olostep")
            return await self._result(data, key, source, retrieved_at, "olostep", False, credits)
        raise GatewayError("Bounded attempts exhausted")

    @staticmethod
    def _parse(endpoint, body, parameters):
        if not isinstance(body, dict):
            raise ValueError
        if endpoint == "/v1/maps":
            urls = body["urls"]
            if not isinstance(urls, list) or len(urls) > parameters["top_n"]:
                raise ValueError
            for url in urls:
                url_host(url)
            return WebData(urls=urls)
        if endpoint == "/v1/scrapes":
            markdown = body["result"]["markdown_content"]
            if not isinstance(markdown, str) or not markdown.strip():
                raise ValueError
            return WebData(markdown_content=markdown)
        links = body["result"]["links"]
        if not isinstance(links, list) or len(links) > parameters["limit"]:
            raise ValueError
        for link in links:
            url_host(link["url"])
        return WebData(links=[SearchHit(url=link["url"], title=link["title"], description=link["description"]) for link in links])
