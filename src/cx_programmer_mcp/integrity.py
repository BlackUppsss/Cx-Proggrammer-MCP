from __future__ import annotations

import hashlib
from typing import Any

from .cxt import CxtProject


def _protected_projection(text: str) -> str:
    """Return all CXT content except the program-editable surfaces.

    Editable surfaces are the entire Programs block (including local symbols) and the
    GlobalVariables block. Everything else is protected against accidental mutation.
    """
    p = CxtProject(text)
    ranges: list[tuple[int, int, str]] = []
    try:
        b = p._programs_block()
        ranges.append((b.header, b.end, "<PROGRAMS_EDITABLE>"))
    except Exception:
        pass
    try:
        b = p._find_block(r"^\s*GlobalVariables:=\s*$")
        ranges.append((b.header, b.end, "<GLOBAL_VARIABLES_EDITABLE>"))
    except Exception:
        pass
    lines = p.lines[:]
    for start, end, marker in sorted(ranges, reverse=True):
        lines[start:end + 1] = [marker]
    return "\n".join(lines)


def protected_fingerprint(text: str) -> str:
    return hashlib.sha256(_protected_projection(text).encode("utf-8")).hexdigest()


def scope_integrity(original_text: str, current_text: str) -> dict[str, Any]:
    before = protected_fingerprint(original_text)
    after = protected_fingerprint(current_text)
    return {"ok": before == after, "original_sha256": before, "current_sha256": after}
