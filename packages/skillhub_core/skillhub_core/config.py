"""Runtime configuration, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings resolved from the environment (and an optional .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    anthropic_api_key: str = ""
    skillhub_llm_model: str = "claude-sonnet-5"
    skillhub_llm_temperature: float = 0.0
    skillhub_llm_max_tokens: int = 4096

    # --- Embeddings ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- Database ---
    postgres_user: str = "skillhub"
    postgres_password: str = "skillhub"
    postgres_db: str = "skillhub"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # --- API ---
    skillhub_cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.skillhub_cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
