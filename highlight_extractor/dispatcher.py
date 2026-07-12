"""
dispatcher.py — Format-aware dispatcher.

Picks the right extractor based on file extension and calls
extract(file_path) -> list[Highlight].

Adding a new format later means: write one new extractor module,
register it here. No other file changes needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .schema import Highlight

# Registry: extension (lower-case, with dot) -> extractor module
_REGISTRY: dict[str, str] = {
    ".pdf": "highlight_extractor.pdf_extractor",
    ".docx": "highlight_extractor.docx_extractor",
}


def extract(file_path: Union[str, Path], include_formatting: bool = False) -> list[Highlight]:
    """
    Dispatch extraction to the appropriate format-specific extractor.

    Parameters
    ----------
    file_path:
        Path to the source document.

    Returns
    -------
    list[Highlight]
        All highlights in reading order, using the shared schema.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported file format: {ext!r}. "
            f"Supported formats: {supported}"
        )

    import importlib
    module = importlib.import_module(_REGISTRY[ext])
    if ext == ".docx":
        return module.extract(file_path, include_formatting=include_formatting)
    return module.extract(file_path)


def supported_extensions() -> list[str]:
    """Return the list of supported file extensions."""
    return sorted(_REGISTRY.keys())
