import re

from llms_gen.crawler.rank import rank_and_bucket
from llms_gen.generator import build_llms_txt
from llms_gen.models.domain import CrawlResult, PageRecord, PageSource


def _page(url: str, title: str, desc: str, wc: int = 500) -> PageRecord:
    return PageRecord(
        url=url,
        final_url=url,
        title=title,
        description=desc,
        status_code=200,
        source=PageSource.BFS,
        word_count=wc,
        content_hash="x",
    )


def test_boilerplate_description_only_once():
    same = "See how Owner could work for you. Learn how other restaurants use Owner."
    pages = [
        _page("https://ex.com/a", "A", same, 800),
        _page("https://ex.com/b", "B", same, 800),
        _page("https://ex.com/c", "C", same, 800),
        _page("https://ex.com/d", "D", "Unique page about catering orders here.", 800),
    ]
    result = CrawlResult(
        root_url="https://ex.com",
        site_name="Ex",
        homepage_blurb="Hi",
        pages=pages,
    )
    curated = rank_and_bucket(result, max_per_section=10, max_optional=10)
    text_notes = 0
    for _name, items in curated.sections:
        for it in items:
            if same[:40] in (it.note or ""):
                text_notes += 1
    assert text_notes == 1


def test_duplicate_pipe_title_collapsed():
    pages = [
        _page(
            "https://ex.com/demo",
            "Owner | Owner",
            "Short",
            100,
        ),
    ]
    result = CrawlResult(
        root_url="https://ex.com",
        site_name="Ex",
        homepage_blurb="Hi",
        pages=pages,
    )
    curated = rank_and_bucket(result)
    key = next(items for name, items in curated.sections if name == "Key pages")
    assert key[0].title == "Owner"


def test_funnel_pages_follow_key_pages():
    """Lower-priority funnel URLs should sort after substantive key URLs."""
    pages = [
        _page("https://ex.com/about-us", "About", "Real description here.", 500),
        _page("https://ex.com/demo-start", "Demo", "Real description here.", 500),
    ]
    result = CrawlResult(
        root_url="https://ex.com",
        site_name="Ex",
        homepage_blurb="Hi",
        pages=pages,
    )
    curated = rank_and_bucket(result, max_per_section=10)
    key_section = next(items for name, items in curated.sections if name == "Key pages")
    titles = [it.title for it in key_section]
    assert titles[0] == "About"


def test_homepage_omitted_when_note_duplicates_blurb():
    blurb = "Owner gives you the same tools that major national brands use."
    pages = [
        _page("https://ex.com/", "Home | Ex", blurb, 500),
        _page("https://ex.com/about", "About", "Different description here.", 500),
    ]
    result = CrawlResult(
        root_url="https://ex.com",
        site_name="Ex",
        homepage_blurb=blurb,
        pages=pages,
    )
    curated = rank_and_bucket(result)
    md = build_llms_txt(curated)
    assert not re.search(r"\(https://ex\.com/?\)", md)
    assert "https://ex.com/about" in md
