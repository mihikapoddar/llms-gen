from __future__ import annotations

import re
from typing import Iterable, Optional, Set
from urllib.parse import urlparse

from llms_gen.crawler.normalize import same_site
from llms_gen.models.domain import CrawlResult, CuratedSite, LinkItem, PageRecord, PageSource

# Descriptions shorter than this are not treated as duplicate boilerplate.
_MIN_DESC_LEN_FOR_BOILERPLATE = 36
# Same normalized description on this many+ pages → only the top-scored page keeps the note.
_BOILERPLATE_MIN_PAGES = 3


def _path_bucket(path: str) -> Optional[str]:
    p = path.lower()
    optional_markers = (
        "/privacy",
        "/terms",
        "/legal",
        "/cookie",
        "/gdpr",
        "/security",
        "/status",
        "/changelog",
        "/license",
        "/imprint",
        "/disclaimer",
        "/accessibility",
    )
    if any(m in p for m in optional_markers):
        return "optional"
    doc_markers = (
        "/doc",
        "/guide",
        "/learn",
        "/reference",
        "/api",
        "/manual",
        "/tutorial",
        "/wiki",
        "/docs",
    )
    if any(m in p for m in doc_markers):
        return "docs"
    blog_markers = ("/blog", "/post", "/article", "/news", "/journal", "/stories")
    if any(m in p for m in blog_markers):
        return "blog"
    product_markers = ("/pricing", "/product", "/features", "/solutions", "/enterprise", "/plans")
    if any(m in p for m in product_markers):
        return "product"
    return None


def _score_page(rec: PageRecord) -> float:
    score = 0.0
    if rec.description:
        score += 3.0
    if rec.title and rec.title != rec.final_url:
        score += 2.0
    wc = rec.word_count
    if 120 <= wc <= 8000:
        score += 2.0
    elif wc < 40:
        score -= 2.0
    if rec.source == PageSource.SITEMAP:
        score += 1.0
    u = rec.final_url.lower()
    if any(x in u for x in ("/tag/", "/tags/", "/category/", "page=", "/search")):
        score -= 2.0
    return score


def _url_key(rec: PageRecord) -> str:
    return rec.final_url.rstrip("/")


def _norm_desc(d: str) -> str:
    if not d:
        return ""
    return re.sub(r"\s+", " ", d).strip().lower()[:480]


def _urls_that_keep_meta_description(records: Iterable[PageRecord]) -> Set[str]:
    """
    For descriptions repeated across many pages (marketing boilerplate),
    only the highest-scored page per description keeps the note text.
    """
    groups: dict[str, list[PageRecord]] = {}
    for r in records:
        nd = _norm_desc(r.description)
        if not nd or len(nd) < _MIN_DESC_LEN_FOR_BOILERPLATE:
            key = f"__short__:{_url_key(r)}"
        else:
            key = nd
        groups.setdefault(key, []).append(r)

    allowed: Set[str] = set()
    for key, group in groups.items():
        if key.startswith("__short__:"):
            for r in group:
                allowed.add(_url_key(r))
            continue
        if len(group) < _BOILERPLATE_MIN_PAGES:
            for r in group:
                allowed.add(_url_key(r))
        else:
            best = max(group, key=_score_page)
            allowed.add(_url_key(best))
    return allowed


_FUNNEL_NEGATIVE = (
    "/blog",
    "/pricing",
    "/docs",
    "/doc/",
    "case-stud",
    "careers",
    "/reviews",
    "/leadership",
    "/catering",
    "/pos",
    "/online-ordering",
    "/mobile",
    "/loyalty",
    "/automatic-marketing",
    "/branded-apps",
    "/how-owner",
    "/partner",
    "affiliate",
)
_FUNNEL_POSITIVE = re.compile(
    r"(demo|funnel|quiz|grader|talkin-tacos)",
    re.IGNORECASE,
)


def _is_soft_funnel_path(path: str) -> bool:
    """Landing / funnel paths to list after substantive pages and overflow to Optional."""
    p = (path or "/").lower()
    if any(x in p for x in _FUNNEL_NEGATIVE):
        return False
    return bool(_FUNNEL_POSITIVE.search(p))


def _title_from_path(final_url: str) -> str:
    path = (urlparse(final_url).path or "").strip("/")
    if not path:
        return final_url
    last = path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").strip()
    if not last:
        return final_url
    return last[:1].upper() + last[1:] if len(last) == 1 else last.title()


def _sanitize_title(title: str, final_url: str) -> str:
    title = (title or "").replace("\n", " ").strip()
    if not title or title == final_url:
        return _title_from_path(final_url)

    parts = [p.strip() for p in title.split("|") if p.strip()]
    if len(parts) >= 2:
        lowered = [p.lower() for p in parts]
        if len(set(lowered)) == 1:
            title = parts[0]
        elif len(parts) == 2:
            a, b = parts[0], parts[1]
            if a.lower() == b.lower():
                title = a
            elif len(a) <= 2:
                title = b
            elif len(b) <= 2:
                title = a
            elif a.lower() in ("owner", "home", "page") and len(b) >= len(a):
                title = b
            elif b.lower() in ("owner", "home", "page") and len(a) >= len(b):
                title = a

    title = title.replace("]", " ").strip()
    if not title:
        return _title_from_path(final_url)
    if len(title) > 200:
        title = title[:197].rstrip() + "…"
    return title


def _is_document_root_url(page_url: str, crawl_root: str) -> bool:
    if not same_site(page_url, crawl_root):
        return False
    path = (urlparse(page_url).path or "/").rstrip("/")
    return path == ""


def _note_echoes_blurb(blurb: str, note: str) -> bool:
    """True if the link note duplicates the homepage blurb (or is a near-substring)."""
    b = _norm_desc(blurb)
    n = _norm_desc(note)
    if not b or not n:
        return False
    if b == n:
        return True
    if len(n) >= 40 and (n in b or b in n):
        shorter, longer = (n, b) if len(n) <= len(b) else (b, n)
        if len(shorter) / max(len(longer), 1) >= 0.88:
            return True
    return False


def _filter_homepage_noise(
    items: list[LinkItem], crawl_root: str, blurb: str
) -> list[LinkItem]:
    if not blurb:
        return items
    return [
        it
        for it in items
        if not (
            _is_document_root_url(it.url, crawl_root)
            and _note_echoes_blurb(blurb, it.note)
        )
    ]


def _to_link(rec: PageRecord, keep_description: bool) -> LinkItem:
    note = rec.description or ""
    note = re.sub(r"\s+", " ", note).strip()
    if not keep_description:
        note = ""
    if len(note) > 220:
        note = note[:217].rstrip() + "…"
    title = _sanitize_title(rec.title, rec.final_url)
    return LinkItem(title=title, url=rec.final_url, note=note)


def rank_and_bucket(
    result: CrawlResult,
    *,
    max_per_section: int = 28,
    max_optional: int = 36,
) -> CuratedSite:
    """Deduplicate by final_url, classify paths, score, de-boilerplate notes, cap list sizes."""
    by_url: dict[str, PageRecord] = {}
    for p in result.pages:
        key = p.final_url.rstrip("/")
        prev = by_url.get(key)
        if prev is None or _score_page(p) > _score_page(prev):
            by_url[key] = p

    all_recs = list(by_url.values())
    keep_desc_for_url = _urls_that_keep_meta_description(all_recs)

    buckets: dict[str, list[PageRecord]] = {
        "docs": [],
        "blog": [],
        "product": [],
        "key": [],
        "optional": [],
    }
    for rec in all_recs:
        path = urlparse(rec.final_url).path or "/"
        b = _path_bucket(path)
        if b == "optional":
            buckets["optional"].append(rec)
        elif b == "docs":
            buckets["docs"].append(rec)
        elif b == "blog":
            buckets["blog"].append(rec)
        elif b == "product":
            buckets["product"].append(rec)
        else:
            buckets["key"].append(rec)

    for name in buckets:
        buckets[name].sort(key=_score_page, reverse=True)

    def take(key: str) -> list[LinkItem]:
        return [
            _to_link(r, _url_key(r) in keep_desc_for_url)
            for r in buckets[key][:max_per_section]
        ]

    # Key pages: substantive URLs first, then funnel-style paths (demo / quiz / etc.).
    key_list = buckets["key"]
    paths = [(rec, urlparse(rec.final_url).path or "/") for rec in key_list]
    non_funnel = [rec for rec, p in paths if not _is_soft_funnel_path(p)]
    funnel = [rec for rec, p in paths if _is_soft_funnel_path(p)]
    non_funnel.sort(key=_score_page, reverse=True)
    funnel.sort(key=_score_page, reverse=True)
    merged_key = non_funnel + funnel
    key_selected = merged_key[:max_per_section]
    key_rest = merged_key[max_per_section:]

    sections: list[tuple[str, list[LinkItem]]] = []
    if buckets["docs"]:
        sections.append(("Docs", take("docs")))
    if buckets["blog"]:
        sections.append(("Blog", take("blog")))
    if buckets["product"]:
        sections.append(("Product", take("product")))
    if key_selected:
        sections.append(
            (
                "Key pages",
                [_to_link(r, _url_key(r) in keep_desc_for_url) for r in key_selected],
            )
        )

    optional_recs = list(buckets["optional"])
    seen_opt = {_url_key(r) for r in optional_recs}
    for r in key_rest:
        k = _url_key(r)
        if k not in seen_opt:
            optional_recs.append(r)
            seen_opt.add(k)
    optional_recs.sort(key=_score_page, reverse=True)
    optional_links = [
        _to_link(r, _url_key(r) in keep_desc_for_url)
        for r in optional_recs[:max_optional]
    ]

    blurb = re.sub(r"\s+", " ", result.homepage_blurb or "").strip()
    if len(blurb) > 400:
        blurb = blurb[:397].rstrip() + "…"

    crawl_root = result.root_url
    sections = [
        (name, _filter_homepage_noise(lst, crawl_root, blurb)) for name, lst in sections
    ]
    sections = [(name, lst) for name, lst in sections if lst]
    optional_links = _filter_homepage_noise(optional_links, crawl_root, blurb)

    title = result.site_name or urlparse(result.root_url).netloc
    title = title.replace("\n", " ").strip()[:200]

    detail_bullets: list[str] = []
    if result.errors:
        detail_bullets.append(
            f"Crawl completed with {len(result.errors)} fetch warning(s); some pages may be missing."
        )

    return CuratedSite(
        site_title=title,
        blurb=blurb,
        detail_bullets=detail_bullets,
        sections=sections,
        optional=optional_links,
    )
