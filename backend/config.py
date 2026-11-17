"""TrainBench Configuration Settings."""
from pathlib import Path
from typing import List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TrainBench"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # API and Server
    api_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    # Must be set to true to bind to a non-loopback address (LAN, tunnel, public).
    # The app has no real authentication yet — exposing it is unsafe.
    allow_public_bind: bool = False
    allowed_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

    # Storage and Database
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    artifacts_dir: Path = data_dir / "artifacts"
    database_url: str = f"sqlite+aiosqlite:///{data_dir / 'trainbench.db'}"

    # Execution limits
    max_epochs: int = 1000
    max_concurrent_runs: int = 4
    max_batch_size: int = 4096
    min_batch_size: int = 1
    max_learning_rate: float = 10.0
    min_learning_rate: float = 1e-6
    default_page_size: int = 50
    max_page_size: int = 200

    # Security & Auth
    auth_enabled: bool = False
    default_user_id: str = "user-local"
    jwt_secret_key: Optional[str] = None
    # Optional shared-secret API key. When set, every /api request must send it
    # via the X-API-Key header or "Authorization: Bearer <key>".
    api_key: Optional[str] = None

    # Debug/sensitive endpoints (/docs, /openapi.json, /diagnostics).
    # Keep enabled for local development; disable when self-hosting.
    expose_api_docs: bool = True
    expose_diagnostics: bool = True

    # Simple per-IP rate limit for write (non-GET) API requests per minute.
    rate_limit_per_minute: int = 30

    # Dataset limits
    max_dataset_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_dataset_formats: List[str] = ["csv", "json"]

    @model_validator(mode="after")
    def _require_jwt_secret_when_auth_enabled(self) -> "Settings":
        if self.auth_enabled and not self.jwt_secret_key:
            raise ValueError(
                "TRAINBENCH_JWT_SECRET_KEY must be set when TRAINBENCH_AUTH_ENABLED=true"
            )
        return self

    model_config = SettingsConfigDict(
        env_prefix="TRAINBENCH_",
        # backend/.env is a fallback; a .env in the working directory (project
        # root) takes precedence. Keys in env files also need the TRAINBENCH_ prefix.
        env_file=(str(Path(__file__).resolve().parent / ".env"), ".env"),
        extra="ignore"
    )


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
