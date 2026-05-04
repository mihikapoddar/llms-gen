from __future__ import annotations

from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse


def normalize_url(base: str, href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    h = href.strip()
    if not h or h.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    joined = urljoin(base, h)
    clean, _frag = urldefrag(joined)
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https"):
        return None
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = urlunparse(
        (parsed.scheme, netloc, path, "", parsed.query, "")
    )
    return normalized


def _host_key(netloc: str) -> str:
    """Host without port, lowercase."""
    return netloc.lower().split("@")[-1].split(":")[0]


def _hosts_same_site(host_a: str, host_b: str) -> bool:
    """
    Same crawl scope as long as scheme matches elsewhere; treat ``www.example.com``
    and ``example.com`` as the same site (common redirect / link pattern).
    """
    a, b = host_a.lower(), host_b.lower()
    if a == b:
        return True
    if a.startswith("www.") and a[4:] == b:
        return True
    if b.startswith("www.") and b[4:] == a:
        return True
    return False


def same_site(url_a: str, url_b: str) -> bool:
    pa, pb = urlparse(url_a), urlparse(url_b)
    if pa.scheme != pb.scheme:
        return False
    return _hosts_same_site(_host_key(pa.netloc), _host_key(pb.netloc))


def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}"


def normalize_user_root_url(raw: str) -> str:
    """
    Accept user input with or without a scheme: ``owner.com``, ``www.owner.com``,
    ``//cdn.example.com``, or full ``https://...`` URLs.
    """
    s = raw.strip()
    if not s:
        raise ValueError("URL is required")
    if s.startswith("//"):
        s = "https:" + s
    p = urlparse(s)
    if p.scheme in ("http", "https"):
        if not p.netloc:
            raise ValueError("Invalid URL: missing host")
        return urlunparse((p.scheme, p.netloc.lower(), p.path, "", p.query, ""))
    host_and_path = s.lstrip("/")
    if not host_and_path:
        raise ValueError("Invalid URL")
    return "https://" + host_and_path


def canonical_root(url: str) -> str:
    """Normalize scheme, host, and path for crawl root."""
    p = urlparse(url)
    path = p.path if p.path else "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))


def base_for_relative_link(final_url: str) -> str:
    """
    Base URL for resolving relative hrefs like ``bar`` from HTML.

    ``urllib.parse.urljoin`` drops the last path segment when the base has no
    trailing slash; for directory-like paths (no file extension), append ``/``
    so ``/docs`` + ``bar`` becomes ``/docs/bar`` instead of ``/bar``.
    """
    clean, _frag = urldefrag(final_url)
    p = urlparse(clean)
    netloc = p.netloc.lower()
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    last_seg = path.rsplit("/", 1)[-1] if path not in ("", "/") else ""
    looks_like_file = "." in last_seg and not last_seg.startswith(".")
    if looks_like_file or path in ("", "/"):
        return urlunparse((p.scheme, netloc, path or "/", "", p.query, ""))
    return urlunparse((p.scheme, netloc, path + "/", "", p.query, ""))
