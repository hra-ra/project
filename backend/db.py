"""
db.py

Thin data-access layer over Supabase. Kept deliberately separate from
orchestration logic (see agent/orchestrator.py) so the pipeline can be
unit-tested against a FakeDB with no live Supabase credentials required —
the same pattern used for the solver and vision modules.

Anything that touches `supabase.Client` lives here. Nothing here makes
scheduling decisions — it only reads/writes rows.
"""

import os
from datetime import datetime, date
from typing import Protocol

from supabase import create_client, Client


class SchoolDB(Protocol):
    """Interface the orchestrator depends on. SupabaseDB implements this
    for real use; FakeDB (in tests) implements it for isolated testing."""

    def get_all_teachers(self) -> list[dict]: ...
    def get_affected_sessions(self, teacher_name: str, target_date: date) -> list[dict]: ...
    def insert_form_submission(self, extraction: dict) -> str: ...
    def update_form_submission_status(self, form_id: str, status: str) -> None: ...
    def apply_diff(self, diff: list[dict], form_id: str, solver_status: str) -> str: ...
    def get_active_alerts(self) -> list[dict]: ...
    def get_full_timetable(self) -> dict: ...


class SupabaseDB:
    def __init__(self):
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        self.client: Client = create_client(url, key)

    def get_all_teachers(self) -> list[dict]:
        res = self.client.table("teachers").select("*").eq("is_available", True).execute()
        return res.data

    def get_affected_sessions(self, teacher_name: str, target_date: date) -> list[dict]:
        day_of_week = target_date.isoweekday()

        teacher_res = (
            self.client.table("teachers").select("id").ilike("name", f"%{teacher_name}%").execute()
        )
        if not teacher_res.data:
            return []
        teacher_id = teacher_res.data[0]["id"]

        sessions_res = (
            self.client.table("class_sessions")
            .select("*, sections(grade, section_label), timeslots(day_of_week, period_number)")
            .eq("teacher_id", teacher_id)
            .execute()
        )
        return [
            s for s in sessions_res.data
            if s.get("timeslots", {}).get("day_of_week") == day_of_week
        ]

    def insert_form_submission(self, extraction: dict) -> str:
        res = self.client.table("form_submissions").insert({
            "form_type": "leave_application",
            "extracted_json": extraction["fields"],
            "overall_confidence": extraction["overall_confidence"],
            "status": extraction["status"],
        }).execute()
        return res.data[0]["id"]

    def update_form_submission_status(self, form_id: str, status: str) -> None:
        self.client.table("form_submissions").update({"status": status}).eq("id", form_id).execute()

    def apply_diff(self, diff: list[dict], form_id: str, solver_status: str) -> str:
        version_res = self.client.table("timetable_versions").insert({
            "triggered_by_form_id": form_id,
            "diff_json": diff,
            "solver_status": solver_status,
        }).execute()
        version_id = version_res.data[0]["id"]

        for entry in diff:
            if not entry.get("resolved"):
                continue
            self.client.table("class_sessions").update({
                "teacher_id": entry["new_teacher_id"],
                "is_substitute": True,
                "original_teacher_id": entry["original_teacher_id"],
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", entry["session_id"]).execute()

            self.client.table("substitution_log").insert({
                "class_session_id": entry["session_id"],
                "original_teacher_id": entry["original_teacher_id"],
                "substitute_teacher_id": entry["new_teacher_id"],
                "reasoning_text": entry["reasoning"],
                "timetable_version_id": version_id,
            }).execute()

            sub_teacher = self.client.table("teachers").select("substitution_count_month").eq(
                "id", entry["new_teacher_id"]
            ).execute().data[0]
            self.client.table("teachers").update({
                "substitution_count_month": sub_teacher["substitution_count_month"] + 1
            }).eq("id", entry["new_teacher_id"]).execute()

        return version_id

    def get_active_alerts(self) -> list[dict]:
        res = self.client.table("alerts").select("*").eq("resolved", False).order(
            "created_at", desc=True
        ).execute()
        return res.data

    def get_full_timetable(self) -> dict:
        """
        Returns the live timetable shaped for the dashboard grid:
        { "Mon P1": [{section, subject, teacher, room, is_substitute}, ...], ... }
        """
        day_labels = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}

        res = (
    self.client.table("class_sessions")
    .select(
        "*, sections(grade, section_label), "
        "teachers!class_sessions_teacher_id_fkey(name), "
        "rooms(name), timeslots(day_of_week, period_number)"
    )
    .execute()
)

        grid: dict[str, list[dict]] = {}
        for row in res.data:
            ts = row.get("timeslots") or {}
            day_label = day_labels.get(ts.get("day_of_week"))
            period = ts.get("period_number")
            if not day_label or not period:
                continue

            key = f"{day_label} P{period}"
            section = row.get("sections") or {}
            teacher = row.get("teachers") or {}
            room = row.get("rooms") or {}

            grid.setdefault(key, []).append({
                "section": f"Grade {section.get('grade')}-{section.get('section_label')}",
                "subject": row["subject"],
                "teacher": teacher.get("name", "Unassigned"),
                "room": room.get("name", "TBD"),
                "is_substitute": row.get("is_substitute", False),
            })

        return grid