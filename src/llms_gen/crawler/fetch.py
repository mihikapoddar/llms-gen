from __future__ import annotations

from typing import Optional, Tuple

import httpx

from llms_gen.config import Settings


def build_client(settings: Settings) -> httpx.AsyncClient:
    headers = {"User-Agent": settings.crawl_user_agent}
    timeout = httpx.Timeout(settings.fetch_timeout_s)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    )


async def fetch_limited_body(
    client: httpx.AsyncClient,
    url: str,
    max_bytes: int,
) -> Tuple[int, str, Optional[str], bytes]:
    """GET url; return (status_code, final_url, content_type, body_prefix)."""
    async with client.stream("GET", url) as response:
        final = str(response.url)
        code = response.status_code
        content_type = response.headers.get("content-type")
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            if not chunk:
                continue
            remaining = max_bytes - total
            if remaining <= 0:
                break
            piece = chunk if len(chunk) <= remaining else chunk[:remaining]
            chunks.append(piece)
            total += len(piece)
        body = b"".join(chunks)
        return code, final, content_type, body
