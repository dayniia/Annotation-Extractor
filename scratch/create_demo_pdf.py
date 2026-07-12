"""
create_demo_pdf.py — Creates a demo PDF with all four annotation types:
highlight, underline, strikeout, and text note (sticky note).
"""
import fitz  # PyMuPDF
from pathlib import Path
import datetime

def _stamp(annot, label=None):
    """Attach a visible timestamp to an annotation's content and set PDF modDate."""
    ts_display = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ts_pdf = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    existing = annot.info.get('content', '')
    if label:
        annot.info['content'] = f"{label} — {ts_display}"
    elif existing:
        annot.info['content'] = f"{existing} — {ts_display}"
    else:
        annot.info['content'] = f"Timestamp: {ts_display}"
    annot.set_info(modDate=f"D:{ts_pdf}Z")
    try:
        annot.update()
    except Exception:
        pass

def create_demo_pdf(output_path: str):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Insert some readable text blocks
    text_blocks = [
        (50, 80,  "Highlight Extractor — Demo Document", 18, True),
        (50, 120, "This file contains all four annotation types supported by the extractor.", 11, False),
        (50, 150, "Use it to verify extraction works end-to-end.", 11, False),
        (50, 200, "HIGHLIGHTED TEXT", 13, True),
        (50, 225, "The theory of relativity was developed by Albert Einstein in the early 20th century.", 11, False),
        (50, 260, "Quantum mechanics describes nature at the smallest scales of energy levels of atoms.", 11, False),
        (50, 310, "UNDERLINED TEXT", 13, True),
        (50, 335, "The speed of light in a vacuum is approximately 299,792 kilometres per second.", 11, False),
        (50, 360, "Gravity is a fundamental force that attracts objects with mass toward each other.", 11, False),
        (50, 410, "STRIKETHROUGH TEXT", 13, True),
        (50, 435, "This hypothesis has been thoroughly debunked by modern research.", 11, False),
        (50, 460, "The old model of the atom has been replaced by the quantum mechanical model.", 11, False),
        (50, 510, "TEXT NOTE (STICKY NOTE)", 13, True),
        (50, 535, "DNA carries the genetic instructions for the growth, development, and functioning of all life.", 11, False),
        (50, 560, "The structure of DNA was first described by Watson and Crick in 1953.", 11, False),
    ]

    for (x, y, text, size, bold) in text_blocks:
        flags = fitz.TEXT_FONT_BOLD if bold else 0
        page.insert_text(
            (x, y), text,
            fontsize=size,
            fontname="helv",
            color=(0.1, 0.1, 0.1)
        )

    # ── 1. HIGHLIGHT annotation ─────────────────────────────────────────────
    # Highlight the sentence about relativity
    hl_rect = fitz.Rect(50, 214, 545, 240)
    highlight = page.add_highlight_annot(hl_rect)
    highlight.set_colors(stroke=(1.0, 1.0, 0.0))  # Yellow
    highlight.info["title"] = "Reader"
    _stamp(highlight, label="Key physics concept")

    # Second highlight — blue
    hl_rect2 = fitz.Rect(50, 250, 545, 275)
    highlight2 = page.add_highlight_annot(hl_rect2)
    highlight2.set_colors(stroke=(0.56, 0.87, 0.98))  # Light blue
    _stamp(highlight2, label="Highlight")

    # ── 2. UNDERLINE annotation ─────────────────────────────────────────────
    ul_rect = fitz.Rect(50, 324, 545, 350)
    underline = page.add_underline_annot(ul_rect)
    underline.set_colors(stroke=(0.0, 0.5, 1.0))
    underline.info["content"] = "Important constant"
    _stamp(underline)

    ul_rect2 = fitz.Rect(50, 350, 545, 375)
    underline2 = page.add_underline_annot(ul_rect2)
    underline2.set_colors(stroke=(0.0, 0.5, 1.0))
    _stamp(underline2, label="Underline")

    # ── 3. STRIKEOUT annotation ─────────────────────────────────────────────
    st_rect = fitz.Rect(50, 424, 545, 450)
    strikeout = page.add_strikeout_annot(st_rect)
    strikeout.set_colors(stroke=(1.0, 0.0, 0.0))
    strikeout.info["content"] = "Outdated claim"
    _stamp(strikeout)

    st_rect2 = fitz.Rect(50, 450, 545, 475)
    strikeout2 = page.add_strikeout_annot(st_rect2)
    strikeout2.set_colors(stroke=(1.0, 0.0, 0.0))
    _stamp(strikeout2, label="Strikeout")

    # ── 4. TEXT NOTE (Sticky Note) annotation ─────────────────────────────
    note = page.add_text_annot((50, 524), "This is a sticky note comment attached near the DNA text.")
    note.set_colors(stroke=(1.0, 0.8, 0.0))
    note.info["title"] = "Reader"
    note.info["content"] = "This is a sticky note comment attached near the DNA text."
    _stamp(note)

    # ── Page 2 — more examples ──────────────────────────────────────────────
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 80), "Page 2 — Additional Annotations", fontsize=16, fontname="helv", color=(0.1, 0.1, 0.1))
    page2.insert_text((50, 120), "Machine learning is a branch of artificial intelligence.", fontsize=11, fontname="helv")
    page2.insert_text((50, 150), "Neural networks are modelled loosely on the human brain.", fontsize=11, fontname="helv")
    page2.insert_text((50, 190), "Climate change is the long-term shift in global temperatures and weather patterns.", fontsize=11, fontname="helv")

    # Green highlight on page 2
    hl_p2 = fitz.Rect(50, 110, 545, 135)
    h2 = page2.add_highlight_annot(hl_p2)
    h2.set_colors(stroke=(0.49, 0.94, 0.40))  # Green
    _stamp(h2, label="Highlight")

    # Pink highlight on page 2
    hl_p2b = fitz.Rect(50, 140, 545, 165)
    h2b = page2.add_highlight_annot(hl_p2b)
    h2b.set_colors(stroke=(1.0, 0.60, 0.80))  # Pink
    _stamp(h2b, label="Highlight")

    # Strikeout on page 2
    st_p2 = fitz.Rect(50, 180, 545, 205)
    s2 = page2.add_strikeout_annot(st_p2)
    s2.set_colors(stroke=(1.0, 0.0, 0.0))
    _stamp(s2, label="Strikeout")

    out = Path(output_path)
    doc.save(str(out))
    doc.close()
    print(f"Demo PDF saved to: {out}")

create_demo_pdf("frontend/demo.pdf")
