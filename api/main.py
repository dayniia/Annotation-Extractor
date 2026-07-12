"""
main.py — FastAPI application (Milestone 8).

Thin adapter over highlight_extractor core.
Zero business logic in route handlers — all logic lives in core.

Endpoints:
  POST /extract   — upload a file, get highlight JSON back
  POST /export    — send highlight JSON + format, get a file download
  POST /organize  — send highlight JSON, get AI clusters back (Milestone 10)
  GET  /          — serves frontend/index.html
  GET  /static/*  — serves frontend static assets

Run with:
  uvicorn api.main:app --reload
"""

from __future__ import annotations

import os
import tempfile

# Load .env automatically (no-op if python-dotenv is not installed)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass
from pathlib import Path
from typing import Annotated
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from highlight_extractor import extract as core_extract, supported_extensions, highlights_to_json
from highlight_extractor.exporters import export_markdown, export_anki, export_notion_md, export_pdf, export_docx
from highlight_extractor.schema import Highlight

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Annotation Extractor API",
    description=(
        "Extract and export highlight annotations from PDF and DOCX files. "
        "Thin REST layer over the highlight_extractor core library."
    ),
    version="0.1.0",
)

# Configure Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure Logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key: str = Depends(api_key_header)):
    # In development mode, skip auth entirely for convenience
    env = os.environ.get("ENV", "development").lower()
    if env != "production":
        return "dev-bypass"

    expected_key = os.environ.get("APP_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="APP_API_KEY is not configured on the server. Admin must set this in .env.",
        )
    if api_key == expected_key:
        return api_key
    raise HTTPException(status_code=401, detail="Invalid API Key.")

# CORS — allow all origins in dev. In production, restrict this.
env_str = os.environ.get("ENV", "development").lower()
allowed_origins = ["*"] if env_str != "production" else [] # In production, restrict to actual domains

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ---------------------------------------------------------------------------
# Helper: deserialize highlight dicts back to Highlight objects
# ---------------------------------------------------------------------------

def _dicts_to_highlights(data: list[dict]) -> list[Highlight]:
    return [
        Highlight(
            id=d["id"],
            source_format=d["source_format"],
            annotation_type=d.get("annotation_type", "highlight"),
            location=d["location"],
            color=d["color"],
            text=d["text"],
            note=d.get("note"),
            timestamp=d.get("timestamp"),
            order=d["order"],
        )
        for d in data
    ]



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post(
    "/extract",
    summary="Extract highlights from a file",
    response_description="JSON array of highlight objects",
)
@limiter.limit("10/minute")
async def extract_highlights(request: Request, file: UploadFile = File(...), include_formatting: bool = Form(False), api_key: str = Depends(get_api_key)):
    """
    Upload a PDF or DOCX file and receive its highlights as a JSON array.

    - **400** — unsupported file format
    - **422** — PDF has no text layer (scanned/image PDF)
    - **500** — unexpected extraction error
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in supported_extensions():
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {suffix!r}. Supported: {', '.join(supported_extensions())}",
        )

    # Save upload to a temp file (core extract() needs a path, not a stream)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        highlights = core_extract(tmp_path, include_formatting=include_formatting)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        # Covers unsupported format + cannot-open errors
        msg = str(exc)
        if "no text layer" in msg.lower() or "scanned" in msg.lower():
            raise HTTPException(status_code=422, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as exc:
        logger.error(f"Extraction failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred during extraction.")
    finally:
        tmp_path.unlink(missing_ok=True)

    return [h.to_dict() for h in highlights]


@app.post(
    "/export",
    summary="Export highlights to a file format",
    response_description="The exported file content as plain text",
)
@limiter.limit("20/minute")
async def export_highlights(request: Request, api_key: str = Depends(get_api_key)):
    """
    Accept a JSON body with `highlights` (array) and `format` (\"md\", \"anki\", or \"notion\").
    Optionally accepts a `template` field (\"simple\" or \"reading_notes\").
    Returns the exported file as a downloadable response.
    """
    body = await request.json()
    highlights_data = body.get("highlights", [])
    fmt = body.get("format", "md").lower().strip()
    template = body.get("template", "simple").lower().strip()

    if not highlights_data:
        raise HTTPException(status_code=400, detail="No highlights provided.")

    EXPORTERS = {
        "md": ("highlights.md", "text/markdown", export_markdown),
        "anki": ("highlights_anki.txt", "text/plain", export_anki),
        "notion": ("highlights_notion.md", "text/markdown", export_notion_md),
        "pdf": ("highlights.pdf", "application/pdf", export_pdf),
        "docx": ("highlights.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", export_docx),
    }
    if fmt not in EXPORTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format: {fmt!r}. Choose from: {', '.join(EXPORTERS)}",
        )

    try:
        highlights = _dicts_to_highlights(highlights_data)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid highlight data: {exc}")

    filename, media_type, exporter_fn = EXPORTERS[fmt]
    # Pass template to exporter (only md, pdf, docx care, but we'll pass it to all and they can ignore if not needed, or just support it)
    content = exporter_fn(highlights, template=template)
    
    if isinstance(content, str):
        content = content.encode("utf-8")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post(
    "/summarize",
    summary="AI detailed summary of highlights",
    response_description="A detailed summary of the highlights",
)
@limiter.limit("5/minute")
async def summarize_highlights(request: Request, api_key: str = Depends(get_api_key)):
    """
    Send highlights through the Gemini AI layer to get a single detailed summary.

    Requires `GEMINI_API_KEY` environment variable to be set on the server.

    - **503** — Gemini API key not configured
    - **502** — Gemini call failed
    """
    body = await request.json()
    highlights_data = body.get("highlights", [])
    # Prefer explicit request body field; fall back to env var, then default
    default_model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    model = body.get("model") or default_model

    if not highlights_data:
        raise HTTPException(status_code=400, detail="No highlights provided.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set on the server. AI summary is unavailable.",
        )

    try:
        highlights = _dicts_to_highlights(highlights_data)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid highlight data: {exc}")

    try:
        from highlight_extractor.ai_organizer import summarize
        summary_text = summarize(highlights, api_key=api_key, model=model)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"AI summary failed: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="An internal server error occurred during AI summarization.")

    return {"summary": summary_text}


# ---------------------------------------------------------------------------
# Serve frontend (must be last so API routes take priority)
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def no_frontend():
        return HTMLResponse(
            "<h2>Frontend not found.</h2>"
            "<p>Build the frontend or run from the project root.</p>"
            "<p><a href='/docs'>API docs →</a></p>"
        )
