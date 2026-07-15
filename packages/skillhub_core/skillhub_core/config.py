"""Runtime configuration, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The OAuth identity provider used for browser login. The auth layer is provider-agnostic
# (SkillHub is its own authorization server); only /login and /callback are provider-specific.
AUTH_PROVIDER = "github"

# GitHub OAuth endpoints (fixed; not configurable).
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


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

    # --- Auth: GitHub OAuth (browser login) ---
    github_client_id: str = ""
    github_client_secret: str = ""
    # Exact callback URL registered in the GitHub OAuth App. Empty → derived from public_url.
    oauth_redirect_uri: str = ""

    # --- Auth: sessions / roles ---
    # Session cookie lifetime (seconds); default 14 days.
    skillhub_session_ttl: int = 14 * 24 * 3600
    # Role assigned to a brand-new user (validated against ROLES at use site).
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
        if self.oauth_redirect_uri:
            return self.oauth_redirect_uri
        return f"{self.skillhub_public_url.rstrip('/')}/api/auth/callback"

    @property
    def bootstrap_admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.skillhub_bootstrap_admins.split(",") if e.strip()}

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
