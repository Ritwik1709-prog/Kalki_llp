"""Strict response contracts for the execution API."""
from ..schemas import StrictModel,EngagementStatus,Framework,FindingStatus,Severity,GateStatus

class CreatedEngagement(StrictModel):
    id: str
    code: str
    status: EngagementStatus
    stream_url: str

class EngagementSummary(StrictModel):
    id: str
    code: str | None
    vendor_name: str | None
    framework: Framework | None
    status: EngagementStatus
    risk_score: int | None
    credits_used: int
    duration_ms: int | None
    created_at: str

class EngagementRecord(EngagementSummary):
    version: int
    data: dict | None
    target_url: str | None
    questionnaire_json: list[dict] | None
    event_seq: int
    audit_head: str | None
    updated_at: str

class StepRecord(StrictModel):
    id: str
    engagement_id: str
    sequence: int
    stage: str
    event_type: str
    message: str
    payload_json: dict | None
    credits_delta: int
    latency_ms: int | None
    created_at: str

class EvidenceRecord(StrictModel):
    id: str
    engagement_id: str
    source_url: str
    page_type: str
    markdown_content: str
    content_sha256: str
    injection_detected: bool
    cache_hit: bool
    cache_key_sha256: str
    retrieved_at: str
    provenance: str
    created_at: str

class FindingRecord(StrictModel):
    id: str
    engagement_id: str
    severity: Severity
    citations: list[dict]
    data: dict | None
    control_id: str | None
    claim_text: str | None
    status: FindingStatus | None
    verbatim_quote: str | None
    source_url: str | None
    confidence: float | None
    redline_original: str | None
    redline_proposed: str | None
    partner_status: GateStatus | None

class GateRecord(StrictModel):
    id: str
    engagement_id: str
    status: GateStatus
    reviewer: str | None
    reviewed_version: int | None
    reviewed_at: str | None
    rationale: str | None
    partner_notes: str | None
    decided_by: str | None
    decided_at: str | None
    evidence_version: str | None

class AuditRecord(StrictModel):
    id: str
    engagement_id: str | None
    created_at: str
    event: dict
    issuer: str
    actor: str | None
    action: str | None
    payload_json: dict | None
    prev_hash: str | None
    entry_hash: str | None

class QueueResponse(StrictModel):
    items: list[EngagementSummary]
    total: int
    limit: int
    offset: int
    summary: dict[str,int]

class DetailResponse(StrictModel):
    engagement: EngagementRecord
    steps: list[StepRecord]
    evidence: list[EvidenceRecord]
    findings: list[FindingRecord]
    approval_gates: list[GateRecord]
    approval_gate: GateRecord | None
    audit_logs: list[AuditRecord]
