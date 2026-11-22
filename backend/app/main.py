from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text, select, func
from .config import Settings
from .db import build_engine, migrate
from .models import engagements, findings, credit_ledger
from .presets import load_fixtures, seed_replay_cache
from .schemas import Health, Preset, FirmMetrics


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        engine = build_engine(settings)
        app.state.engine = engine
        try:
            await migrate(engine)
            if settings.olostep_mode == "replay":
                await seed_replay_cache(engine)
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Kalki LLP API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
        allow_origin_regex=settings.allowed_origin_regex, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"], allow_credentials=False)

    async def credits_reserved(conn):
        return int((await conn.execute(select(func.coalesce(func.sum(credit_ledger.c.credits_consumed), 0)))).scalar_one())

    @app.get("/health", response_model=Health)
    async def health():
        try:
            async with app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                spent = await credits_reserved(conn)
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable", "db": "disconnected", "olostep_mode": settings.olostep_mode})
        return Health(olostep_mode=settings.olostep_mode, budget_remaining=max(0, 5000-spent))

    @app.get("/api/presets", response_model=list[Preset])
    async def presets():
        return [fixture.preset for fixture in load_fixtures()]

    @app.get("/api/metrics/firm", response_model=FirmMetrics)
    async def firm_metrics():
        async with app.state.engine.connect() as conn:
            total = (await conn.execute(select(func.count()).select_from(engagements))).scalar_one()
            pending = (await conn.execute(select(func.count()).select_from(engagements).where(
                engagements.c.status == "PENDING_PARTNER_REVIEW"))).scalar_one()
            count = (await conn.execute(select(func.count()).select_from(findings))).scalar_one()
            spent = await credits_reserved(conn)
        return FirmMetrics(engagements=total, pending_partner_review=pending, findings=count,
            credits_reserved=spent, budget_remaining=max(0, 5000-spent))
    return app


app = create_app()
