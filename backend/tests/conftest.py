import pytest


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    """Tests must never inherit production DB settings or paid-service modes."""
    for name in ("DATABASE_URL", "RENDER", "APP_ENV", "OLOSTEP_MODE", "ALLOWED_ORIGINS", "ALLOWED_ORIGIN_REGEX", "OLOSTEP_API_KEY", "LLM_API_KEY", "LLM_MODEL", "LLM_FAST_MODEL", "LLM_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_MODE", "mock")


@pytest.fixture(autouse=True)
def no_paid_transport(monkeypatch):
    import httpx
    async def blocked(*args, **kwargs):
        raise AssertionError("Real HTTP transport forbidden in routine tests")
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)
