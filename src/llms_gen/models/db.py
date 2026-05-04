from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.pending.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    llms_txt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_pages: Mapped[int] = mapped_column(Integer, default=60)
    monitored_site_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("monitored_sites.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class MonitoredSite(Base):
    """Registered root URL for periodic re-crawl and llms.txt hash tracking."""

    __tablename__ = "monitored_sites"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    max_pages: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=86_400)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_llms_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    content_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    webhook_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
