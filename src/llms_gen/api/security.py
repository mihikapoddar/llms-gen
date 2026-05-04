"""Optional shared-secret gate for HTTP API routes."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from llms_gen.config import get_settings


async def require_api_key(request: Request) -> None:
    """If ``LLMS_GEN_API_KEY`` is set, require ``X-LLMS-GEN-API-Key`` or ``Authorization: Bearer``."""
    expected = (get_settings().api_key or "").strip()
    if not expected:
        return
    provided = request.headers.get("X-LLMS-GEN-API-Key", "").strip()
    auth = request.headers.get("Authorization", "")
    if not provided and auth.lower().startswith("bearer "):
        provided = auth[7:].strip()
    try:
        ok = bool(provided) and hmac.compare_digest(provided, expected)
    except (TypeError, ValueError):
        ok = False
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key (use X-LLMS-GEN-API-Key or Authorization: Bearer)",
            headers={"WWW-Authenticate": "Bearer"},
        )
