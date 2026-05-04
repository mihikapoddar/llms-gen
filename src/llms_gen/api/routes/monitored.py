from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from llms_gen.api.deps import get_session, require_api_key
from llms_gen.config import get_settings
from llms_gen.crawler.normalize import normalize_user_root_url
from llms_gen.models.db import Job, JobStatus, MonitoredSite
from llms_gen.services.job_runner import run_job_in_background

router = APIRouter(prefix="/api/monitored-sites", tags=["monitored"])


def _normalize_webhook(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    s = v.strip()
    if not s:
        return None
    if not s.startswith(("http://", "https://")):
        raise ValueError("Webhook URL must start with http:// or https://")
    return s[:2048]


class MonitoredCreate(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)
    max_pages: Optional[int] = Field(None, ge=1, le=200)
    interval_hours: float = Field(24, ge=1, le=8760)
    webhook_url: Optional[str] = Field(None, max_length=2048)

    @field_validator("url")
    @classmethod
    def normalize_root_url(cls, v: str) -> str:
        return normalize_user_root_url(v)

    @field_validator("webhook_url")
    @classmethod
    def webhook(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_webhook(v)


class MonitoredPatch(BaseModel):
    webhook_url: Optional[str] = Field(None, max_length=2048)
    interval_hours: Optional[float] = Field(None, ge=1, le=8760)
    enabled: Optional[bool] = None

    @field_validator("webhook_url")
    @classmethod
    def webhook(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _normalize_webhook(v)


class MonitoredOut(BaseModel):
    id: str
    root_url: str
    max_pages: int
    enabled: bool
    interval_seconds: int
    last_run_at: Optional[datetime] = None
    last_llms_sha256: Optional[str] = None
    last_job_id: Optional[str] = None
    content_changed_at: Optional[datetime] = None
    webhook_url: Optional[str] = None

    model_config = {"from_attributes": True}


class RefreshOut(BaseModel):
    job_id: str


@router.post("", response_model=MonitoredOut, status_code=201)
async def add_monitored_site(
    body: MonitoredCreate,
    session: AsyncSession = Depends(get_session),
) -> MonitoredSite:
    settings = get_settings()
    cap = min(body.max_pages or settings.max_pages_per_job, settings.max_pages_per_job)
    interval_sec = int(body.interval_hours * 3600)
    site = MonitoredSite(
        root_url=body.url,
        max_pages=cap,
        interval_seconds=interval_sec,
        webhook_url=body.webhook_url,
    )
    session.add(site)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This URL is already monitored; delete or update the existing entry.",
        )
    await session.refresh(site)
    return site


@router.get(
    "",
    response_model=list[MonitoredOut],
    dependencies=[Depends(require_api_key)],
)
async def list_monitored_sites(
    session: AsyncSession = Depends(get_session),
) -> list[MonitoredSite]:
    result = await session.execute(
        select(MonitoredSite).order_by(MonitoredSite.created_at.desc())
    )
    return list(result.scalars().all())


@router.get(
    "/{site_id}",
    response_model=MonitoredOut,
    dependencies=[Depends(require_api_key)],
)
async def get_monitored_site(
    site_id: str,
    session: AsyncSession = Depends(get_session),
) -> MonitoredSite:
    site = await session.get(MonitoredSite, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Not found")
    return site


@router.patch(
    "/{site_id}",
    response_model=MonitoredOut,
    dependencies=[Depends(require_api_key)],
)
async def patch_monitored_site(
    site_id: str,
    body: MonitoredPatch,
    session: AsyncSession = Depends(get_session),
) -> MonitoredSite:
    site = await session.get(MonitoredSite, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Not found")
    data = body.model_dump(exclude_unset=True)
    if "webhook_url" in data:
        site.webhook_url = data["webhook_url"]
    if "interval_hours" in data:
        site.interval_seconds = int(data["interval_hours"] * 3600)
    if "enabled" in data:
        site.enabled = data["enabled"]
    await session.commit()
    await session.refresh(site)
    return site


@router.delete(
    "/{site_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
async def delete_monitored_site(
    site_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    site = await session.get(MonitoredSite, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Not found")
    await session.delete(site)
    await session.commit()


@router.post(
    "/{site_id}/refresh",
    response_model=RefreshOut,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
async def refresh_monitored_site(
    site_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RefreshOut:
    site = await session.get(MonitoredSite, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Not found")
    job = Job(
        root_url=site.root_url,
        max_pages=site.max_pages,
        status=JobStatus.pending.value,
        monitored_site_id=site.id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    jid = job.id
    background_tasks.add_task(run_job_in_background, jid)
    return RefreshOut(job_id=jid)
