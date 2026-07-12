"""
schema.py — Shared data model for all highlight extractors.

Every extractor produces list[Highlight].  Nothing downstream should
ever need to know which format the highlight came from.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json


@dataclass
class Highlight:
    """One extracted highlight annotation."""

    id: str
    source_format: str          # "pdf" | "docx"
    annotation_type: str        # "highlight" | "underline" | "strikeout" | "note"
    location: str               # "page 4" | "paragraph 12" | etc.
    color: str                  # canonical lowercase palette name (yellow, green, cyan, etc.)
    text: str
    note: str | None            # attached comment/note, if any
    timestamp: str | None       # ISO 8601 datetime string, or None if unavailable
    order: int                  # reading order index (0-based, per-document)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def highlights_to_json(highlights: list[Highlight], indent: int = 2) -> str:
    """Serialize a list of Highlight objects to a JSON string."""
    return json.dumps([h.to_dict() for h in highlights], ensure_ascii=False, indent=indent)
