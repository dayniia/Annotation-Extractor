"""
highlight_extractor — Highlight extraction and export tool.

Public API:
    from highlight_extractor import extract, supported_extensions
    from highlight_extractor.exporters import export_markdown, export_anki, export_notion_md
    from highlight_extractor.ai_organizer import organize  # optional
"""

from .dispatcher import extract, supported_extensions
from .schema import Highlight, highlights_to_json

__all__ = [
    "extract",
    "supported_extensions",
    "Highlight",
    "highlights_to_json",
]
