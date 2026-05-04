from __future__ import annotations

import logging

from llms_gen.db_session import AsyncSessionLocal
from llms_gen.services.pipeline import run_crawl_job

logger = logging.getLogger(__name__)


async def run_job_in_background(job_id: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await run_crawl_job(session, job_id)
    except Exception:
        logger.exception("Job %s failed", job_id)
