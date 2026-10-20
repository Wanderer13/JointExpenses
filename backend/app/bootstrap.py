"""Run Alembic migrations and ensure directories. Used by Docker CMD."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import get_settings


def run_migrations() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


def main() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.mail_outbox_dir).mkdir(parents=True, exist_ok=True)
    run_migrations()
    print("Database ready.")


if __name__ == "__main__":
    main()
