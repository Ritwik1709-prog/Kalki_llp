import pytest


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    """Tests must never inherit production DB settings or paid-service modes."""
    for name in ("DATABASE_URL", "RENDER", "APP_ENV", "OLOSTEP_MODE", "ALLOWED_ORIGINS", "ALLOWED_ORIGIN_REGEX"):
        monkeypatch.delenv(name, raising=False)
