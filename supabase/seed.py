"""
Seed script — populates realistic demo data with deliberate stress points
so the CP-SAT solver has genuine conflicts to resolve during the live demo.

Run with: python seed.py
Requires: pip install supabase python-dotenv --break-system-packages
Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
from datetime import time
from dotenv import load_dotenv, find_dotenv
from supabase import create_client

load_dotenv(find_dotenv(usecwd=True))
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
sb = create_client(url, key)

# ------------------------------------------------------------
# 1. TEACHERS — deliberately includes stress points:
#    - Mr. Rao: Physics specialist, will be the one who "calls in sick" in the demo
#    - Ms. Iyer: also teaches Physics, but already near max_periods_per_day
#      -> solver must weigh "qualified but loaded" vs "less qualified but free"
#    - Mr. Singh: highest substitution_count_month -> fairness constraint
#      should actively AVOID picking him again even though he's free
# ------------------------------------------------------------
teachers = [
    {"name": "Mr. Rao",    "subjects": ["Physics", "Math"],       "max_periods_per_day": 6, "current_load_today": 4, "substitution_count_month": 1},
    {"name": "Ms. Iyer",   "subjects": ["Physics", "Chemistry"],  "max_periods_per_day": 6, "current_load_today": 5, "substitution_count_month": 2},
    {"name": "Mr. Singh",  "subjects": ["Physics", "Biology"],    "max_periods_per_day": 6, "current_load_today": 3, "substitution_count_month": 6},  # overused
    {"name": "Ms. Fatima", "subjects": ["Math", "Physics"],       "max_periods_per_day": 6, "current_load_today": 2, "substitution_count_month": 0},  # ideal candidate
    {"name": "Mr. Das",    "subjects": ["English", "History"],    "max_periods_per_day": 6, "current_load_today": 4, "substitution_count_month": 1},
    {"name": "Ms. Nair",   "subjects": ["Chemistry", "Biology"],  "max_periods_per_day": 6, "current_load_today": 3, "substitution_count_month": 2},
]

rooms = [
    {"name": "Room 101", "capacity": 40, "room_type": "classroom"},
    {"name": "Room 204", "capacity": 30, "room_type": "classroom"},  # deliberately smaller
    {"name": "Lab 2",    "capacity": 35, "room_type": "lab"},
    {"name": "Hall A",   "capacity": 100, "room_type": "hall"},
]

sections = [
    {"grade": 9,  "section_label": "A", "student_count": 32},
    {"grade": 9,  "section_label": "B", "student_count": 38},  # near Room 204's capacity -> triggers bottleneck alert
    {"grade": 10, "section_label": "A", "student_count": 28},
]

# Periods 1-6, Monday-Friday
timeslots = []
period_times = [
    (time(8, 0), time(8, 45)),
    (time(8, 45), time(9, 30)),
    (time(9, 45), time(10, 30)),
    (time(10, 30), time(11, 15)),
    (time(11, 30), time(12, 15)),
    (time(12, 15), time(13, 0)),
]
for day in range(1, 6):
    for i, (start, end) in enumerate(period_times, start=1):
        timeslots.append({
            "day_of_week": day,
            "period_number": i,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        })


def seed():
    print("Seeding teachers...")
    teacher_rows = sb.table("teachers").insert(teachers).execute().data
    teacher_by_name = {t["name"]: t["id"] for t in teacher_rows}

    print("Seeding rooms...")
    room_rows = sb.table("rooms").insert(rooms).execute().data
    room_by_name = {r["name"]: r["id"] for r in room_rows}

    print("Seeding sections...")
    section_rows = sb.table("sections").insert(sections).execute().data

    print("Seeding timeslots...")
    timeslot_rows = sb.table("timeslots").insert(timeslots).execute().data

    # ------------------------------------------------------------
    # Class sessions: Monday. Mr. Rao teaches Grade 9-A Physics at
    # Period 1 and Grade 9-B Physics at Period 2 — two DIFFERENT
    # timeslots (a teacher can't be in two rooms at the same time,
    # so same-slot double-booking isn't realistic and is blocked by
    # the uq_teacher_slot constraint). When his leave form is
    # processed, BOTH sessions still need coverage on the same day,
    # giving the solver two vacancies to resolve in one solve.
    # ------------------------------------------------------------
    monday_p1 = next(t for t in timeslot_rows if t["day_of_week"] == 1 and t["period_number"] == 1)
    monday_p2 = next(t for t in timeslot_rows if t["day_of_week"] == 1 and t["period_number"] == 2)

    grade9a = next(s for s in section_rows if s["grade"] == 9 and s["section_label"] == "A")
    grade9b = next(s for s in section_rows if s["grade"] == 9 and s["section_label"] == "B")

    class_sessions = [
        {
            "section_id": grade9a["id"],
            "subject": "Physics",
            "teacher_id": teacher_by_name["Mr. Rao"],
            "room_id": room_by_name["Lab 2"],
            "timeslot_id": monday_p1["id"],
        },
        {
            "section_id": grade9b["id"],
            "subject": "Physics",
            "teacher_id": teacher_by_name["Mr. Rao"],
            "room_id": room_by_name["Room 204"],  # capacity 30, but section has 38
            "timeslot_id": monday_p2["id"],
        },
    ]
    print("Seeding class_sessions (Rao teaches both sessions on Monday, different periods)...")
    sb.table("class_sessions").insert(class_sessions).execute()

    # A standing bottleneck alert, so the dashboard has proactive
    # content to show BEFORE any form is even uploaded.
    print("Seeding baseline alert (capacity bottleneck)...")
    sb.table("alerts").insert({
        "alert_type": "bottleneck",
        "severity": "watch",
        "message": "Room 204 is booked for Grade 9-B (38 students) but has a capacity of 30.",
        "related_entity_type": "room",
        "related_entity_id": room_by_name["Room 204"],
    }).execute()

    print("Done. Ready to demo: upload a leave form for 'Mr. Rao' dated this Monday.")


if __name__ == "__main__":
    seed()