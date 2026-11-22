from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./kalki_local.db"
    olostep_mode: Literal["replay", "record", "live"] = "replay"
    olostep_api_key: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")
    allowed_origins: str = "http://localhost:5173"
    allowed_origin_regex: str | None = None
    render: bool = False
    app_env: str = "development"
    llm_model: str = "gemini-3.8-flash"
    llm_fast_model: str = "gemini-3.5-flash-lite"

    @property
    def origins(self):
        return [x.strip().rstrip("/") for x in self.allowed_origins.split(",") if x.strip()]
