from __future__ import annotations

from collections import deque
from typing import Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

from llms_gen.crawler.normalize import normalize_url


def _locs_from_xml(content: str) -> tuple[bool, list[str]]:
    """Return (is_sitemap_index, loc_urls)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return False, []
    is_index = root.tag.endswith("sitemapindex")
    locs: list[str] = []
    for el in root.iter():
        if el.tag.endswith("loc") and el.text:
            locs.append(el.text.strip())
    return is_index, locs


async def collect_urls_from_sitemaps(
    client: httpx.AsyncClient,
    seeds: list[str],
    *,
    max_urls: int = 400,
    max_sitemap_files: int = 24,
) -> list[str]:
    """Expand sitemap index files and collect page locs (bounded)."""
    seen_files: set[str] = set()
    collected: list[str] = []
    queue: deque[str] = deque(dict.fromkeys(seeds))
    files_read = 0

    while queue and len(collected) < max_urls and files_read < max_sitemap_files:
        sm_url = queue.popleft()
        if sm_url in seen_files:
            continue
        seen_files.add(sm_url)
        try:
            r = await client.get(sm_url, follow_redirects=True)
            if r.status_code != 200:
                continue
            is_index, locs = _locs_from_xml(r.text)
            files_read += 1
            if is_index:
                for u in locs:
                    nu = normalize_url(sm_url, u)
                    if nu and urlparse(nu).scheme in ("http", "https"):
                        queue.append(nu)
            else:
                for u in locs:
                    if len(collected) >= max_urls:
                        break
                    nu = normalize_url(sm_url, u)
                    if nu:
                        collected.append(nu)
        except httpx.HTTPError:
            continue

    return collected


async def fetch_sitemap_urls(
    client: httpx.AsyncClient,
    origin: str,
    *,
    max_urls: int = 400,
    max_nested: int = 15,
) -> list[str]:
    """Collect page URLs from default /sitemap.xml paths at origin."""
    seeds = [
        urljoin(origin + "/", "sitemap.xml"),
        urljoin(origin + "/", "sitemap_index.xml"),
    ]
    return await collect_urls_from_sitemaps(
        client,
        seeds,
        max_urls=max_urls,
        max_sitemap_files=max_nested,
    )


def sitemap_urls_from_robots_body(body: Optional[str], origin: str) -> list[str]:
    if not body:
        return []
    out: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            u = line.split(":", 1)[1].strip()
            if u.startswith("http"):
                out.append(u)
    return out
