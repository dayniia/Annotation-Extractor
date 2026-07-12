"""
cli.py — Command-line interface for the highlight extractor (Milestone 6).

Usage:
    extract <file> [--export md,anki,notion] [--out <dir>] [--organize] [--json]

Examples:
    extract notes.pdf --export md,anki
    extract thesis.docx --export md --out ./output
    extract notes.pdf --organize            # requires GEMINI_API_KEY
    extract notes.pdf --json                # raw JSON to stdout
"""

from __future__ import annotations

import sys
import io

# Fix Windows terminal Unicode issues (cp1252 -> utf-8)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
from pathlib import Path

from highlight_extractor import extract, supported_extensions, highlights_to_json
from highlight_extractor.exporters import export_markdown, export_anki, export_notion_md
from highlight_extractor.dispatcher import supported_extensions


EXPORT_MAP = {
    "md": ("highlights.md", export_markdown),
    "anki": ("highlights_anki.txt", export_anki),
    "notion": ("highlights_notion.md", export_notion_md),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract",
        description=(
            "Extract highlight annotations from PDF or DOCX files and export them "
            "as Markdown, Anki flashcards, or Notion-flavored Markdown."
        ),
    )
    parser.add_argument(
        "file",
        help="Path to the source document (.pdf or .docx).",
    )
    parser.add_argument(
        "--export",
        default="",
        metavar="FORMATS",
        help=(
            "Comma-separated list of export formats to produce. "
            f"Available: {', '.join(EXPORT_MAP)}. "
            "Example: --export md,anki"
        ),
    )
    parser.add_argument(
        "--out",
        default=".",
        metavar="DIR",
        help="Output directory for exported files (default: current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON schema output to stdout instead of (or in addition to) exporting.",
    )
    parser.add_argument(
        "--organize",
        action="store_true",
        help=(
            "[Milestone 8] Use Google Gemini to cluster and summarize highlights. "
            "Requires the GEMINI_API_KEY environment variable to be set."
        ),
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-1.5-flash",
        metavar="MODEL",
        help="Gemini model to use with --organize (default: gemini-1.5-flash).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[error] File not found: {file_path}", file=sys.stderr)
        return 1

    ext = file_path.suffix.lower()
    if ext not in supported_extensions():
        print(
            f"[error] Unsupported format: {ext!r}. "
            f"Supported: {', '.join(supported_extensions())}",
            file=sys.stderr,
        )
        return 1

    # ── Extract ──────────────────────────────────────────────────────────────
    print(f"[extract] Reading {file_path.name} …")
    try:
        highlights = extract(file_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if not highlights:
        print("[extract] No highlights found in the document.")
        return 0

    print(f"[extract] Found {len(highlights)} highlight(s).")

    # ── JSON output ──────────────────────────────────────────────────────────
    if args.json:
        print(highlights_to_json(highlights))

    # ── AI organization (optional) ────────────────────────────────────────
    clusters = None
    if args.organize:
        print("[organize] Sending highlights to Gemini for thematic clustering …")
        try:
            from highlight_extractor.ai_organizer import organize, export_clustered_markdown
            clusters = organize(highlights, model=args.gemini_model)
            print(f"[organize] Produced {len(clusters)} cluster(s).")
        except ImportError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        except EnvironmentError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"[error] AI organization failed: {exc}", file=sys.stderr)
            return 1

    # ── Export ────────────────────────────────────────────────────────────────
    requested = [f.strip() for f in args.export.split(",") if f.strip()]
    if not requested and not args.json:
        # Default: print markdown to stdout if no output flags given
        print(export_markdown(highlights))
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for fmt in requested:
        if fmt not in EXPORT_MAP:
            print(f"[warn] Unknown export format {fmt!r}, skipping.", file=sys.stderr)
            continue

        filename, exporter_fn = EXPORT_MAP[fmt]
        out_path = out_dir / filename

        # If clusters are available and we're doing md/notion, use the clustered version
        if clusters is not None and fmt in ("md", "notion"):
            from highlight_extractor.ai_organizer import export_clustered_markdown
            content = export_clustered_markdown(clusters)
        else:
            content = exporter_fn(highlights)

        out_path.write_text(content, encoding="utf-8")
        print(f"[export] Wrote {fmt} → {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
