from __future__ import annotations

from collections import deque
from urllib.parse import urljoin, urlparse

import httpx

from llms_gen.config import Settings
from llms_gen.crawler.fetch import fetch_limited_body
from llms_gen.crawler.normalize import canonical_root, normalize_user_root_url, origin_of, same_site
from llms_gen.crawler.parse import extract_links, looks_like_html, parse_page
from llms_gen.crawler.robots import build_robot_parser, can_fetch, fetch_robots_txt
from llms_gen.crawler.sitemap import (
    collect_urls_from_sitemaps,
    fetch_sitemap_urls,
    sitemap_urls_from_robots_body,
)
from llms_gen.models.domain import CrawlResult, PageRecord, PageSource


async def crawl_site(
    client: httpx.AsyncClient,
    settings: Settings,
    root_url: str,
    max_pages: int,
) -> CrawlResult:
    root = normalize_user_root_url(root_url)
    parsed = urlparse(root)
    if not parsed.netloc:
        return CrawlResult(
            root_url=root_url,
            site_name="",
            homepage_blurb="",
            errors=["Invalid URL"],
            robots_respected=True,
        )

    origin = origin_of(root)
    errors: list[str] = []
    robots_url = urljoin(origin + "/", "robots.txt")
    robots_body = await fetch_robots_txt(client, origin)
    rp = build_robot_parser(robots_url, robots_body)
    ua = settings.crawl_user_agent

    sm_from_robots = sitemap_urls_from_robots_body(robots_body, origin)
    default_sm = [
        urljoin(origin + "/", "sitemap.xml"),
        urljoin(origin + "/", "sitemap_index.xml"),
    ]
    sm_seeds = list(dict.fromkeys([*sm_from_robots[:12], *default_sm]))
    sitemap_pages = await collect_urls_from_sitemaps(
        client,
        sm_seeds,
        max_urls=350,
        max_sitemap_files=24,
    )
    if not sitemap_pages:
        sitemap_pages = await fetch_sitemap_urls(
            client, origin, max_urls=300, max_nested=15
        )
    sitemap_set = set(sitemap_pages)

    root_norm = canonical_root(root)
    seeds: list[str] = [root_norm]
    for u in sitemap_pages:
        if same_site(root_norm, u) and can_fetch(rp, ua, u):
            seeds.append(u)
        if len(seeds) > 100:
            break

    queue: deque[str] = deque(dict.fromkeys(seeds))
    visited: set[str] = set()
    pages: list[PageRecord] = []
    homepage_blurb = ""
    site_name = urlparse(root_norm).netloc.split(":")[0]

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if not same_site(root_norm, url):
            continue
        if not can_fetch(rp, ua, url):
            continue

        try:
            code, final, ctype, body = await fetch_limited_body(
                client, url, settings.max_response_bytes
            )
        except httpx.HTTPError as e:
            errors.append(f"{url}: {e!s}")
            continue

        if code != 200:
            continue
        if not looks_like_html(ctype, body):
            continue

        if url in sitemap_set or final in sitemap_set:
            source = PageSource.SITEMAP
        else:
            source = PageSource.BFS

        rn = root_norm.rstrip("/")
        fn = final.rstrip("/")
        un = url.rstrip("/")
        if un == rn or fn == rn:
            source = PageSource.SEED

        title, desc, words, chash = parse_page(body, url, final)
        if not homepage_blurb and source == PageSource.SEED:
            homepage_blurb = desc or title
            if title and title != final:
                site_name = title.split("|")[0].split("-")[0].strip() or site_name

        pages.append(
            PageRecord(
                url=url,
                final_url=final,
                title=title,
                description=desc,
                status_code=code,
                source=source,
                word_count=words,
                content_hash=chash,
            )
        )

        if not homepage_blurb and len(pages) == 1:
            homepage_blurb = desc or title

        for link in extract_links(body, final):
            if link not in visited and same_site(root_norm, link):
                if can_fetch(rp, ua, link):
                    queue.append(link)

    if not homepage_blurb and pages:
        homepage_blurb = pages[0].description or pages[0].title

    return CrawlResult(
        root_url=root_norm,
        site_name=site_name[:120],
        homepage_blurb=homepage_blurb[:500],
        pages=pages,
        errors=errors[:50],
        robots_respected=rp is not None or robots_body is None,
    )
