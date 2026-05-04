from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from llms_gen.api.deps import get_session, require_api_key
from llms_gen.config import get_settings
from llms_gen.crawler.normalize import normalize_user_root_url
from llms_gen.models.db import Job, JobStatus
from llms_gen.services.job_runner import run_job_in_background

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["jobs"],
    dependencies=[Depends(require_api_key)],
)


class JobCreate(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)
    max_pages: Optional[int] = Field(None, ge=1, le=200)

    @field_validator("url")
    @classmethod
    def normalize_root_url(cls, v: str) -> str:
        return normalize_user_root_url(v)


class JobOut(BaseModel):
    id: str
    status: str
    root_url: str
    pages_crawled: Optional[int] = None
    error_message: Optional[str] = None
    artifact_id: Optional[str] = None

    model_config = {"from_attributes": True}


@router.post("/jobs", status_code=202)
async def create_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    settings = get_settings()
    cap = min(body.max_pages or settings.max_pages_per_job, settings.max_pages_per_job)
    job = Job(root_url=body.url, status=JobStatus.pending.value, max_pages=cap)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    jid = job.id
    background_tasks.add_task(run_job_in_background, jid)
    return {"id": jid, "status": JobStatus.pending.value}


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobOut:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    artifact_id = job.id if job.status == JobStatus.completed.value and job.llms_txt else None
    return JobOut(
        id=job.id,
        status=job.status,
        root_url=job.root_url,
        pages_crawled=job.pages_crawled,
        error_message=job.error_message,
        artifact_id=artifact_id,
    )


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, session: AsyncSession = Depends(get_session)):
    from fastapi.responses import PlainTextResponse

    job = await session.get(Job, artifact_id)
    if job is None or job.llms_txt is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if job.status != JobStatus.completed.value:
        raise HTTPException(status_code=404, detail="Artifact not ready")
    return PlainTextResponse(
        content=job.llms_txt,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="llms.txt"'},
    )
