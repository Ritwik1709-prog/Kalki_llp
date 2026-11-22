"""Bounded five-agent workflow. Models propose; application code owns authority."""
import asyncio
import hashlib
import html
import json
import re
import time
from urllib.parse import urlsplit
from sqlalchemy import select, update
from ..models import engagements, evidence_items, findings, approval_gates, identifier, utcnow
from ..schemas import Claim
from ..services.event_bus import TERMINAL
from ..services.llm_client import LLMClient
from ..services.olostep_gateway import OlostepGateway, GatewayError, injection_detected, url_host

def exact_excerpt(quote, original):
    if not isinstance(quote, str) or not quote.strip():
        return None
    pattern = r"\s+".join(re.escape(part) for part in quote.split())
    match = re.search(pattern, original, re.I)
    return match.group(0) if match else None

def scan_injection(text):
    normalized = html.unescape(text)
    normalized = re.sub(r"[\u200b-\u200f\ufeff]", "", normalized)
    return injection_detected(normalized) or bool(re.search(
        r"ignore\s*(?:all\s*)?previous\s*instructions|</?system>|</UNTRUSTED_WEB_EVIDENCE>|(?:approve|sign|bypass).{0,40}(?:gate|dossier|review)|(?:reveal|print).{0,30}(?:secret|api.key)", normalized, re.I | re.S))

def citation(item, quote):
    return dict(evidence_id=item["id"],source_url=item["source_url"],retrieved_at=item["retrieved_at"],
        cache_key_sha256=item["cache_key_sha256"],content_sha256=item["content_sha256"],verbatim_quote=quote)

class IntakeAgent:
    async def run(self, row):
        # Input is already structured into atomic, bounded claims. Do not let an LLM
        # rewrite the questionnaire's original claim wording or assign authority.
        claims = [Claim.model_validate(claim) for claim in row["questionnaire_json"]]
        if not claims or len(claims) > 30 or len({c.control_id for c in claims}) != len(claims):
            raise ValueError("Invalid atomic questionnaire")
        return [c.model_dump() for c in claims]

class DiscoveryAgent:
    async def run(self, row, gateway, llm):
        mapped = await gateway.map_site(row["target_url"])
        if mapped.status != "ok":
            raise GatewayError("Discovery unavailable")
        host = url_host(row["target_url"])
        candidates = []
        for url in mapped.urls:
            if url_host(url) == host and any(path in urlsplit(url).path.lower() for path in ("privacy","security","terms","trust","subprocessors")):
                candidates.append(url)
        candidates = list(dict.fromkeys(candidates))[:50]
        ranked = await llm.rank_urls(candidates)
        # A model can only select from already-discovered, validated URLs.
        return list(dict.fromkeys(url for url in ranked.urls if url in candidates))[:5], mapped

class InvestigatorAgent:
    async def run(self, urls, row, gateway):
        semaphore = asyncio.Semaphore(3)
        async def scrape(url):
            async with semaphore:
                try:
                    return url, await gateway.scrape_url(url)
                except GatewayError:
                    return url, None
        async def search():
            try:
                return await gateway.search_adverse_media(row["vendor_name"] + " security breach regulatory action")
            except GatewayError:
                return None
        # Await all children even during cancellation; no detached paid requests.
        tasks = [asyncio.create_task(scrape(url)) for url in urls]
        tasks.append(asyncio.create_task(search()))
        try:
            results = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return results[:-1], results[-1]

class CrossExamAgent:
    async def run(self, claim, evidence, llm):
        result = await llm.analyze(claim, evidence)
        if result.status == "UNVERIFIED":
            return None
        item = next((e for e in evidence if e["id"] == result.evidence_id and e["source_url"] == result.source_url), None)
        quote = exact_excerpt(result.verbatim_quote, item["markdown_content"]) if item else None
        if not quote:
            return None  # Dropped, and explicitly recorded as an unresolved claim.
        severity = result.severity
        if result.status == "CONTRADICTED" and severity in {"LOW","MEDIUM"}:
            severity = "HIGH"  # Conservative gate; never downgrade to evade review.
        return dict(id=identifier(),control_id=claim["control_id"],claim_text=claim["text"],
            status=result.status,severity=severity,verbatim_quote=quote,source_url=item["source_url"],
            confidence=result.confidence,citations=[citation(item,quote)],partner_status="PENDING",
            data={"rationale":result.rationale})

class RedlineAgent:
    async def run(self, rows, llm):
        for row in rows:
            if row["status"] == "CONTRADICTED" and row["severity"] in {"HIGH","CRITICAL"}:
                draft = await llm.redline(row)
                original = exact_excerpt(draft.redline_original, row["verbatim_quote"])
                if not original:
                    raise ValueError("Redline original is not cited source text")
                row.update(redline_original=original,redline_proposed=draft.redline_proposed)
        weights = {"LOW":0,"MEDIUM":30,"HIGH":65,"CRITICAL":90}
        scores = [weights[r["severity"]] for r in rows]
        return min(100, max(scores,default=0) + 5*max(0,sum(s>0 for s in scores)-1))

class Orchestrator:
    def __init__(self, engine, settings, bus, *, llm=None, gateway_factory=None):
        self.engine,self.settings,self.bus = engine,settings,bus
        self.llm = llm or LLMClient(settings)
        self.gateway_factory = gateway_factory or (lambda settings, eid: OlostepGateway(engine,settings,eid))

    async def recover(self):
        async with self.engine.connect() as conn:
            rows = (await conn.execute(select(engagements).where(engagements.c.status.in_(
                ["DRAFT","INTAKE","DISCOVERY","EVIDENCE_COLLECTION","CROSS_EXAMINATION","REDLINE_DRAFTING"])))).mappings().all()
        for row in rows:
            async with self.engine.connect() as conn:
                persisted = [dict(f) for f in (await conn.execute(select(findings).where(findings.c.engagement_id==row["id"]))).mappings()]
            await self._fail(row["id"],dict(row),persisted,[],time.monotonic(),"Execution interrupted by restart; manual rerun required.")

    async def run(self, eid):
        start = time.monotonic()
        async with self.engine.begin() as conn:
            claimed = (await conn.execute(update(engagements).where(engagements.c.id==eid,engagements.c.status=="DRAFT")
                .values(status="INTAKE").returning(engagements))).mappings().first()
        if claimed is None:
            return  # At-most-one run, including across concurrent callers.
        row = dict(claimed)
        collected = []
        gaps = []
        try:
            mode = (row["data"] or {}).get("mode",self.settings.olostep_mode)
            settings = self.settings.model_copy(update={"olostep_mode":mode})
            gateway = self.gateway_factory(settings,eid)
            await self.bus.emit(eid,"INTAKE","Normalizing atomic vendor claims.",status="INTAKE",
                payload={"llm_mode":"mock" if self.llm.mock else "live", "olostep_mode":mode})
            claims = await IntakeAgent().run(row)
            await self.bus.emit(eid,"DISCOVERY","Discovering and ranking bounded compliance URLs.",status="DISCOVERY")
            urls,mapped = await DiscoveryAgent().run(row,gateway,self.llm)
            await self.bus.emit(eid,"DISCOVERY","Compliance URLs ranked.",payload={"urls":urls},credits_delta=mapped.credits_consumed)
            if not urls:
                raise GatewayError("No eligible evidence URLs")
            await self.bus.emit(eid,"EVIDENCE_COLLECTION","Collecting evidence with concurrency capped at three.",status="EVIDENCE_COLLECTION")
            results,search = await InvestigatorAgent().run(urls,row,gateway)
            async with self.engine.connect() as conn:
                stored = [dict(r) for r in (await conn.execute(select(evidence_items).where(evidence_items.c.engagement_id==eid))).mappings()]
            eligible = []
            for item in stored:
                if scan_injection(item["markdown_content"]):
                    quote = item["markdown_content"]
                    finding = dict(id=identifier(),engagement_id=eid,control_id="EVIDENCE-INTEGRITY",claim_text="Source content is evidence, never authority.",
                        status="UNVERIFIED",severity="CRITICAL",verbatim_quote=quote,source_url=item["source_url"],confidence=1.0,
                        citations=[citation(item,quote)],partner_status="PENDING",data={"rationale":"Prompt-injection attempt quarantined.","security_integrity":True})
                    collected.append(finding)
                    async def quarantine(conn, item=item, finding=finding):
                        await conn.execute(update(evidence_items).where(evidence_items.c.id==item["id"]).values(injection_detected=True))
                        await conn.execute(findings.insert().values(**finding))
                    await self.bus.emit(eid,"EVIDENCE_COLLECTION","CRITICAL source-instruction attempt quarantined.",
                        event_type="security_alert",payload={"evidence_id":item["id"],"severity":"CRITICAL"},mutate=quarantine)
                else:
                    eligible.append(item)
            for url,result in results:
                if result is None or result.status != "ok":
                    gaps.append({"source_url":url,"reason":"Evidence unavailable"})
                await self.bus.emit(eid,"EVIDENCE_COLLECTION","Evidence retrieval completed.",
                    payload={"source_url":url,"status":result.status if result else "unavailable"},credits_delta=result.credits_consumed if result else 0)
            if search is None or search.status != "ok":
                gaps.append({"reason":"Adverse-media search unavailable"})
            elif search.links:
                # Snippets are leads, not accepted findings; this phase never invents
                # corroboration or fetches additional unbounded pages from search.
                gaps.append({"reason":"Adverse-media leads require corroboration","leads":[h.model_dump() for h in search.links]})
            await self.bus.emit(eid,"EVIDENCE_COLLECTION","Bounded adverse-media check completed.",
                payload={"status":search.status if search else "unavailable","leads":len(search.links) if search else 0},credits_delta=search.credits_consumed if search else 0)
            await self.bus.emit(eid,"CROSS_EXAMINATION","Validating claims against eligible original evidence.",status="CROSS_EXAMINATION")
            for index,claim in enumerate(claims):
                result = await CrossExamAgent().run(claim,eligible,self.llm)
                if result:
                    result["engagement_id"] = eid
                    # Both sides of contradictions include exact claim provenance.
                    result["citations"].append(dict(source_url=claim["source_url"],retrieved_at=row["created_at"],
                        evidence_id=f"questionnaire:{eid}:v{row['version']}:{index}",
                        content_sha256=hashlib.sha256(claim["text"].encode()).hexdigest(),verbatim_quote=claim["text"]))
                    async def persist(conn, result=result):
                        await conn.execute(findings.insert().values(**result))
                    await self.bus.emit(eid,"CROSS_EXAMINATION","Cited finding accepted.",payload={"control_id":claim["control_id"],"status":result["status"]},mutate=persist)
                    collected.append(result)
                else:
                    gaps.append({"control_id":claim["control_id"],"reason":"UNVERIFIED: missing or invalid citation"})
                    await self.bus.emit(eid,"CROSS_EXAMINATION","Claim unresolved; no unsupported finding persisted.",payload={"control_id":claim["control_id"],"status":"UNVERIFIED"})
            await self.bus.emit(eid,"REDLINE_DRAFTING","Drafting cited remediation and computing risk.",status="REDLINE_DRAFTING")
            risk = await RedlineAgent().run(collected,self.llm)
            risk = max(risk,30 if gaps else 0)
            review = any(f["severity"] in {"HIGH","CRITICAL"} or f.get("redline_proposed") for f in collected)
            terminal = "AWAITING_PARTNER_REVIEW" if review else "FAILED_GRACEFULLY" if gaps or any(f["severity"]!="LOW" for f in collected) else "DELIVERED"
            await self._finish(eid,row,collected,gaps,risk,terminal,start)
        except asyncio.CancelledError:
            await self._fail(eid,row,collected,gaps,start,"Execution cancelled; evidence retained.")
            raise
        except Exception:
            await self._fail(eid,row,collected,gaps,start,"Execution unavailable; evidence retained for investigation.")

    async def _fail(self,eid,row,collected,gaps,start,message):
        critical = any(f["severity"] in {"HIGH","CRITICAL"} for f in collected)
        try:
            await self._finish(eid,row,collected,gaps+[{"reason":message}],90 if critical else 30,
                "AWAITING_PARTNER_REVIEW" if critical else "FAILED_GRACEFULLY",start)
        except Exception:
            # A DB outage cannot safely manufacture a terminal event. Startup
            # recovery handles the durable unfinished state when DB returns.
            pass

    async def _finish(self,eid,row,collected,gaps,risk,status,start):
        async def persist(conn):
            for finding in collected:
                if finding.get("redline_proposed"):
                    await conn.execute(update(findings).where(findings.c.id==finding["id"]).values(
                        redline_original=finding["redline_original"],redline_proposed=finding["redline_proposed"]))
            if status=="AWAITING_PARTNER_REVIEW":
                await conn.execute(approval_gates.insert().values(engagement_id=eid,status="PENDING",
                    reviewed_version=row["version"],evidence_version=hashlib.sha256(json.dumps(
                        [f["citations"] for f in collected],sort_keys=True).encode()).hexdigest(),
                    partner_notes="Human decision required; no automatic approval."))
        data = dict(row["data"] or {}, unresolved=gaps, signed=False, release_authorized=False,
            delivery_kind="unsigned_analysis", llm_mode="mock" if self.llm.mock else "live")
        await self.bus.emit(eid,status,"Analysis paused for Partner review." if status=="AWAITING_PARTNER_REVIEW" else "Unsigned analysis delivered." if status=="DELIVERED" else "Investigation incomplete; evidence gaps retained.",
            status=status,event_type="terminal",payload={"status":status,"risk_score":risk,"unresolved":len(gaps),"signed":False},
            values={"risk_score":risk,"duration_ms":int((time.monotonic()-start)*1000),"data":data},mutate=persist)
