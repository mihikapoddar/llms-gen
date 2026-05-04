from llms_gen.crawler.normalize import (
    base_for_relative_link,
    canonical_root,
    normalize_url,
    normalize_user_root_url,
    same_site,
)


def test_same_site_www_bare_host_equivalent():
    assert same_site("https://owner.com/", "https://www.owner.com/pricing")
    assert same_site("https://www.example.com", "https://example.com/foo")
    assert not same_site("https://owner.com", "https://other.com")


def test_normalize_and_same_site():
    # Leading "/" on href resolves against the origin (not under /foo).
    a = normalize_url("https://Example.com/foo", "/bar?q=1#x")
    assert a == "https://example.com/bar?q=1"
    assert same_site("https://example.com/a", "https://example.com/b")
    assert not same_site("https://example.com", "https://other.com")
    assert canonical_root("https://EXAMPLE.com") == "https://example.com/"
    # Relative hrefs resolve under the last path segment only if base ends with "/".
    rel = normalize_url("https://example.com/foo/", "bar")
    assert rel == "https://example.com/foo/bar"
    # Directory-like paths get a trailing slash for relative resolution.
    rel2 = normalize_url(base_for_relative_link("https://example.com/foo"), "bar")
    assert rel2 == "https://example.com/foo/bar"


def test_normalize_user_root_url():
    assert normalize_user_root_url("owner.com") == "https://owner.com"
    assert normalize_user_root_url("www.owner.com") == "https://www.owner.com"
    assert normalize_user_root_url("HTTPS://Owner.COM/pricing") == "https://owner.com/pricing"
    assert normalize_user_root_url("//cdn.example.com") == "https://cdn.example.com"
