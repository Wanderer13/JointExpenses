from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    APP_ENV_PRODUCTION,
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_APP_ENV,
    DEFAULT_AUTH_RATE_LIMIT_PER_MINUTE,
    DEFAULT_FRONTEND_URL,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
    DEFAULT_REMINDER_CHECK_SECONDS,
    DEFAULT_SECRET,
    DEFAULT_SMTP_PORT,
    MAIL_BACKEND_SMTP,
    MAIL_BACKEND_STUB,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = DEFAULT_APP_ENV
    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'expenses.db'}"
    secret_key: str = DEFAULT_SECRET
    access_token_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
    # Public UI origin for invite/reminder links in emails (no trailing slash).
    frontend_url: str = DEFAULT_FRONTEND_URL
    upload_dir: str = str(Path(__file__).resolve().parent.parent / "uploads")
    mail_outbox_dir: str = str(Path(__file__).resolve().parent.parent / "mail_outbox")
    reminder_check_seconds: int = DEFAULT_REMINDER_CHECK_SECONDS
    google_client_id: str = ""
    mail_backend: str = MAIL_BACKEND_STUB
    smtp_host: str = ""
    smtp_port: int = DEFAULT_SMTP_PORT
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    cookie_secure: bool = False
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    auth_rate_limit_per_minute: int = DEFAULT_AUTH_RATE_LIMIT_PER_MINUTE
    # Comma-separated emails granted AppRole.admin on register / Google create / seed.
    admin_emails: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def public_frontend_url(self) -> str:
        url = (self.frontend_url or "").strip().rstrip("/")
        if url:
            return url
        origins = self.cors_origin_list
        return origins[0].rstrip("/") if origins else DEFAULT_FRONTEND_URL

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == APP_ENV_PRODUCTION

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.is_production:
            if not self.secret_key or self.secret_key == DEFAULT_SECRET:
                raise ValueError("SECRET_KEY must be set to a strong value when APP_ENV=production")
            if self.mail_backend == MAIL_BACKEND_SMTP and not self.smtp_host:
                raise ValueError("SMTP_HOST is required when MAIL_BACKEND=smtp in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
