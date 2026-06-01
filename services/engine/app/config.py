"""Central settings. All secrets/keys live here (server-side only) and are read
from the environment — never hardcoded, never shipped to the browser
(CLAUDE.md §1.4, §4, §9)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ── LLM providers (server-side only) ─────────────────────────────────────
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    llm_offline: bool = Field(default=False, alias="LLM_OFFLINE")
    llm_default_provider: str = Field(default="anthropic", alias="LLM_DEFAULT_PROVIDER")

    # Model IDs (overridable; verify against current docs before changing).
    model_deep_anthropic: str = Field(default="claude-opus-4-8", alias="MODEL_DEEP_ANTHROPIC")
    model_medium_anthropic: str = Field(default="claude-sonnet-4-6", alias="MODEL_MEDIUM_ANTHROPIC")
    model_low_anthropic: str = Field(default="claude-haiku-4-5", alias="MODEL_LOW_ANTHROPIC")
    model_deep_google: str = Field(default="gemini-3.1-pro-preview", alias="MODEL_DEEP_GOOGLE")
    model_medium_google: str = Field(default="gemini-3.5-flash", alias="MODEL_MEDIUM_GOOGLE")
    model_low_google: str = Field(default="gemini-3.1-flash-lite", alias="MODEL_LOW_GOOGLE")

    # ── Datastores ───────────────────────────────────────────────────────────
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="chainos-dev-pw", alias="NEO4J_PASSWORD")
    neo4j_staging_db: str = Field(default="staging", alias="NEO4J_STAGING_DB")
    neo4j_production_db: str = Field(default="production", alias="NEO4J_PRODUCTION_DB")

    database_url: str = Field(
        default="postgresql+psycopg://chainos:chainos-dev-pw@localhost:5432/chainos",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    vector_backend: str = Field(default="pgvector", alias="VECTOR_BACKEND")
    pinecone_api_key: str | None = Field(default=None, alias="PINECONE_API_KEY")

    # ── Market data ──────────────────────────────────────────────────────────
    market_data_api_key: str | None = Field(default=None, alias="MARKET_DATA_API_KEY")
    market_data_mode: str = Field(default="delayed", alias="MARKET_DATA_MODE")

    @property
    def offline(self) -> bool:
        """Use the deterministic offline provider when explicitly set OR when no
        provider key is configured (so the stack always boots)."""
        return self.llm_offline or not (self.anthropic_api_key or self.google_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
