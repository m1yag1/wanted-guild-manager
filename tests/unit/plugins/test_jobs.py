"""Plugin background jobs: repeating, surviving failures, stopping. No real sleeps."""

import asyncio

import httpx
import pytest

from wgm.db.config import database_config
from wgm.domain.discord.client import DiscordClient
from wgm.plugins import Job, JobContext
from wgm.plugins.jobs import repeat, running


class Ticks:
    """A sleep that returns at once and stops the loop after `limit` waits."""

    def __init__(self, limit: int) -> None:
        self.waits: list[float] = []
        self.limit = limit

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)
        if len(self.waits) > self.limit:
            raise asyncio.CancelledError
        await asyncio.sleep(0)


@pytest.fixture
async def ctx() -> JobContext:
    async with httpx.AsyncClient() as http:
        return JobContext(
            database_config("sqlite+aiosqlite://"),
            DiscordClient("t", "http://127.0.0.1:9", http),
            {},
        )


@pytest.mark.anyio
async def test_a_job_waits_then_runs_and_survives_a_failure(
    ctx: JobContext, caplog: pytest.LogCaptureFixture
) -> None:
    runs: list[int] = []

    async def run(job_ctx: JobContext) -> None:
        runs.append(len(runs))
        if len(runs) == 1:
            raise RuntimeError("boom")

    ticks = Ticks(limit=3)
    with pytest.raises(asyncio.CancelledError):
        await repeat(Job("count", 60, run), ctx, ticks)

    assert ticks.waits == [60, 60, 60, 60]
    assert runs == [0, 1, 2]
    assert "Background job count failed" in caplog.text


@pytest.mark.anyio
async def test_jobs_run_side_by_side_and_stop_with_the_block(ctx: JobContext) -> None:
    started: list[str] = []
    stopped = asyncio.Event()

    async def run(job_ctx: JobContext) -> None:
        started.append("run")
        await asyncio.sleep(0)

    async def instant(seconds: float) -> None:
        if len(started) >= 4:
            stopped.set()
        await asyncio.sleep(0)

    jobs = [(Job("a", 1, run), ctx), (Job("b", 1, run), ctx)]
    async with running(jobs, instant):
        await stopped.wait()

    count = len(started)
    await asyncio.sleep(0)
    assert count >= 4
    assert len(started) == count
