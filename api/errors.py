"""
errors.py — Custom exception types for the highlight extractor API.

These map cleanly to HTTP status codes in main.py.
They can also be raised by core (extractor) code and caught here.
"""

from __future__ import annotations


class UnsupportedFormatError(ValueError):
    """Raised when a file extension is not supported."""
    http_status = 400


class NoTextLayerError(RuntimeError):
    """Raised when a PDF has no selectable text layer (scanned image)."""
    http_status = 422


class ExtractionError(RuntimeError):
    """General extraction failure."""
    http_status = 500
