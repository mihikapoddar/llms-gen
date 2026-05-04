from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from llms_gen.config import get_settings
from llms_gen.db_session import AsyncSessionLocal
from llms_gen.models.db import Job, JobStatus, MonitoredSite
from llms_gen.services.job_runner import run_job_in_background

logger = logging.getLogger(__name__)


async def tick_monitored_sites() -> None:
    """Enqueue crawl jobs for monitored sites that are due and not already running."""
    settings = get_settings()
    if not settings.monitor_enabled:
        return

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MonitoredSite).where(MonitoredSite.enabled.is_(True))
        )
        sites = list(result.scalars().all())
        job_ids: list[str] = []
        for site in sites:
            if site.last_run_at is not None:
                elapsed = (now - site.last_run_at).total_seconds()
                if elapsed < float(site.interval_seconds):
                    continue

            busy = await session.execute(
                select(Job.id).where(
                    Job.monitored_site_id == site.id,
                    Job.status.in_(
                        [JobStatus.pending.value, JobStatus.running.value]
                    ),
                )
            )
            if busy.first() is not None:
                continue

            job = Job(
                root_url=site.root_url,
                max_pages=site.max_pages,
                status=JobStatus.pending.value,
                monitored_site_id=site.id,
            )
            session.add(job)
            await session.flush()
            job_ids.append(job.id)
        await session.commit()

    for jid in job_ids:
        asyncio.create_task(run_job_in_background(jid))
        logger.info("Scheduled monitor job %s", jid)


async def monitor_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(float(settings.monitor_poll_interval_s))
        try:
            await tick_monitored_sites()
        except Exception:
            logger.exception("Monitor tick failed")
