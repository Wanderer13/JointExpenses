"""Idempotent schema tweaks for existing DBs (create_all does not alter columns)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def migrate_schema(engine: Engine) -> None:
    if engine.dialect.name == "sqlite":
        _migrate_sqlite(engine)
    elif engine.dialect.name == "postgresql":
        _migrate_postgres(engine)


def _migrate_sqlite(engine: Engine) -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "users" not in tables:
            return

        cols = {row[1]: row for row in conn.execute(text("PRAGMA table_info(users)"))}
        if "google_sub" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)"))
            cols = {row[1]: row for row in conn.execute(text("PRAGMA table_info(users)"))}

        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users(google_sub)"))

        pw = cols.get("password_hash")
        if pw is not None and pw[3] == 1:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(
                text(
                    """
                    CREATE TABLE users_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        name VARCHAR(120) NOT NULL,
                        password_hash VARCHAR(255),
                        google_sub VARCHAR(255),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO users_new (id, email, name, password_hash, google_sub, created_at)
                    SELECT id, email, name, password_hash, google_sub, created_at FROM users
                    """
                )
            )
            conn.execute(text("DROP TABLE users"))
            conn.execute(text("ALTER TABLE users_new RENAME TO users"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users(google_sub)"))
            conn.execute(text("PRAGMA foreign_keys=ON"))


def _migrate_postgres(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users(google_sub)"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
