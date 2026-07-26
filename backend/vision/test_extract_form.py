"""
Tests the routing/validation logic in extract_form.py using mocked
model responses — no live API call or credentials needed. This proves
the confidence-gating behaves correctly across the cases that matter;
prompt-quality against a real scanned image still needs a live sanity
check once you have an API key and sample forms.

Run with: python test_extract_form.py
"""

import json
from extract_form import _parse_and_route


def test_high_confidence_auto_applies():
    raw = json.dumps({
        "fields": {
            "teacher_name": {"value": "Mr. Rao", "confidence": 0.96},
            "date": {"value": "2026-07-28", "confidence": 0.94},
            "reason": {"value": "Medical leave", "confidence": 0.91},
            "submitted_by": {"value": "Front Office", "confidence": 0.98},
            "sections_affected": {"value": "Grade 9-A, 9-B", "confidence": 0.89},
        },
        "overall_confidence": 0.94,
        "notes": "",
    })
    result = _parse_and_route(raw)
    assert result.status == "auto_applied", f"expected auto_applied, got {result.status}"
    assert result.flagged_fields == []
    print("PASS: high-confidence clean form -> auto_applied")


def test_one_bad_field_forces_review():
    raw = json.dumps({
        "fields": {
            "teacher_name": {"value": "Mr. Rao", "confidence": 0.95},
            "date": {"value": None, "confidence": 0.30},  # illegible date
            "reason": {"value": "Medical leave", "confidence": 0.90},
            "submitted_by": {"value": "Front Office", "confidence": 0.97},
            "sections_affected": {"value": "Grade 9-A", "confidence": 0.92},
        },
        "overall_confidence": 0.81,  # overall still looks fine in isolation
        "notes": "Date field smudged.",
    })
    result = _parse_and_route(raw)
    assert result.status == "needs_review", f"expected needs_review, got {result.status}"
    assert "date" in result.flagged_fields
    print("PASS: single low-confidence field -> needs_review, even with high overall score")


def test_low_overall_confidence_forces_review_even_if_fields_look_ok():
    raw = json.dumps({
        "fields": {
            "teacher_name": {"value": "Mr. Rao", "confidence": 0.80},
            "date": {"value": "2026-07-28", "confidence": 0.80},
            "reason": {"value": "Medical leave", "confidence": 0.80},
            "submitted_by": {"value": "Front Office", "confidence": 0.80},
            "sections_affected": {"value": "Grade 9-A", "confidence": 0.80},
        },
        "overall_confidence": 0.55,  # model itself flags systemic quality issue
        "notes": "Image heavily skewed and partially cropped.",
    })
    result = _parse_and_route(raw)
    assert result.status == "needs_review", f"expected needs_review, got {result.status}"
    print("PASS: low overall confidence -> needs_review despite individually-OK fields")


def test_malformed_json_never_silently_passes():
    raw = "Sure! Here's the extracted data: {not valid json at all"
    result = _parse_and_route(raw)
    assert result.status == "needs_review"
    assert result.flagged_fields == ["__all__"]
    print("PASS: malformed model output -> needs_review, not silently trusted")


def test_mixed_script_field_preserved_not_dropped():
    raw = json.dumps({
        "fields": {
            "teacher_name": {"value": "श्री राव (Mr. Rao)", "confidence": 0.88},
            "date": {"value": "28/07/2026", "confidence": 0.90},
            "reason": {"value": "चिकित्सा अवकाश", "confidence": 0.85},
            "submitted_by": {"value": "Front Office", "confidence": 0.95},
            "sections_affected": {"value": "Grade 9-A", "confidence": 0.90},
        },
        "overall_confidence": 0.89,
        "notes": "Mixed Hindi/English form.",
    })
    result = _parse_and_route(raw)
    assert result.status == "auto_applied"
    assert result.fields["teacher_name"]["value"] == "श्री राव (Mr. Rao)"
    print("PASS: mixed-script fields preserved and not mistranslated/dropped")


if __name__ == "__main__":
    test_high_confidence_auto_applies()
    test_one_bad_field_forces_review()
    test_low_overall_confidence_forces_review_even_if_fields_look_ok()
    test_malformed_json_never_silently_passes()
    test_mixed_script_field_preserved_not_dropped()
    print("\nAll extraction routing tests passed.")
