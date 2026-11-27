"""Lock event posts once sign-ups close.

A press after closing is already refused. This job also greys out the buttons
and changes "Sign-ups close" to "Sign-ups closed" on the post itself, so
members can see it without pressing anything.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import NoReturn

from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.domain.discord.client import DiscordApiError, DiscordClient
from wgm.domain.events.roster import buttons, event_post
from wgm.domain.events.services import EventService

logger = logging.getLogger(__name__)

CHECK_SECONDS = 60.0
"""How often to look for posts to lock."""
GONE = (403, 404)
"""The post was deleted or the app lost access: stop trying."""


async def lock_closed_posts(
    db: SQLAlchemyAsyncConfig, discord: DiscordClient, now: datetime
) -> int:
    """Lock every post whose sign-ups have closed. Returns how many were locked."""
    locked = 0
    async with db.get_session() as session:
        events = EventService(session=session)
        for event in await events.due_to_lock(now):
            try:
                await discord.edit_message(
                    event.channel_id or "",
                    event.message_id or "",
                    event_post(event, now),
                    buttons(event, now),
                )
            except DiscordApiError as error:
                if error.status not in GONE:
                    logger.warning("Could not lock event %s: %s", event.id, error)
                    continue
                logger.info("Event %s post is gone; not locking it", event.id)
            else:
                locked += 1
            event.closed_post_at = now
            await events.update(event)
        await session.commit()
    return locked


async def repeat(seconds: float, job: Callable[[], Awaitable[object]]) -> NoReturn:
    """Run `job` every `seconds`, starting after the first wait. Errors are logged."""
    while True:
        await asyncio.sleep(seconds)
        try:
            await job()
        except Exception:
            logger.exception("Background job failed")


def closing_job(
    db: SQLAlchemyAsyncConfig, discord: DiscordClient
) -> Callable[[], Awaitable[int]]:
    """The job `repeat` runs: lock what has closed as of now."""

    async def job() -> int:
        return await lock_closed_posts(db, discord, datetime.now(UTC))

    return job
