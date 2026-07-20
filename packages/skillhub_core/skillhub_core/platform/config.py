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
# Repository visibility for the authenticated user: 200 if the token's user can access the repo
# (collaborator/owner), 404 if not. Needs the `repo` scope for a private repo; format with owner/repo.
GITHUB_REPO_URL = "https://api.github.com/repos/{repo}"


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
    # Restrict access to people who can access this GitHub repository ("owner/repo", e.g.
    # "prologisticsbeliani/prologistics") — repo access == service access. Empty → any GitHub account
    # may sign in. When set, login also requests the `repo` scope and rejects non-collaborators at the
    # callback (admins bypass).
    skillhub_allowed_repo: str = ""

    # --- Auth: sessions / roles ---
    # When False, even reads (catalog/search/stats/…) require a logged-in user; only health and the
    # auth endpoints stay open. True keeps the catalog world-readable (default; dev convenience).
    skillhub_public_reads: bool = True
    # Session cookie lifetime (seconds); default 14 days.
    skillhub_session_ttl: int = 14 * 24 * 3600
    # OAuth access-token lifetime (seconds) for the remote HTTP MCP; default 30 days. A paired
    # refresh token (non-expiring) lets the client mint a fresh access token without re-login.
    skillhub_oauth_access_ttl: int = 30 * 24 * 3600
    # Role assigned to a brand-new user (validated against ROLES at use site).
    skillhub_default_role: str = "viewer"
    # Task Review: when True (default, early phase), ANY authenticated user may post a review verdict
    # ("anyone can be the lead"). Set False once a fixed lead exists — then only users flagged
    # ``is_reviewer`` (or admins) may review.
    skillhub_open_review: bool = True
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

    @property
    def allowed_repo(self) -> str:
        """The gating repo as "owner/repo", trimmed. Empty = no restriction."""
        return self.skillhub_allowed_repo.strip().strip("/")

    @property
    def access_restricted(self) -> bool:
        return bool(self.allowed_repo)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
