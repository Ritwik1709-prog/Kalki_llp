import asyncio
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Request, HTTPException, Query, Header
from pydantic import Field, model_validator, field_validator
from sqlalchemy import select, func
from ..schemas import StrictModel, Framework, Claim
from ..models import engagements, agent_steps, evidence_items, findings, approval_gates, audit_logs, identifier
from ..presets import load_fixtures
from ..services.olostep_gateway import url_host, UnsafeURL
from ..streaming import sse_response
from .responses import CreatedEngagement,QueueResponse,DetailResponse

router = APIRouter(prefix="/api/engagements", tags=["engagements"])

class CreateEngagement(StrictModel):
    preset_id: str | None = None
    vendor_name: str | None = Field(default=None,min_length=1,max_length=150)
    target_url: str | None = Field(default=None,max_length=2048)
    framework: Framework | None = None
    questionnaire: list[Claim] | None = Field(default=None,min_length=1,max_length=30)
    mode_override: Literal["replay","record","live"] | None = None

    @field_validator("framework",mode="before")
    @classmethod
    def normalize_framework(cls,value):
        return value.strip().upper() if isinstance(value,str) else value

    @model_validator(mode="after")
    def selection(self):
        custom = [self.vendor_name,self.target_url,self.framework,self.questionnaire]
        if self.preset_id:
            if any(value is not None for value in custom):
                raise ValueError("Choose a preset OR custom fields")
        elif any(value is None for value in custom):
            raise ValueError("Custom engagement requires all vendor and questionnaire fields")
        if self.questionnaire:
            if len({c.control_id for c in self.questionnaire}) != len(self.questionnaire):
                raise ValueError("Control IDs must be unique")
            if any(not c.text.strip() or len(c.text)>10000 or not c.control_id.strip() or len(c.control_id)>100 for c in self.questionnaire):
                raise ValueError("Claims must be nonempty and bounded")
        return self

async def engagement(request,eid):
    async with request.app.state.engine.connect() as conn:
        row = (await conn.execute(select(engagements).where(engagements.c.id==eid))).mappings().first()
    if row is None:
        raise HTTPException(404,"Engagement not found")
    return dict(row)

@router.post("",status_code=202,response_model=CreatedEngagement)
async def create(body: CreateEngagement, request: Request):
    settings = request.app.state.settings
    if body.mode_override is not None and settings.olostep_mode != "live":
        raise HTTPException(403,"Mode override requires server live mode")
    preset = None
    if body.preset_id:
        preset = next((f.preset for f in load_fixtures() if f.preset.id==body.preset_id),None)
        if preset is None:
            raise HTTPException(404,"Preset not found")
        if body.mode_override not in {None,"replay"}:
            raise HTTPException(422,"Synthetic presets require replay mode")
    name,url,framework,claims = (preset.vendor_name,preset.target_url,preset.framework,preset.questionnaire) if preset else (
        body.vendor_name,body.target_url,body.framework,body.questionnaire)
    try:
        url_host(url)
        for claim in claims:
            url_host(claim.source_url)
    except UnsafeURL:
        raise HTTPException(422,"Invalid public vendor or claim URL") from None
    eid = identifier()
    row = dict(id=eid,code=f"KLK-{datetime.now(timezone.utc).year}-{eid[:8].upper()}",vendor_name=name,
        target_url=url,framework=framework,questionnaire_json=[claim.model_dump() for claim in claims],status="DRAFT",
        data={"preset_id":body.preset_id,"synthetic":preset is not None,"mode":"replay" if preset else body.mode_override or settings.olostep_mode,
              "signed":False,"release_authorized":False})
    async with request.app.state.engine.begin() as conn:
        await conn.execute(engagements.insert().values(**row))
    task = asyncio.create_task(request.app.state.orchestrator.run(eid))
    request.app.state.tasks.add(task)
    def completed(task):
        request.app.state.tasks.discard(task)
        if not task.cancelled():
            task.exception()  # Consume errors without leaking sensitive exceptions.
    task.add_done_callback(completed)
    return {"id":eid,"code":row["code"],"status":"DRAFT","stream_url":f"/api/engagements/{eid}/stream"}

@router.get("",response_model=QueueResponse)
async def listing(request:Request, limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    async with request.app.state.engine.connect() as conn:
        count = (await conn.execute(select(func.count()).select_from(engagements))).scalar_one()
        rows = (await conn.execute(select(engagements.c.id,engagements.c.code,engagements.c.vendor_name,
            engagements.c.framework,engagements.c.status,engagements.c.risk_score,engagements.c.credits_used,
            engagements.c.duration_ms,engagements.c.created_at).order_by(engagements.c.created_at.desc(),engagements.c.id).limit(limit).offset(offset))).mappings().all()
        statuses = (await conn.execute(select(engagements.c.status,func.count()).group_by(engagements.c.status))).all()
    return {"items":[dict(row) for row in rows],"total":count,"limit":limit,"offset":offset,"summary":dict(statuses)}

@router.get("/{eid}/stream")
async def stream(eid:str,request:Request,last_event_id:str|None=Header(default=None)):
    row = await engagement(request,eid)
    try:
        after = int(last_event_id) if last_event_id is not None else 0
        if not 0 <= after <= row["event_seq"]:
            raise ValueError
    except ValueError:
        raise HTTPException(422,"Invalid Last-Event-ID") from None
    return sse_response(request.app.state.event_bus.stream(eid,after))

@router.get("/{eid}",response_model=DetailResponse)
async def detail(eid:str,request:Request):
    row = await engagement(request,eid)
    result = {"engagement":row}
    async with request.app.state.engine.connect() as conn:
        for key,table in [("steps",agent_steps),("evidence",evidence_items),("findings",findings),
                          ("approval_gates",approval_gates),("audit_logs",audit_logs)]:
            query = select(table).where(table.c.engagement_id==eid)
            if table is agent_steps:
                query = query.order_by(table.c.sequence)
            elif "created_at" in table.c:
                query = query.order_by(table.c.created_at,table.c.id)
            result[key] = [dict(r) for r in (await conn.execute(query)).mappings()]
    result["approval_gate"] = next((g for g in result["approval_gates"] if g["status"]=="PENDING"),None)
    return result
