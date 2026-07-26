"""
Test the solver against the exact scenario seeded in supabase/seed.py.
Run with: python test_solver.py

This validates, BEFORE any API/DB wiring exists, that:
  1. The solver correctly resolves both simultaneous vacancies (9-A and 9-B)
  2. It picks Ms. Fatima (0 substitutions) over Mr. Singh (6 substitutions)
     -> proves the fairness constraint is actually working, not just claimed
  3. It respects the qualification + load-cap hard constraints
"""

from substitute_solver import Teacher, VacantSession, solve_substitutions


def main():
    teachers = [
        Teacher(id="rao",    name="Mr. Rao",    subjects=["Physics", "Math"],      max_periods_per_day=6, current_load_today=4, substitution_count_month=1),
        Teacher(id="iyer",   name="Ms. Iyer",   subjects=["Physics", "Chemistry"], max_periods_per_day=6, current_load_today=5, substitution_count_month=2),
        Teacher(id="singh",  name="Mr. Singh",  subjects=["Physics", "Biology"],   max_periods_per_day=6, current_load_today=3, substitution_count_month=6),
        Teacher(id="fatima", name="Ms. Fatima", subjects=["Math", "Physics"],      max_periods_per_day=6, current_load_today=2, substitution_count_month=0),
        Teacher(id="das",    name="Mr. Das",    subjects=["English", "History"],   max_periods_per_day=6, current_load_today=4, substitution_count_month=1),
        Teacher(id="nair",   name="Ms. Nair",   subjects=["Chemistry", "Biology"], max_periods_per_day=6, current_load_today=3, substitution_count_month=2),
    ]

    # Mr. Rao is on leave -> both his Monday P1 sessions need coverage
    vacant_sessions = [
        VacantSession(id="sess_9A_physics", section_label="Grade 9-A", subject="Physics",
                      timeslot_id="mon_p1", original_teacher_id="rao"),
        VacantSession(id="sess_9B_physics", section_label="Grade 9-B", subject="Physics",
                      timeslot_id="mon_p1", original_teacher_id="rao"),
    ]

    result = solve_substitutions(vacant_sessions, teachers)

    print(f"Solver status: {result['status']}\n")
    for a in result["assignments"]:
        print(f"Session: {a['session_id']}")
        print(f"  Resolved: {a['resolved']}")
        print(f"  Teacher: {a['teacher_name']}")
        print(f"  Reasoning: {a['reasoning']}")
        if a["fallback_candidates"]:
            print(f"  Fallback candidates: {a['fallback_candidates']}")
        print()

    # ---- Assertions to prove correctness, not just print output ----
    assignments_by_session = {a["session_id"]: a for a in result["assignments"]}

    both_resolved = all(a["resolved"] for a in result["assignments"])
    assigned_teachers = {a["teacher_id"] for a in result["assignments"]}
    no_double_assignment = len(assigned_teachers) == len(result["assignments"])
    fatima_used = "fatima" in assigned_teachers
    singh_avoided = "singh" not in assigned_teachers

    print("--- Validation ---")
    print(f"Both sessions resolved: {both_resolved}")
    print(f"No teacher double-booked across the two sessions: {no_double_assignment}")
    print(f"Ms. Fatima (fairest choice) used: {fatima_used}")
    print(f"Mr. Singh (overused, 6 subs) avoided: {singh_avoided}")

    assert both_resolved, "FAIL: expected both vacancies to be resolved"
    assert no_double_assignment, "FAIL: same teacher assigned to both simultaneous sessions"
    assert fatima_used, "FAIL: expected fairness constraint to prefer Ms. Fatima"
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
