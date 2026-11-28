"""Lock event posts once sign-ups close.

A press after closing is already refused. This job also greys out the buttons
and changes "Sign-ups close" to "Sign-ups closed" on the post itself, so
members can see it without pressing anything.
"""

import logging
from datetime import datetime

from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.domain.discord.client import DiscordApiError, DiscordClient
from wgm.domain.events.roster import post_components
from wgm.domain.events.services import EventService
from wgm.plugins.spec import JobContext

logger = logging.getLogger(__name__)

GONE = (400, 403, 404)
"""Retrying won't help: Discord refused the edit (such as an old plain-text
post that can't become the new design), or the post was deleted, or the app
lost access."""


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
                    post_components(event, now),
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


async def close_job(ctx: JobContext) -> int:
    """The event plugin's job: lock what has closed as of now."""
    return await lock_closed_posts(ctx.db, ctx.discord, ctx.clock())
