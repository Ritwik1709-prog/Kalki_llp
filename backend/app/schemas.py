from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Framework = Literal["DPDP", "GDPR", "SOC2"]
EngagementStatus = Literal["DRAFT", "INVESTIGATING", "PENDING_PARTNER_REVIEW", "APPROVED", "REJECTED", "RECHECK", "COMPLETED", "INTAKE", "DISCOVERY", "EVIDENCE_COLLECTION", "CROSS_EXAMINATION", "REDLINE_DRAFTING", "AWAITING_PARTNER_REVIEW", "DELIVERED", "FAILED_GRACEFULLY"]
FindingStatus = Literal["VERIFIED", "CONTRADICTED", "UNVERIFIED"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
GateStatus = Literal["PENDING", "APPROVED", "REJECTED", "RECHECK"]

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

class SearchHit(StrictModel):
    url: str
    title: str
    description: str

class WebData(StrictModel):
    status: Literal["ok", "not_found", "timeout", "unavailable"] = "ok"
    urls: list[str] = Field(default_factory=list, max_length=50)
    markdown_content: str | None = None
    links: list[SearchHit] = Field(default_factory=list, max_length=3)

class GatewayResult(WebData):
    cache_hit: bool
    credits_consumed: int
    cache_key_sha256: str
    retrieved_at: str
    provenance: str
    evidence_id: str | None = None

class Claim(StrictModel):
    control_id: str
    text: str
    source_url: str

class Preset(StrictModel):
    id: str
    vendor_name: str
    target_url: str
    framework: Framework
    description: str
    questionnaire: list[Claim] = Field(min_length=2)
    expected_risk: Severity
    expected_status: EngagementStatus
    synthetic: Literal[True] = True
    requires_final_partner_approval: Literal[True] = True

class Cassette(StrictModel):
    endpoint: Literal["/v1/maps", "/v1/scrapes", "/v1/searches"]
    parameters: dict
    retrieved_at: str
    response: WebData

class Fixture(StrictModel):
    preset: Preset
    cassettes: list[Cassette]

class FirmMetrics(StrictModel):
    engagements: int
    pending_partner_review: int
    findings: int
    credits_reserved: int
    budget_total: Literal[5000] = 5000
    budget_remaining: int
    budget_source: Literal["local_ledger_not_provider_balance"] = "local_ledger_not_provider_balance"

class Health(StrictModel):
    status: Literal["ok"] = "ok"
    db: Literal["connected"] = "connected"
    olostep_mode: Literal["replay", "record", "live"]
    budget_total: Literal[5000] = 5000
    budget_remaining: int
    budget_source: Literal["local_ledger_not_provider_balance"] = "local_ledger_not_provider_balance"
