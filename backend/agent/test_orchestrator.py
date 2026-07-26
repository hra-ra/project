"""
test_orchestrator.py

Tests the FULL closed-loop pipeline (extraction result -> DB lookups ->
solver -> diff -> DB write) using a FakeDB that implements the SchoolDB
Protocol in-memory. No Supabase credentials, no live API calls, no
network — this proves the orchestration logic itself is correct.

Run with: python -m agent.test_orchestrator   (from the backend/ directory)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from agent.orchestrator import process_leave_form
from vision.extract_form import ExtractionResult


class FakeDB:
    """In-memory stand-in for SupabaseDB, mirroring the seeded demo scenario
    from supabase/seed.py exactly, so this test doubles as a regression
    check against the same data the solver test already validated."""

    def __init__(self):
        self.teachers = {
            "rao":    {"id": "rao", "name": "Mr. Rao", "subjects": ["Physics", "Math"], "max_periods_per_day": 6, "current_load_today": 4, "substitution_count_month": 1, "is_available": True},
            "iyer":   {"id": "iyer", "name": "Ms. Iyer", "subjects": ["Physics", "Chemistry"], "max_periods_per_day": 6, "current_load_today": 5, "substitution_count_month": 2, "is_available": True},
            "singh":  {"id": "singh", "name": "Mr. Singh", "subjects": ["Physics", "Biology"], "max_periods_per_day": 6, "current_load_today": 3, "substitution_count_month": 6, "is_available": True},
            "fatima": {"id": "fatima", "name": "Ms. Fatima", "subjects": ["Math", "Physics"], "max_periods_per_day": 6, "current_load_today": 2, "substitution_count_month": 0, "is_available": True},
        }
        # Monday (isoweekday=1) sessions where Mr. Rao teaches Physics to
        # two sections simultaneously — same conflict as the solver test.
        self.sessions = [
            {
                "id": "sess_9A", "subject": "Physics", "teacher_id": "rao",
                "section_id": "sec_9a", "timeslot_id": "mon_p1",
                "sections": {"grade": 9, "section_label": "A"},
                "timeslots": {"day_of_week": 1, "period_number": 1},
            },
            {
                "id": "sess_9B", "subject": "Physics", "teacher_id": "rao",
                "section_id": "sec_9b", "timeslot_id": "mon_p1",
                "sections": {"grade": 9, "section_label": "B"},
                "timeslots": {"day_of_week": 1, "period_number": 1},
            },
        ]
        self.form_submissions = {}
        self.applied_diffs = []
        self.next_id = 1

    def _new_id(self, prefix):
        self.next_id += 1
        return f"{prefix}_{self.next_id}"

    def get_all_teachers(self):
        return list(self.teachers.values())

    def get_affected_sessions(self, teacher_name, target_date):
        day_of_week = target_date.isoweekday()
        tid = next((tid for tid, t in self.teachers.items() if teacher_name in t["name"]), None)
        if not tid:
            return []
        return [
            s for s in self.sessions
            if s["teacher_id"] == tid and s["timeslots"]["day_of_week"] == day_of_week
        ]

    def insert_form_submission(self, extraction):
        fid = self._new_id("form")
        self.form_submissions[fid] = {**extraction, "status_history": [extraction["status"]]}
        return fid

    def update_form_submission_status(self, form_id, status):
        self.form_submissions[form_id]["status_history"].append(status)

    def apply_diff(self, diff, form_id, solver_status):
        vid = self._new_id("version")
        self.applied_diffs.append({"version_id": vid, "diff": diff, "solver_status": solver_status})
        for entry in diff:
            if entry.get("resolved"):
                for s in self.sessions:
                    if s["id"] == entry["session_id"]:
                        s["teacher_id"] = entry["new_teacher_id"]
                self.teachers[entry["new_teacher_id"]]["substitution_count_month"] += 1
        return vid

    def get_active_alerts(self):
        return []


def test_full_pipeline_resolves_both_conflicts():
    db = FakeDB()

    # A confident, clean extraction — mirrors mockData.ts's mockFormSubmission
    extraction = ExtractionResult(
        fields={
            "teacher_name": {"value": "Mr. Rao", "confidence": 0.96},
            "date": {"value": "2026-07-27", "confidence": 0.94},  # a Monday
            "reason": {"value": "Medical leave", "confidence": 0.91},
        },
        overall_confidence=0.94,
        notes="",
        status="auto_applied",
        flagged_fields=[],
    )

    result = process_leave_form(extraction, db)

    print(f"Status: {result['status']}")
    print(f"Solver status: {result.get('solver_status')}")
    for d in result["diff"]:
        print(f"  {d['session_label']}: {d['old_value']} -> {d['new_value']}")
        print(f"    reasoning: {d['reasoning']}")

    assert result["status"] == "applied", f"expected applied, got {result['status']}"
    assert len(result["diff"]) == 2
    assert all(d["resolved"] for d in result["diff"])
    assert len(db.applied_diffs) == 1, "expected exactly one timetable version written"

    # Confirm the DB was actually mutated, not just the response shaped correctly
    updated_teacher_ids = {s["teacher_id"] for s in db.sessions}
    assert "rao" not in updated_teacher_ids, "Rao's sessions should have been reassigned"

    print("\nPASS: full pipeline resolves both conflicts and persists the change")


def test_low_confidence_extraction_never_reaches_solver():
    db = FakeDB()

    extraction = ExtractionResult(
        fields={"teacher_name": {"value": None, "confidence": 0.2}},
        overall_confidence=0.35,
        notes="Heavily smudged.",
        status="needs_review",
        flagged_fields=["teacher_name"],
    )

    result = process_leave_form(extraction, db)

    assert result["status"] == "needs_review"
    assert result["diff"] is None
    assert len(db.applied_diffs) == 0, "solver/DB write must never fire on low-confidence extraction"

    print("PASS: low-confidence extraction halts before touching the solver or timetable")


def test_unparseable_date_halts_gracefully():
    db = FakeDB()

    extraction = ExtractionResult(
        fields={
            "teacher_name": {"value": "Mr. Rao", "confidence": 0.95},
            "date": {"value": "sometime next week??", "confidence": 0.9},  # garbage date, high confidence
        },
        overall_confidence=0.9,
        notes="",
        status="auto_applied",
        flagged_fields=[],
    )

    result = process_leave_form(extraction, db)

    assert result["status"] == "needs_review"
    assert len(db.applied_diffs) == 0
    print("PASS: unparseable date halts pipeline even when extraction confidence was high")


if __name__ == "__main__":
    test_full_pipeline_resolves_both_conflicts()
    test_low_confidence_extraction_never_reaches_solver()
    test_unparseable_date_halts_gracefully()
    print("\nAll orchestrator pipeline tests passed.")
