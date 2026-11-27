"""SQLAlchemy and Alembic configuration for Advanced Alchemy."""

from pathlib import Path

from advanced_alchemy.extensions.litestar import (
    AlembicAsyncConfig,
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def database_config(url: str) -> SQLAlchemyAsyncConfig:
    """Database configuration for a SQLAlchemy URL, with migrations in this package."""
    return SQLAlchemyAsyncConfig(
        connection_string=url,
        before_send_handler="autocommit",
        session_config=AsyncSessionConfig(expire_on_commit=False),
        alembic_config=AlembicAsyncConfig(
            script_location=str(MIGRATIONS_DIR),
            script_config=str(MIGRATIONS_DIR / "alembic.ini"),
            version_table_name="ddl_version",
        ),
    )
