from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from llms_gen.config import Settings, get_settings

logger = logging.getLogger(__name__)
from llms_gen.crawler.discover import crawl_site
from llms_gen.crawler.fetch import build_client
from llms_gen.crawler.rank import rank_and_bucket
from llms_gen.generator import build_llms_txt, validate_llms_txt
from llms_gen.models.db import Job, JobStatus, MonitoredSite


async def run_crawl_job(
    session: AsyncSession, job_id: str, settings: Optional[Settings] = None
) -> None:
    settings = settings or get_settings()
    job = await session.get(Job, job_id)
    if job is None:
        return

    monitored_id = job.monitored_site_id

    job.status = JobStatus.running.value
    job.error_message = None
    await session.commit()

    try:
        async with build_client(settings) as client:
            crawl = await crawl_site(client, settings, job.root_url, job.max_pages)
        curated = rank_and_bucket(crawl)
        text = build_llms_txt(curated)
        issues = validate_llms_txt(text)
        if issues:
            logger.warning("llms.txt validation notes for job %s: %s", job_id, issues)

        job = await session.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.completed.value
        job.llms_txt = text
        job.pages_crawled = len(crawl.pages)
        job.error_message = None
        await session.commit()

        if monitored_id:
            site = await session.get(MonitoredSite, monitored_id)
            if site is not None:
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                prev = site.last_llms_sha256
                wh_url = (site.webhook_url or "").strip()
                site_id_val = site.id
                root_val = site.root_url
                site.last_llms_sha256 = digest
                site.last_job_id = job_id
                site.last_run_at = datetime.now(timezone.utc)
                changed_at: Optional[datetime] = None
                if prev is not None and prev != digest:
                    changed_at = datetime.now(timezone.utc)
                    site.content_changed_at = changed_at
                await session.commit()

                if prev is not None and prev != digest and wh_url:
                    from llms_gen.services.webhook_notify import post_llms_changed_webhook

                    settings = get_settings()
                    base = (settings.public_base_url or "").rstrip("/")
                    artifact = (
                        f"{base}/api/artifacts/{job_id}" if base else f"/api/artifacts/{job_id}"
                    )
                    asyncio.create_task(
                        post_llms_changed_webhook(
                            wh_url,
                            site_id=site_id_val,
                            root_url=root_val,
                            job_id=job_id,
                            sha256=digest,
                            previous_sha256=prev,
                            content_changed_at=(
                                changed_at or datetime.now(timezone.utc)
                            ).isoformat(),
                            artifact_path=artifact,
                        )
                    )
    except Exception as e:
        job = await session.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.failed.value
            job.error_message = str(e)[:4000]
            await session.commit()
        if monitored_id:
            site = await session.get(MonitoredSite, monitored_id)
            if site is not None:
                site.last_run_at = datetime.now(timezone.utc)
                await session.commit()
        raise
