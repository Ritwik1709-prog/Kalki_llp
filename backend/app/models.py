"""Portable SQLAlchemy Core models, used through async connections/sessions.

Legacy evidence and approval columns remain intact for migration compatibility.
UTC timestamps are ISO-8601 strings, avoiding SQLite/PostgreSQL timezone drift.
"""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (MetaData, Table, Column, String, Integer, Float, Boolean,
                        JSON, Text, ForeignKey, CheckConstraint, Enum)
from typing import get_args
from .schemas import Framework, EngagementStatus, FindingStatus, Severity, GateStatus

metadata = MetaData()

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def identifier():
    return str(uuid4())

def id_column():
    return Column("id", String, primary_key=True, default=identifier)

def engagement_fk():
    return Column("engagement_id", String, ForeignKey("engagements.id"), nullable=False, index=True)

def timestamp(name="created_at"):
    return Column(name, String, nullable=False, default=utcnow, server_default="1970-01-01T00:00:00+00:00")

def enum_type(literal):
    return Enum(*get_args(literal), native_enum=False, validate_strings=True)

engagements = Table("engagements", metadata,
    id_column(), Column("status", enum_type(EngagementStatus), nullable=False, server_default="DRAFT"),
    Column("version", Integer, nullable=False, default=1, server_default="1"), Column("data", JSON),
    Column("code", String, unique=True), Column("vendor_name", String), Column("target_url", Text),
    Column("framework", enum_type(Framework), CheckConstraint("framework IN ('DPDP','GDPR','SOC2')")),
    Column("questionnaire_json", JSON), Column("risk_score", Integer, CheckConstraint("risk_score BETWEEN 0 AND 100")),
    Column("credits_used", Integer, CheckConstraint("credits_used BETWEEN 0 AND 25"), nullable=False, server_default="0"),
    Column("duration_ms", Integer), timestamp(), timestamp("updated_at"))

agent_steps = Table("agent_steps", metadata, id_column(), engagement_fk(),
    Column("stage", String, nullable=False), Column("event_type", String, nullable=False),
    Column("message", Text, nullable=False), Column("payload_json", JSON),
    Column("credits_delta", Integer, nullable=False, server_default="0"), Column("latency_ms", Integer), timestamp())

evidence_items = Table("evidence_items", metadata, id_column(), engagement_fk(),
    Column("source_url", Text, nullable=False), Column("page_type", String, nullable=False),
    Column("markdown_content", Text, nullable=False), Column("content_sha256", String(64), nullable=False),
    Column("injection_detected", Boolean, nullable=False), Column("cache_hit", Boolean, nullable=False),
    Column("cache_key_sha256", String(64), nullable=False), Column("retrieved_at", String, nullable=False),
    Column("provenance", String, nullable=False), timestamp())

findings = Table("findings", metadata, id_column(), engagement_fk(),
    Column("severity", enum_type(Severity), nullable=False), Column("citations", JSON, nullable=False), Column("data", JSON),
    Column("control_id", String), Column("claim_text", Text),
    Column("status", enum_type(FindingStatus), CheckConstraint("status IN ('VERIFIED','CONTRADICTED','UNVERIFIED')"), server_default="UNVERIFIED"),
    Column("verbatim_quote", Text), Column("source_url", Text),
    Column("confidence", Float, CheckConstraint("confidence BETWEEN 0 AND 1")),
    Column("redline_original", Text), Column("redline_proposed", Text),
    Column("partner_status", enum_type(GateStatus), server_default="PENDING"))

approval_gates = Table("approval_gates", metadata, id_column(), engagement_fk(),
    Column("status", enum_type(GateStatus), nullable=False), Column("reviewer", String), Column("reviewed_version", Integer),
    Column("reviewed_at", String), Column("rationale", Text), Column("partner_notes", Text),
    Column("decided_by", String), Column("decided_at", String), Column("evidence_version", String))

audit_logs = Table("audit_logs", metadata, id_column(),
    Column("engagement_id", String, ForeignKey("engagements.id")), timestamp(),
    Column("event", JSON, nullable=False), Column("issuer", String, nullable=False, server_default="Kalki LLP"),
    Column("actor", String), Column("action", String), Column("payload_json", JSON),
    Column("prev_hash", String(64)), Column("entry_hash", String(64)))

olostep_cache = Table("olostep_cache", metadata,
    Column("cache_key_sha256", String(64), primary_key=True),
    Column("retrieved_at", String, nullable=False), Column("source_url", Text, nullable=False),
    Column("response", JSON, nullable=False), Column("endpoint", String), Column("request_url", Text),
    Column("response_json", JSON), Column("provenance", String, nullable=False, server_default="legacy"), timestamp())

credit_ledger = Table("credit_ledger", metadata, id_column(), engagement_fk(),
    Column("endpoint", String, nullable=False),
    Column("credits_consumed", Integer, CheckConstraint("credits_consumed BETWEEN 0 AND 25"), nullable=False),
    Column("cache_hit", Boolean, nullable=False), Column("mode", String, nullable=False),
    Column("latency_ms", Integer), Column("status_code", Integer),
    Column("outcome", String, nullable=False, server_default="reserved"), timestamp())
