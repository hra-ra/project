"""
orchestrator.py

The agent that turns "a scanned leave form" into "an applied, explained
timetable change." This is Concept 4's connective tissue: it calls
vision extraction, looks up affected sessions via the DB layer, calls
the CP-SAT solver, and decides whether to auto-apply or hold for review.

Deliberately depends on the `SchoolDB` Protocol (see db.py), not the
concrete SupabaseDB class — this is what lets us test the full pipeline
logic below with a FakeDB and no live credentials or network calls.
"""

from datetime import datetime, date as date_cls

from db import SchoolDB
from solver.substitute_solver import Teacher, VacantSession, solve_substitutions
from vision.extract_form import ExtractionResult


class UnresolvableDateError(Exception):
    """Raised when the extracted date field can't be parsed into a real date."""


def _parse_date(raw: str) -> date_cls:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except (ValueError, TypeError):
            continue
    raise UnresolvableDateError(f"Could not parse date value: {raw!r}")


def _teacher_dict_to_dataclass(t: dict) -> Teacher:
    return Teacher(
        id=t["id"],
        name=t["name"],
        subjects=t["subjects"],
        max_periods_per_day=t["max_periods_per_day"],
        current_load_today=t["current_load_today"],
        substitution_count_month=t["substitution_count_month"],
        is_available=t.get("is_available", True),
    )


def _session_dict_to_vacant(s: dict) -> VacantSession:
    section = s.get("sections", {})
    section_label = f"Grade {section.get('grade')}-{section.get('section_label')}" if section else s["section_id"]
    return VacantSession(
        id=s["id"],
        section_label=section_label,
        subject=s["subject"],
        timeslot_id=s["timeslot_id"],
        original_teacher_id=s["teacher_id"],
    )


def _resolve_and_persist(teacher_name: str, date_raw: str, form_id: str, db: SchoolDB, extraction_summary: dict) -> dict:
    """
    Shared logic from 'we trust teacher_name + date' onward — used both
    by the automatic pipeline (process_leave_form) and by the human
    correction path (resolve_reviewed_form) after an admin fixes a
    flagged field. Keeping this in one place means both paths get
    identical solving/persistence behavior.
    """
    try:
        target_date = _parse_date(date_raw)
    except UnresolvableDateError as e:
        db.update_form_submission_status(form_id, "needs_review")
        return {
            "form_id": form_id,
            "status": "needs_review",
            "reason": str(e),
            "diff": None,
            **extraction_summary,
        }

    affected_sessions_raw = db.get_affected_sessions(teacher_name, target_date)
    if not affected_sessions_raw:
        db.update_form_submission_status(form_id, "applied")
        return {
            "form_id": form_id,
            "status": "applied",
            "reason": f"No scheduled sessions found for {teacher_name} on {target_date}. Nothing to reassign.",
            "diff": [],
            **extraction_summary,
        }

    all_teachers_raw = db.get_all_teachers()
    teachers = [_teacher_dict_to_dataclass(t) for t in all_teachers_raw]
    vacant_sessions = [_session_dict_to_vacant(s) for s in affected_sessions_raw]

    solve_result = solve_substitutions(vacant_sessions, teachers)

    session_by_id = {s["id"]: s for s in affected_sessions_raw}
    teacher_by_id = {t.id: t for t in teachers}

    diff = []
    any_unresolved = False
    for assignment in solve_result["assignments"]:
        session = session_by_id[assignment["session_id"]]
        original_teacher = teacher_by_id.get(session["teacher_id"])
        section = session.get("sections", {})
        session_label = f"Grade {section.get('grade')}-{section.get('section_label')} · {session['subject']}"

        if assignment["resolved"]:
            diff.append({
                "session_id": assignment["session_id"],
                "session_label": session_label,
                "field": "teacher",
                "old_value": original_teacher.name if original_teacher else "Unknown",
                "new_value": assignment["teacher_name"],
                "new_teacher_id": assignment["teacher_id"],
                "original_teacher_id": session["teacher_id"],
                "reasoning": assignment["reasoning"],
                "resolved": True,
            })
        else:
            any_unresolved = True
            diff.append({
                "session_id": assignment["session_id"],
                "session_label": session_label,
                "field": "teacher",
                "old_value": original_teacher.name if original_teacher else "Unknown",
                "new_value": None,
                "reasoning": assignment["reasoning"],
                "resolved": False,
                "fallback_candidates": assignment["fallback_candidates"],
            })

    if any_unresolved:
        db.update_form_submission_status(form_id, "needs_review")
        status = "needs_review"
    else:
        db.apply_diff(diff, form_id, solve_result["status"])
        db.update_form_submission_status(form_id, "applied")
        status = "applied"

    return {
        "form_id": form_id,
        "status": status,
        "solver_status": solve_result["status"],
        "reason": f"{teacher_name} — leave application, {target_date.strftime('%a %d %b')}",
        "diff": diff,
        **extraction_summary,
    }


def process_leave_form(extraction: ExtractionResult, db: SchoolDB) -> dict:
    """
    Given an already-extracted form (see vision/extract_form.py) and a
    DB implementation, runs the full resolution pipeline and returns a
    response shaped for the frontend's LedgerDiff/ReviewQueue components.
    """
    form_id = db.insert_form_submission({
        "fields": extraction.fields,
        "overall_confidence": extraction.overall_confidence,
        "status": extraction.status,
    })

    extraction_summary = {
        "extracted_fields": extraction.fields,
        "overall_confidence": extraction.overall_confidence,
    }

    # If extraction itself wasn't confident enough, stop here — never let
    # a low-confidence read drive a real scheduling change. The form_id
    # is returned so the frontend can later submit human corrections
    # against this same record via resolve_reviewed_form.
    if extraction.status == "needs_review":
        return {
            "form_id": form_id,
            "status": "needs_review",
            "reason": "Extraction confidence below threshold; awaiting manual review.",
            "flagged_fields": extraction.flagged_fields,
            "diff": None,
            **extraction_summary,
        }

    teacher_name = extraction.fields.get("teacher_name", {}).get("value")
    date_raw = extraction.fields.get("date", {}).get("value")

    return _resolve_and_persist(teacher_name, date_raw, form_id, db, extraction_summary)


def resolve_reviewed_form(form_id: str, corrected_fields: dict, db: SchoolDB) -> dict:
    """
    Called when a human reviews and corrects/confirms fields for a form
    that was previously flagged needs_review (e.g. filling in a teacher
    name the vision model couldn't read). Human-provided values are
    trusted at full confidence — they've already been checked by a
    person — and the same solve/persist pipeline runs from here.
    """
    fields_with_confidence = {
        k: {"value": v, "confidence": 1.0} for k, v in corrected_fields.items() if v
    }
    extraction_summary = {
        "extracted_fields": fields_with_confidence,
        "overall_confidence": 1.0,
    }
    teacher_name = corrected_fields.get("teacher_name")
    date_raw = corrected_fields.get("date")

    if not teacher_name or not date_raw:
        return {
            "form_id": form_id,
            "status": "needs_review",
            "reason": "Teacher name and date are both required to resolve this form.",
            "diff": None,
            **extraction_summary,
        }

    return _resolve_and_persist(teacher_name, date_raw, form_id, db, extraction_summary)