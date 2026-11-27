from datetime import UTC, datetime, timedelta

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.db.config import database_config
from wgm.db.models import Event
from wgm.domain.events.services import EventService

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def config(database_url: str) -> SQLAlchemyAsyncConfig:
    config = database_config(database_url)
    AlembicCommands(sqlalchemy_config=config).upgrade()
    return config


def _event(title: str, hours: int, guild: str = "1", **extra: object) -> Event:
    return Event(
        guild_id=guild,
        title=title,
        event_type="Siege",
        starts_at=NOW + timedelta(hours=hours),
        created_by="42",
        **extra,
    )


@pytest.mark.anyio
async def test_upcoming_lists_future_events_in_this_server_soonest_first(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        events = EventService(session=session)
        for event in [
            _event("Later", 48),
            _event("Sooner", 2),
            _event("Past", -2),
            _event("Other server", 3, guild="2"),
            _event("Cancelled", 4, cancelled_at=NOW),
        ]:
            await events.create(event)

        upcoming = await events.upcoming("1", NOW)

    assert [event.title for event in upcoming] == ["Sooner", "Later"]
