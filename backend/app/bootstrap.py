"""Create tables and directories. Used by Docker CMD."""

from pathlib import Path

from app.config import get_settings
from app.database import Base, engine


def main() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.mail_outbox_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print("Database ready.")


if __name__ == "__main__":
    main()
