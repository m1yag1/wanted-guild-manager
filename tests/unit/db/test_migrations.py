import sqlite3
from pathlib import Path

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.db.config import database_config


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "migrations.db"


@pytest.fixture
def commands(db_file: Path) -> AlembicCommands:
    return AlembicCommands(
        sqlalchemy_config=database_config(f"sqlite+aiosqlite:///{db_file}")
    )


def _tables(db_file: Path) -> set[str]:
    with sqlite3.connect(db_file) as db:
        rows = db.execute("select name from sqlite_master where type = 'table'")
        return {name for (name,) in rows}


def test_upgrade_creates_the_tables(commands: AlembicCommands, db_file: Path) -> None:
    commands.upgrade()

    assert {"event", "signup", "ddl_version"} <= _tables(db_file)


def test_models_match_the_migrations(commands: AlembicCommands) -> None:
    """Fails when a model changes without a migration (run make-migrations)."""
    commands.upgrade()

    commands.check()


def test_downgrade_removes_the_tables(commands: AlembicCommands, db_file: Path) -> None:
    commands.upgrade()

    commands.downgrade("base")

    assert not {"event", "signup"} & _tables(db_file)


def test_config_points_at_the_packaged_migrations(database_url: str) -> None:
    config: SQLAlchemyAsyncConfig = database_config(database_url)

    assert config.alembic_config.script_location.endswith("wgm/db/migrations")
