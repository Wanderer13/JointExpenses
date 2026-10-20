from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'expenses.db'}"
    secret_key: str = DEFAULT_SECRET
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
    upload_dir: str = str(Path(__file__).resolve().parent.parent / "uploads")
    mail_outbox_dir: str = str(Path(__file__).resolve().parent.parent / "mail_outbox")
    reminder_check_seconds: int = 60
    google_client_id: str = ""
    mail_backend: str = "stub"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True
    cookie_secure: bool = False
    max_upload_bytes: int = 5 * 1024 * 1024
    auth_rate_limit_per_minute: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.is_production:
            if not self.secret_key or self.secret_key == DEFAULT_SECRET:
                raise ValueError("SECRET_KEY must be set to a strong value when APP_ENV=production")
            if self.mail_backend == "smtp" and not self.smtp_host:
                raise ValueError("SMTP_HOST is required when MAIL_BACKEND=smtp in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
