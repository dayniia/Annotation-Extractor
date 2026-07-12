"""
ai_organizer.py — AI summary layer.

Uses the Google Gemini API (google-genai SDK) to:
  1. Treat all highlights as a single document.
  2. Generate a detailed summary of the content.

This module is entirely optional — the rest of the tool works unchanged
if it is never imported.
"""

from __future__ import annotations

import json
import os
from typing import Union

# Load .env early so GEMINI_API_KEY is always available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .schema import Highlight


def summarize(
    highlights: list[Highlight],
    api_key: Union[str, None] = None,
    model: Union[str, None] = None,
) -> str:
    """
    Summarize highlights using Google Gemini.

    Parameters
    ----------
    highlights:
        The list of Highlight objects from any extractor.
    api_key:
        Gemini API key. If None, reads from the GEMINI_API_KEY environment variable.
    model:
        Gemini model name to use. Falls back to GEMINI_MODEL env var,
        then 'gemini-2.0-flash-lite'.

    Returns
    -------
    str
        A detailed summary of the highlights.

    Raises
    ------
    ImportError
        If google-genai is not installed.
    EnvironmentError
        If no API key is found.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError(
            "google-genai is required for AI organization. Install it with:\n"
            "  pip install google-genai"
        ) from exc

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise EnvironmentError(
            "No Gemini API key found. Set GEMINI_API_KEY in your .env file "
            "or as an environment variable."
        )

    # Model fallback: arg → GEMINI_MODEL env var → hardcoded default
    effective_model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-lite")

    client = genai.Client(api_key=key)

    # Build compact payload
    hl_payload = [
        {
            "location": h.location,
            "text": h.text,
        }
        for h in highlights
    ]

    prompt = f"""You are a research assistant helping summarize reading highlights.

Below is a JSON array of highlights extracted from a document.

Your task:
Treat all the highlights as a single document and write a detailed summary. 
The summary should be comprehensive—not too short and not too long.
Do not summarize each highlight individually. Instead, synthesize the overall meaning and themes.

Return ONLY valid JSON in this exact structure, with no extra prose, no markdown fences:
{{
  "summary": "your detailed summary paragraph(s) here"
}}

Highlights:
{json.dumps(hl_payload, indent=2)}
"""

    response = client.models.generate_content(
        model=effective_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()

    # Strip markdown code fences if the model ignores mime_type instruction
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned non-JSON output. Raw response:\n{raw}"
        ) from exc

    return data.get("summary", "No summary generated.")
