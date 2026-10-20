from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{Path(__file__).resolve().parent.parent / 'expenses.db'}"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = str(Path(__file__).resolve().parent.parent / "uploads")
    mail_outbox_dir: str = str(Path(__file__).resolve().parent.parent / "mail_outbox")
    reminder_check_seconds: int = 60
    google_client_id: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
