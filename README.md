# Annotation Extractor

Extract annotations (highlights, underlines, strikeouts, and notes) from **PDF** and **DOCX** files and export them as clean, structured data — grouped by page/section, in reading order, with annotation color and timestamps preserved.

---

## Features

| Feature | Status |
|---|---|
| PDF annotation extraction (highlights, underlines, strikeouts, text notes) | ✅ |
| Scanned/image PDF detection (graceful failure) | ✅ |
| DOCX highlight extraction (WD_COLOR_INDEX, run merging) | ✅ |
| Unified schema (source-format-agnostic output) | ✅ |
| Markdown, PDF, and DOCX export | ✅ |
| Anki flashcard and Notion-flavored Markdown export | ✅ |
| Web UI (FastAPI + Vanilla JS) with interactive filtering | ✅ |
| AI thematic clustering & summarization via Gemini | ✅ |
| CLI (`extract <file> --export md,anki`) | ✅ |

---

## Installation

```bash
# Core CLI (PDF + DOCX extraction, non-AI exports)
pip install -e .

# With AI organization support
pip install -e ".[ai]"

# Install API requirements for the Web UI
pip install -r requirements-api.txt
```

---

## Web UI (Recommended)

Start the local API and frontend server:

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```
Then open `http://127.0.0.1:8000` in your browser.

**Note on AI Summarization:** To use the AI summary feature in the UI, you must create a `.env` file in the project root and add your Gemini API key. See `.env.example` for details.

---

## CLI Quick Start

```bash
# Extract and print Markdown to stdout
extract my_notes.pdf

# Export to Markdown + Anki flashcards
extract my_notes.pdf --export md,anki --out ./output

# Export with AI clustering (requires GEMINI_API_KEY)
export GEMINI_API_KEY=your_key_here
extract my_notes.pdf --export md --organize

# Dump raw JSON schema
extract my_notes.docx --json
```

---

## Output Schema

Every annotation (regardless of source format) is represented as:

```json
{
  "id": "uuid-string",
  "source_format": "pdf",
  "annotation_type": "highlight",
  "location": "page 4",
  "color": "yellow",
  "text": "The highlighted text",
  "note": "Attached comment, or null",
  "timestamp": "2026-07-12T19:46:23Z",
  "order": 0
}
```

For DOCX files, `color` is a color name string (e.g. `"yellow"`, `"cyan"`) and `location` is `"paragraph 12"`.

---

## Known Limitations

- **Scanned PDFs**: Pages with no text layer are detected and skipped with a warning. OCR is not performed.
- **DOCX comments**: Comment threading is not yet extracted (noted as future work). Only the highlight text and color are captured.
- **Complex DOCX formatting**: Heavily formatted documents (e.g. tables, text boxes) may not yield highlights from non-paragraph content.

---

## Supported Formats

| Extension | Notes |
|---|---|
| `.pdf` | Requires a text layer. Acrobat, browser-saved, and ebook-export PDFs supported. |
| `.docx` | Standard Word documents. `.doc` (legacy) is not supported. |

---

## Project Structure

```
.
├── api/                # FastAPI backend serving UI and endpoints
├── frontend/           # Vanilla JS/CSS frontend interface
├── highlight_extractor/# Core Python library
│   ├── __init__.py         # Public API
│   ├── schema.py           # Shared Annotation dataclass
│   ├── dispatcher.py       # Format router
│   ├── pdf_extractor.py    # PDF extraction (PyMuPDF)
│   ├── docx_extractor.py   # DOCX extraction (python-docx)
│   ├── exporters.py        # Exporters (MD, PDF, DOCX, Anki, Notion)
│   ├── ai_organizer.py     # Gemini AI clustering (optional)
│   └── cli.py              # Command-line interface
```