from __future__ import annotations

import hashlib
import re
from typing import Optional
from lxml import html as lxml_html
from trafilatura import extract_metadata

from llms_gen.crawler.normalize import base_for_relative_link, normalize_url


def _strip_ws(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def extract_links(html_bytes: bytes, base_final_url: str) -> list[str]:
    try:
        tree = lxml_html.document_fromstring(html_bytes)
    except lxml_html.ParserError:
        return []
    link_base = base_for_relative_link(base_final_url)
    out: list[str] = []
    for a in tree.xpath("//a[@href]"):
        href = a.get("href")
        n = normalize_url(link_base, href)
        if n:
            out.append(n)
    return out


def _title_from_dom(tree: lxml_html.HtmlElement) -> str:
    t = tree.xpath("//title/text()")
    if t:
        return _strip_ws(t[0])
    h = tree.xpath("//h1//text()")
    if h:
        return _strip_ws(" ".join(h))
    return ""


def looks_like_html(content_type: Optional[str], body: bytes) -> bool:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in ("text/html", "application/xhtml+xml"):
            return True
    sample = body[:200].lstrip().lower()
    return sample.startswith(b"<html") or sample.startswith(b"<!doctype html")


def parse_page(html_bytes: bytes, url: str, final_url: str) -> tuple[str, str, int, str]:
    """Return title, description, word_count, content_hash."""
    try:
        tree = lxml_html.document_fromstring(html_bytes)
    except lxml_html.ParserError:
        return "", "", 0, ""

    title_dom = _title_from_dom(tree)
    meta_desc = ""
    for sel in ('//meta[@name="description"]/@content', '//meta[@property="og:description"]/@content'):
        m = tree.xpath(sel)
        if m:
            meta_desc = _strip_ws(m[0])
            break

    text_sample = ""
    try:
        meta = extract_metadata(html_bytes.decode("utf-8", errors="ignore"), url=final_url)
        if meta:
            title = _strip_ws(meta.title) or title_dom
            desc = _strip_ws(meta.description) or meta_desc
        else:
            title, desc = title_dom, meta_desc
    except Exception:
        title, desc = title_dom, meta_desc

    body_text = tree.text_content() or ""
    words = len(body_text.split())
    h = hashlib.sha256(body_text[:8000].encode("utf-8", errors="ignore")).hexdigest()
    return title or final_url, desc, words, h
