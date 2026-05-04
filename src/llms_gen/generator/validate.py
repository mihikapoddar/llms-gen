from __future__ import annotations

import re

_H1 = re.compile(r"^#\s+.+$", re.MULTILINE)
_LIST_LINK = re.compile(
    r"^-\s+\[[^\]]+\]\([^)]+\)(?::\s*.+)?$",
)


def validate_llms_txt(text: str) -> list[str]:
    """Return human-readable issues; empty list means basic checks passed."""
    issues: list[str] = []
    if not text.strip():
        return ["File is empty"]
    if not _H1.search(text):
        issues.append("Missing H1 title line (# …)")
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("- [") and "](" in s:
            if not _LIST_LINK.match(s):
                issues.append(
                    f"Line {i}: expected '- [title](url)' or with ': note' (check brackets/URL)"
                )
    return issues[:25]
