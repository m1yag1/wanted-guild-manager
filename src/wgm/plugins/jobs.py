"""Run plugins' background jobs while the app is up (ADR 0013)."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import NoReturn

from wgm.plugins.spec import Job, JobContext

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[object]]


async def repeat(job: Job, ctx: JobContext, sleep: Sleep = asyncio.sleep) -> NoReturn:
    """Run `job` every `job.seconds`, starting after the first wait.

    A failed run is logged and the job carries on at its next interval.
    """
    while True:
        await sleep(job.seconds)
        try:
            await job.run(ctx)
        except Exception:
            logger.exception("Background job %s failed", job.name)


@contextlib.asynccontextmanager
async def running(
    jobs: list[tuple[Job, JobContext]], sleep: Sleep = asyncio.sleep
) -> AsyncIterator[None]:
    """Each job in its own task for the life of the block, then cancelled."""
    tasks = [asyncio.create_task(repeat(job, ctx, sleep)) for job, ctx in jobs]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
