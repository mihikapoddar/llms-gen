from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


async def post_llms_changed_webhook(
    webhook_url: str,
    *,
    site_id: str,
    root_url: str,
    job_id: str,
    sha256: str,
    previous_sha256: Optional[str],
    content_changed_at: str,
    artifact_path: str,
) -> None:
    """POST JSON payload; failures are logged and swallowed (best-effort)."""
    payload: dict[str, Any] = {
        "event": "llms_txt.changed",
        "site_id": site_id,
        "root_url": root_url,
        "job_id": job_id,
        "sha256": sha256,
        "previous_sha256": previous_sha256,
        "content_changed_at": content_changed_at,
        "artifact_path": artifact_path,
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(
                webhook_url,
                json=payload,
                headers={"User-Agent": "llms-gen-webhook/1"},
            )
            r.raise_for_status()
    except Exception as e:
        logger.warning(
            "Webhook delivery failed for site %s: %s",
            site_id,
            e,
        )
