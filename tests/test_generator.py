from llms_gen.generator import build_llms_txt, validate_llms_txt
from llms_gen.models.domain import CuratedSite, LinkItem


def test_build_and_validate_minimal():
    curated = CuratedSite(
        site_title="Example",
        blurb="A short description.",
        detail_bullets=[],
        sections=[
            (
                "Docs",
                [
                    LinkItem(title="Start", url="https://example.com/docs", note="Begin here"),
                ],
            )
        ],
        optional=[LinkItem(title="Terms", url="https://example.com/terms", note="")],
    )
    text = build_llms_txt(curated)
    assert "# Example" in text
    assert "> A short description." in text
    assert "## Docs" in text
    assert "[Start](https://example.com/docs)" in text
    assert "## Optional" in text
    issues = validate_llms_txt(text)
    assert issues == []
