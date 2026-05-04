from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLMS_GEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Render / dashboards often define a key with an empty value; without this, bool/int
        # fields raise ValidationError at startup (then uvicorn shows CancelledError on shutdown).
        env_ignore_empty=True,
    )

    database_url: str = "sqlite+aiosqlite:///./llms_gen.db"
    # When non-empty, all /api/* routes require X-LLMS-GEN-API-Key or Authorization: Bearer (same value).
    api_key: str = ""
    # When False, OpenAPI schema and /docs are disabled (recommended alongside api_key on public hosts).
    expose_openapi: bool = True
    crawl_user_agent: str = "llms-gen/0.1 (https://github.com/llms-gen/llms-gen; automated llms.txt generator)"
    max_pages_per_job: int = 60
    fetch_timeout_s: float = 20.0
    max_response_bytes: int = 2_097_152
    monitor_enabled: bool = True
    monitor_poll_interval_s: int = 300
    # Optional absolute base for artifact links in webhook payloads, e.g. https://your-app.example.com
    public_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
