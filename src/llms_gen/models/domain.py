from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageSource(str, Enum):
    SITEMAP = "sitemap"
    BFS = "bfs"
    SEED = "seed"


@dataclass
class PageRecord:
    url: str
    final_url: str
    title: str
    description: str
    status_code: int
    source: PageSource
    word_count: int = 0
    content_hash: str = ""


@dataclass
class CrawlResult:
    root_url: str
    site_name: str
    homepage_blurb: str
    pages: list[PageRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    robots_respected: bool = True


@dataclass
class LinkItem:
    title: str
    url: str
    note: str


@dataclass
class CuratedSite:
    site_title: str
    blurb: str
    detail_bullets: list[str]
    sections: list[tuple[str, list[LinkItem]]]
    optional: list[LinkItem]
