from __future__ import annotations

from llms_gen.models.domain import CuratedSite


def build_llms_txt(curated: CuratedSite) -> str:
    """Render CuratedSite as llms.txt markdown per https://llmstxt.org/ ."""
    lines: list[str] = [f"# {curated.site_title}", ""]

    if curated.blurb:
        lines.append(f"> {curated.blurb}")
        lines.append("")

    if curated.detail_bullets:
        lines.append("Notes:")
        lines.append("")
        for b in curated.detail_bullets:
            lines.append(f"- {b}")
        lines.append("")

    for section_name, items in curated.sections:
        if not items:
            continue
        lines.append(f"## {section_name}")
        lines.append("")
        for it in items:
            if it.note:
                lines.append(f"- [{it.title}]({it.url}): {it.note}")
            else:
                lines.append(f"- [{it.title}]({it.url})")
        lines.append("")

    if curated.optional:
        lines.append("## Optional")
        lines.append("")
        for it in curated.optional:
            if it.note:
                lines.append(f"- [{it.title}]({it.url}): {it.note}")
            else:
                lines.append(f"- [{it.title}]({it.url})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
