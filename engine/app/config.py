from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = "http://127.0.0.1:54321"
    # Secret (service) key: used ONLY for Auth-admin (invites) and Storage calls. Never sent to clients.
    supabase_secret_key: str = ""
    supabase_publishable_key: str = ""
    # Legacy HS256 secret, used only if a token is HS256-signed. Asymmetric tokens are verified via JWKS.
    supabase_jwt_secret: str = ""
    # Connects as the `engine_app` role (see supabase/migrations/*_foundation.sql).
    database_url: str = "postgresql://engine_app:engine_app_local_only@127.0.0.1:54322/postgres"

    web_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    storage_bucket: str = "uploads"
    max_upload_rows: int = 20000
    max_upload_bytes: int = 20 * 1024 * 1024

    # AIProvider: "anthropic" or "none". AI only extracts/suggests; it never produces a saved number.
    ai_provider: str = "anthropic"
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    @field_validator("supabase_url")
    @classmethod
    def _bare_project_url(cls, v: str) -> str:
        """Accept the dashboard's API URL too (".../rest/v1/"): every client here appends its own path."""
        v = v.strip().rstrip("/")
        return v.removesuffix("/rest/v1").rstrip("/")

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
