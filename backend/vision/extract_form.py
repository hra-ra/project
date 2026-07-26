"""
extract_form.py

Vision-based document extraction using Google's Gemini API (free tier).
Sends a scanned form image, gets back structured JSON with per-field
confidence scores, and routes the result based on confidence thresholds
(auto-apply / needs-review).
"""

import json
import os
import re
from dataclasses import dataclass

from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"

FIELD_CONFIDENCE_THRESHOLD = 0.75
OVERALL_CONFIDENCE_THRESHOLD = 0.70

EXTRACTION_SYSTEM_PROMPT = """You are a document extraction engine for a school administration system.
You will be shown an image of a scanned or photographed physical form (e.g. a teacher leave application).

Extract the following fields if present: teacher_name, date, reason, submitted_by, sections_affected.

For EACH field, provide:
  - "value": your best-effort extracted value (string). If illegible or absent, use null — never guess or hallucinate a plausible-sounding value.
  - "confidence": a float 0.0-1.0 representing YOUR OWN certainty in that specific field's value, based on handwriting legibility, image quality, and ambiguity. Be honest and conservative — do not default to high confidence.

The form may mix languages (e.g. Hindi and English) or use non-standard date formats. Extract in the original script/language; do not translate.

Respond with ONLY valid JSON, no markdown fences, no preamble, in exactly this shape:

{
  "fields": {
    "teacher_name": {"value": "...", "confidence": 0.0},
    "date": {"value": "...", "confidence": 0.0},
    "reason": {"value": "...", "confidence": 0.0},
    "submitted_by": {"value": "...", "confidence": 0.0},
    "sections_affected": {"value": "...", "confidence": 0.0}
  },
  "overall_confidence": 0.0,
  "notes": "brief note on any quality issues (skew, blur, torn corner, mixed script, etc.) or empty string if none"
}
"""


@dataclass
class ExtractionResult:
    fields: dict
    overall_confidence: float
    notes: str
    status: str
    flagged_fields: list


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def extract_form_data(image_bytes: bytes, media_type: str = "image/jpeg") -> ExtractionResult:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=media_type),
            "Extract the fields from this form image per your instructions.",
        ],
        config=types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            max_output_tokens=1000,
        ),
    )

    raw_text = response.text or ""
    print("--- Raw Gemini response ---")
    print(raw_text)
    print("--- end raw response ---")
    return _parse_and_route(raw_text)


def _parse_and_route(raw_text: str) -> ExtractionResult:
    cleaned = _strip_json_fences(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return ExtractionResult(
            fields={},
            overall_confidence=0.0,
            notes=f"JSON parse failure: {e}",
            status="needs_review",
            flagged_fields=["__all__"],
        )

    fields = parsed.get("fields", {})
    overall_confidence = float(parsed.get("overall_confidence", 0.0))
    notes = parsed.get("notes", "")

    flagged_fields = []
    for name, field_data in fields.items():
        confidence = field_data.get("confidence", 0.0)
        value = field_data.get("value")
        if value is None or confidence < FIELD_CONFIDENCE_THRESHOLD:
            flagged_fields.append(name)

    if overall_confidence < OVERALL_CONFIDENCE_THRESHOLD or flagged_fields:
        status = "needs_review"
    else:
        status = "auto_applied"

    return ExtractionResult(
        fields=fields,
        overall_confidence=overall_confidence,
        notes=notes,
        status=status,
        flagged_fields=flagged_fields,
    )