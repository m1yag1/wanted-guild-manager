from datetime import UTC, datetime
from pathlib import Path

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig
from sqlalchemy import select, text

from wgm.db.config import database_config
from wgm.db.models import Event, Signup, SignupStatus

STARTS = datetime(2026, 12, 5, 20, 0, tzinfo=UTC)


@pytest.fixture
def config(tmp_path: Path) -> SQLAlchemyAsyncConfig:
    """A migrated database. Migrations run before the async test starts."""
    config = database_config(f"sqlite+aiosqlite:///{tmp_path / 'models.db'}")
    AlembicCommands(sqlalchemy_config=config).upgrade()
    return config


@pytest.mark.anyio
async def test_events_keep_their_signups_and_delete_them(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        event = Event(
            guild_id="1",
            title="Siege night",
            starts_at=STARTS,
            created_by="42",
        )
        event.signups.append(
            Signup(
                user_id="7",
                character_name="Kael",
                status=SignupStatus.ATTENDING,
                role="Tank",
            )
        )
        event.signups.append(
            Signup(
                user_id="8",
                character_name="Mira",
                status=SignupStatus.NOT_ATTENDING,
            )
        )
        session.add(event)
        await session.commit()

        stored = await session.get(Event, event.id)
        assert stored is not None
        assert stored.starts_at == STARTS
        assert [(s.character_name, s.status, s.role) for s in stored.signups] == [
            ("Kael", SignupStatus.ATTENDING, "Tank"),
            ("Mira", SignupStatus.NOT_ATTENDING, None),
        ]
        raw = await session.execute(text("select status from signup order by user_id"))
        assert raw.scalars().all() == ["attending", "not_attending"]

        await session.delete(stored)
        await session.commit()
        assert (await session.execute(select(Signup))).scalars().all() == []
