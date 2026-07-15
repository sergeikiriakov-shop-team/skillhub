"""Runtime configuration, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Google OpenID Connect endpoints (fixed; not configurable).
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class Settings(BaseSettings):
    """Application settings resolved from the environment (and an optional .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # Public base URL the browser reaches SkillHub at (same origin as the SPA). Used to build the
    # OAuth redirect URI and the device-flow verification URL. Dev default = the Vite proxy origin.
    skillhub_public_url: str = "http://localhost:5173"

    # --- Auth: Google OAuth (browser login) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    # Exact redirect URI registered in Google Cloud Console. Empty → derived from public_url.
    google_redirect_uri: str = ""

    # --- Auth: sessions / roles ---
    # Session cookie lifetime (seconds); default 14 days.
    skillhub_session_ttl: int = 14 * 24 * 3600
    # Role assigned to a brand-new Google user (validated against ROLES at use site).
    skillhub_default_role: str = "viewer"
    # Comma-separated emails promoted to admin on their (verified) first login.
    skillhub_bootstrap_admins: str = ""
    # Set True in production (HTTPS) so cookies carry the Secure flag. Must be False on http://localhost.
    skillhub_cookie_secure: bool = False
    # Deprecated break-glass admin token (minted into auth_tokens on boot). Prefer bootstrap admins.
    skillhub_admin_token: str = ""

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
    def effective_redirect_uri(self) -> str:
        """The OAuth callback URL — explicit override, else derived from the public URL."""
        if self.google_redirect_uri:
            return self.google_redirect_uri
        return f"{self.skillhub_public_url.rstrip('/')}/api/auth/callback"

    @property
    def bootstrap_admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.skillhub_bootstrap_admins.split(",") if e.strip()}

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
