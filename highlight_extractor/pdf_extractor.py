"""
pdf_extractor.py — PDF highlight extractor using PyMuPDF (fitz).

Milestone 1: Parse Highlight annotations via quad points, stitch
multi-line highlights into one string, capture color, output in
reading order.

Milestone 2 additions:
- Detect scanned/image PDFs and report gracefully instead of crashing.
- Capture attached popup notes/comments.
- Tested against Acrobat, browser-saved, and ebook-export PDFs.
"""

from __future__ import annotations

import uuid
import datetime
from pathlib import Path
from typing import Union

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required for PDF extraction. Install it with:\n"
        "  pip install pymupdf"
    ) from exc

from .schema import Highlight


# ---------------------------------------------------------------------------
# Canonical color palette (lowercase, matches WD_COLOR_INDEX names)
# ---------------------------------------------------------------------------

# Each entry: (canonical_name, (R, G, B)) — R/G/B in 0-255 range.
#
# We include both theoretical pure values AND real-world PDF annotation values
# as observed from common PDF readers (Acrobat, browser-save, ebook exports).
# Multiple entries per name are fine — snapping picks the nearest one.
_PALETTE: list[tuple[str, tuple[int, int, int]]] = [
    # Yellow — pure + common soft variants
    ("yellow",      (255, 255, 0)),
    ("yellow",      (255, 240, 102)),   # Acrobat/browser soft yellow
    ("yellow",      (255, 255, 102)),

    # Green — pure + soft
    ("green",       (0, 255, 0)),
    ("green",       (125, 240, 102)),   # common soft green
    ("green",       (144, 238, 144)),   # light green

    # Cyan / turquoise
    ("cyan",        (0, 255, 255)),
    ("turquoise",   (64, 224, 208)),
    ("turquoise",   (0, 206, 209)),

    # Pink — real PDF pink is a warm rose, NOT hot-pink or violet
    ("pink",        (255, 182, 193)),   # light pink (HTML)
    ("pink",        (247, 153, 209)),   # Acrobat/Reader actual pink annotation
    ("pink",        (255, 153, 204)),   # Office pink
    ("pink",        (255, 105, 180)),   # hot pink fallback

    # Red
    ("red",         (255, 0, 0)),
    ("red",         (235, 73,  73)),    # common soft red annotation
    ("red",         (255, 99,  71)),    # tomato

    # Dark red
    ("dark_red",    (139, 0, 0)),
    ("dark_red",    (165, 42, 42)),     # brown-red

    # Blue — real PDF light-blue sits here, NOT near gray
    ("blue",        (0, 0, 255)),
    ("blue",        (143, 222, 249)),   # Acrobat/Reader light-blue annotation
    ("blue",        (100, 149, 237)),   # cornflower blue
    ("blue",        (173, 216, 230)),   # light blue

    # Dark blue
    ("dark_blue",   (0, 0, 139)),
    ("dark_blue",   (0, 0, 205)),

    # Teal
    ("teal",        (0, 128, 128)),
    ("teal",        (32, 178, 170)),    # light sea green

    # Violet / purple — clearly separated from pink now
    ("violet",      (238, 130, 238)),
    ("violet",      (148, 0, 211)),
    ("violet",      (186, 85, 211)),    # medium orchid

    # Dark yellow / orange
    ("dark_yellow", (204, 153, 0)),
    ("dark_yellow", (255, 165, 0)),     # orange

    # Grays — only pure grays snap here
    ("gray_50",     (128, 128, 128)),
    ("gray_25",     (192, 192, 192)),

    # Black / white
    ("black",       (0, 0, 0)),
    ("white",       (255, 255, 255)),
]


def _snap_color(r: float, g: float, b: float) -> str:
    """
    Snap an RGB float triple (0.0–1.0 each) to the nearest canonical palette name.
    Uses squared Euclidean distance in 0-255 space.
    """
    r255, g255, b255 = round(r * 255), round(g * 255), round(b * 255)
    best_name = "yellow"
    best_dist = float("inf")
    for name, (pr, pg, pb) in _PALETTE:
        dist = (r255 - pr) ** 2 + (g255 - pg) ** 2 + (b255 - pb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _color_from_annot(annot: fitz.Annot) -> str:
    """Return canonical lowercase color name from a fitz annotation."""
    colors = annot.colors
    # fitz stores highlight colour under "stroke" as (r, g, b) floats 0-1
    rgb_float = colors.get("stroke") or colors.get("fill") or (1.0, 1.0, 0.0)
    return _snap_color(*rgb_float)


def _extract_text_under_annot(page: fitz.Page, annot: fitz.Annot) -> str:
    """
    Extract the text covered by a highlight annotation.

    Strategy:
      1. Use quad points to get exact covered areas — most reliable.
      2. Fall back to the annotation rect if no quads are available.
    """
    words = page.get_text("words")  # list of (x0, y0, x1, y1, word, block, line, word_idx)

    quads = annot.vertices  # flat list of (x,y) pairs; each quad = 4 points
    if quads:
        # Group into sets of 4 corner points (one quad per text line)
        quad_rects: list[fitz.Rect] = []
        for i in range(0, len(quads), 4):
            pts = quads[i : i + 4]
            if len(pts) == 4:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                quad_rects.append(fitz.Rect(min(xs), min(ys), max(xs), max(ys)))
        covered_rects = quad_rects
    else:
        covered_rects = [annot.rect]

    # Collect words whose centre point falls inside any covered rect
    collected: list[tuple] = []
    for w in words:
        wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
        cx, cy = (wx0 + wx1) / 2, (wy0 + wy1) / 2
        for r in covered_rects:
            if r.contains(fitz.Point(cx, cy)):
                collected.append(w)
                break

    if not collected:
        # Nothing matched via centre-point; try bounding-box overlap as fallback
        for w in words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            wbbox = fitz.Rect(wx0, wy0, wx1, wy1)
            for r in covered_rects:
                if not r.intersect(wbbox).is_empty:
                    collected.append(w)
                    break

    # Sort in reading order: top-to-bottom, left-to-right
    collected.sort(key=lambda w: (round(w[1], 1), w[0]))

    # Stitch words with space; preserve line breaks when y-gap is large
    if not collected:
        return ""

    result_parts: list[str] = []
    prev_y1 = None
    for w in collected:
        if prev_y1 is not None and w[1] > prev_y1 + 2:
            result_parts.append(" ")  # treat as a single space across lines
        result_parts.append(w[4])
        prev_y1 = w[3]

    return " ".join(result_parts).strip()


def _get_popup_note(annot: fitz.Annot) -> Union[str, None]:
    """Return the text content of an attached popup note, or None."""
    info = annot.info
    note_text = info.get("content", "").strip()
    return note_text if note_text else None


def _page_has_text_layer(page: fitz.Page) -> bool:
    """Return True if the page has any selectable text (not a pure image scan)."""
    return bool(page.get_text("text").strip())


def _parse_pdf_date(pdf_date: str) -> Union[str, None]:
    """Convert a PDF date string (e.g. D:20231012140510Z) to ISO 8601, or None."""
    if not pdf_date or not pdf_date.startswith("D:"):
        return None
    # Extract the core YYYYMMDDHHmmss part
    core = pdf_date[2:16]
    if len(core) < 14:
        return None
    try:
        dt = datetime.datetime.strptime(core, "%Y%m%d%H%M%S")
        return dt.isoformat() + "Z"
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Public extractor
# ---------------------------------------------------------------------------

def extract(file_path: Union[str, Path]) -> list[Highlight]:
    """
    Extract all highlight annotations from a PDF.

    Parameters
    ----------
    file_path:
        Path to the PDF file.

    Returns
    -------
    list[Highlight]
        Highlights in reading order (page first, then top-to-bottom).

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not a PDF or cannot be opened.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {file_path.suffix!r}")

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    highlights: list[Highlight] = []
    order = 0
    scanned_pages: list[int] = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        if not _page_has_text_layer(page):
            scanned_pages.append(page_num + 1)
            # Don't crash — just skip and report at the end
            continue

        for annot in page.annots():
            atype = annot.type[0]
            if atype == fitz.PDF_ANNOT_HIGHLIGHT:
                annotation_type = "highlight"
            elif atype == fitz.PDF_ANNOT_UNDERLINE:
                annotation_type = "underline"
            elif atype == fitz.PDF_ANNOT_STRIKE_OUT:
                annotation_type = "strikeout"
            elif atype == fitz.PDF_ANNOT_TEXT:
                annotation_type = "note"
            else:
                continue

            text = _extract_text_under_annot(page, annot)
            note = _get_popup_note(annot)

            # For text annotations, text might be empty underneath it
            if not text and annotation_type != "note":
                continue
            if not text and annotation_type == "note":
                text = note or "Attached Note"
                note = None

            raw_date = annot.info.get("modDate") or annot.info.get("creationDate")
            timestamp = _parse_pdf_date(raw_date) if raw_date else None

            highlights.append(
                Highlight(
                    id=str(uuid.uuid4()),
                    source_format="pdf",
                    annotation_type=annotation_type,
                    location=f"page {page_num + 1}",
                    color=_color_from_annot(annot),
                    text=text,
                    note=note,
                    timestamp=timestamp,
                    order=order,
                )
            )
            order += 1

    doc.close()

    if scanned_pages:
        page_list = ", ".join(str(p) for p in scanned_pages)
        print(
            f"[highlight-extractor] WARNING: The following page(s) appear to be "
            f"scanned images with no text layer — highlights on these pages cannot "
            f"be extracted: {page_list}"
        )

    return highlights
