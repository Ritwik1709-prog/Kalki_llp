"""Database is the event log. Bounded queues are wake-up signals, never truth."""
import asyncio
from collections import defaultdict
import hashlib
import json
from sqlalchemy import select, update
from ..models import engagements, agent_steps, audit_logs, identifier, utcnow

TERMINAL = {"AWAITING_PARTNER_REVIEW", "PENDING_PARTNER_REVIEW", "DELIVERED", "REJECTED", "FAILED_GRACEFULLY"}

class EventBus:
    def __init__(self, engine):
        self.engine = engine
        self.subscribers = defaultdict(set)

    async def emit(self, engagement_id, stage, message, *, event_type="step", payload=None,
                   status=None, credits_delta=0, latency_ms=None, values=None, mutate=None):
        async with self.engine.begin() as conn:
            changes = dict(values or {}, event_seq=engagements.c.event_seq+1, updated_at=utcnow())
            if status:
                changes["status"] = status
            row = (await conn.execute(update(engagements).where(engagements.c.id == engagement_id,
                engagements.c.status.not_in(TERMINAL))
                .values(**changes).returning(engagements.c.event_seq, engagements.c.audit_head))).mappings().one()
            if mutate:
                await mutate(conn)
            step = dict(id=identifier(), engagement_id=engagement_id, sequence=row["event_seq"],
                stage=stage,event_type=event_type,message=message,payload_json=payload or {},
                credits_delta=credits_delta,latency_ms=latency_ms,created_at=utcnow())
            await conn.execute(agent_steps.insert().values(**step))
            previous = row["audit_head"] or "0"*64
            digest = hashlib.sha256((previous + json.dumps(step,sort_keys=True,separators=(",",":"))).encode()).hexdigest()
            await conn.execute(audit_logs.insert().values(engagement_id=engagement_id,actor="system",
                action=event_type,event=step,payload_json=step,prev_hash=previous,entry_hash=digest))
            await conn.execute(update(engagements).where(engagements.c.id == engagement_id).values(audit_head=digest))
        for queue in tuple(self.subscribers.get(engagement_id, ())):
            if not queue.full():
                queue.put_nowait(True)
        return step

    async def stream(self, engagement_id, after=0):
        queue = asyncio.Queue(maxsize=1)
        self.subscribers[engagement_id].add(queue)  # Subscribe before querying persisted history.
        cursor = after
        try:
            while True:
                async with self.engine.connect() as conn:
                    rows = (await conn.execute(select(agent_steps).where(agent_steps.c.engagement_id == engagement_id,
                        agent_steps.c.sequence > cursor).order_by(agent_steps.c.sequence).limit(100))).mappings().all()
                    state = (await conn.execute(select(engagements.c.status,engagements.c.event_seq)
                        .where(engagements.c.id == engagement_id))).mappings().one()
                for row in rows:
                    cursor = row["sequence"]
                    yield f"id: {cursor}\nevent: agent_step\ndata: {json.dumps(dict(row),ensure_ascii=True)}\n\n"
                if cursor >= state["event_seq"] and state["status"] in TERMINAL:
                    return
                if rows:
                    continue
                try:
                    await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    pass  # Reconcile events from another process or a lost wake-up.
        finally:
            self.subscribers[engagement_id].discard(queue)
            if not self.subscribers[engagement_id]:
                del self.subscribers[engagement_id]
