from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .config import Settings
from .db import build_engine, migrate


def create_app(settings=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        engine = build_engine(settings)
        app.state.engine = engine
        try:
            await migrate(engine)
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Kalki LLP API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins,
        allow_origin_regex=settings.allowed_origin_regex, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"], allow_credentials=False)

    @app.get("/health")
    async def health():
        try:
            async with app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable", "db": "disconnected", "olostep_mode": settings.olostep_mode})
        return {"status": "ok", "db": "connected", "olostep_mode": settings.olostep_mode}
    return app


app = create_app()
