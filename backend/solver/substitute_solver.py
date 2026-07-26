"""
substitute_solver.py

Core constraint-solving logic for resolving teacher vacancies
(e.g. from a leave-application form) against the live timetable.

Design goals:
  - Pure function: takes plain dicts/lists in, returns plain dicts out.
    No DB or API dependency here — makes it trivially unit-testable
    and reusable from a script, a test, or the FastAPI layer.
  - Hard constraints are enforced by construction (only feasible
    variables are created) — the solver can never violate them.
  - Soft constraints (fairness, workload) are encoded in the objective,
    so the solver always returns the *best available* answer rather
    than failing outright.
  - Graceful degradation: if a session truly cannot be covered, it
    is reported as UNRESOLVED with the top-3 least-bad candidates
    (even if they violate a hard constraint) so an admin has options
    instead of a dead end.
"""

from dataclasses import dataclass, field
from ortools.sat.python import cp_model


@dataclass
class Teacher:
    id: str
    name: str
    subjects: list          # e.g. ["Physics", "Math"]
    max_periods_per_day: int
    current_load_today: int
    substitution_count_month: int
    is_available: bool = True


@dataclass
class VacantSession:
    id: str                 # class_session id
    section_label: str      # e.g. "Grade 9-B"
    subject: str
    timeslot_id: str         # sessions sharing a timeslot_id can't share a teacher
    original_teacher_id: str


# ------------------------------------------------------------
# Cost weights — tuned so that:
#   - leaving a session unresolved is always worse than any valid
#     assignment (UNRESOLVED_PENALTY dominates)
#   - fairness (avoiding overused substitutes) matters more than
#     raw workload balance, but both are secondary to feasibility
# ------------------------------------------------------------
UNRESOLVED_PENALTY = 10_000
FAIRNESS_WEIGHT = 20      # per substitution_count_month point
WORKLOAD_WEIGHT = 5       # per current_load_today point
BASE_ASSIGNMENT_COST = 1  # tiny tiebreaker so solver prefers fewer total assignments changes


def solve_substitutions(vacant_sessions: list[VacantSession], teachers: list[Teacher]):
    """
    Returns:
        {
          "status": "OPTIMAL" | "FEASIBLE" | "NO_SOLUTION",
          "assignments": [
              {
                "session_id": ...,
                "teacher_id": ... | None,
                "teacher_name": ... | None,
                "reasoning": "...",
                "resolved": True/False,
                "fallback_candidates": [...]   # only if unresolved
              },
              ...
          ]
        }
    """
    model = cp_model.CpModel()

    # x[(session_id, teacher_id)] = 1 if teacher covers that session
    x = {}
    candidate_map = {s.id: [] for s in vacant_sessions}

    for s in vacant_sessions:
        for t in teachers:
            if not t.is_available:
                continue
            if s.subject not in t.subjects:
                continue  # hard constraint: subject qualification
            if t.id == s.original_teacher_id:
                continue  # can't substitute for yourself
            var = model.NewBoolVar(f"x_{s.id}_{t.id}")
            x[(s.id, t.id)] = var
            candidate_map[s.id].append(t)

    # Hard constraint: each session covered by at most 1 teacher
    for s in vacant_sessions:
        vars_for_session = [x[(s.id, t.id)] for t in candidate_map[s.id]]
        if vars_for_session:
            model.Add(sum(vars_for_session) <= 1)

    # Hard constraint: a teacher can't cover two sessions in the same timeslot
    timeslot_groups = {}
    for s in vacant_sessions:
        timeslot_groups.setdefault(s.timeslot_id, []).append(s)

    for _, sessions_in_slot in timeslot_groups.items():
        teacher_ids_involved = {t.id for s in sessions_in_slot for t in candidate_map[s.id]}
        for tid in teacher_ids_involved:
            vars_same_slot = [
                x[(s.id, tid)] for s in sessions_in_slot if (s.id, tid) in x
            ]
            if len(vars_same_slot) > 1:
                model.Add(sum(vars_same_slot) <= 1)

    # Hard constraint: teacher's daily load cap
    teacher_assignment_vars = {t.id: [] for t in teachers}
    for (sid, tid), var in x.items():
        teacher_assignment_vars[tid].append(var)

    for t in teachers:
        remaining_capacity = t.max_periods_per_day - t.current_load_today
        vars_for_teacher = teacher_assignment_vars[t.id]
        if vars_for_teacher:
            model.Add(sum(vars_for_teacher) <= max(remaining_capacity, 0))

    # ------------------------------------------------------------
    # Objective: minimize total cost
    #   - heavily penalize unresolved sessions
    #   - among valid assignments, prefer fair + lightly-loaded teachers
    # ------------------------------------------------------------
    unresolved_vars = []
    cost_terms = []

    for s in vacant_sessions:
        vars_for_session = [x[(s.id, t.id)] for t in candidate_map[s.id]]
        unresolved = model.NewBoolVar(f"unresolved_{s.id}")
        if vars_for_session:
            model.Add(sum(vars_for_session) + unresolved == 1)
        else:
            model.Add(unresolved == 1)
        unresolved_vars.append((s.id, unresolved))
        cost_terms.append(unresolved * UNRESOLVED_PENALTY)

        for t in candidate_map[s.id]:
            var = x[(s.id, t.id)]
            cost = (
                BASE_ASSIGNMENT_COST
                + t.substitution_count_month * FAIRNESS_WEIGHT
                + t.current_load_today * WORKLOAD_WEIGHT
            )
            cost_terms.append(var * cost)

    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    results = {"status": status_name, "assignments": []}

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Totally infeasible model shell (shouldn't happen given unresolved
        # vars always make it feasible, but guard anyway)
        for s in vacant_sessions:
            results["assignments"].append(_unresolved_result(s, teachers))
        return results

    for s in vacant_sessions:
        assigned_teacher = None
        for t in candidate_map[s.id]:
            if solver.Value(x[(s.id, t.id)]) == 1:
                assigned_teacher = t
                break

        if assigned_teacher:
            reasoning = _build_reasoning(s, assigned_teacher, candidate_map[s.id])
            results["assignments"].append({
                "session_id": s.id,
                "teacher_id": assigned_teacher.id,
                "teacher_name": assigned_teacher.name,
                "reasoning": reasoning,
                "resolved": True,
                "fallback_candidates": [],
            })
        else:
            results["assignments"].append(_unresolved_result(s, teachers))

    return results


def _build_reasoning(session: VacantSession, chosen: Teacher, all_candidates: list[Teacher]) -> str:
    reasons = [f"{session.subject}-qualified"]
    others = [t for t in all_candidates if t.id != chosen.id]

    if others and chosen.substitution_count_month == min(t.substitution_count_month for t in all_candidates):
        reasons.append(f"lowest substitution load this month ({chosen.substitution_count_month})")
    if others and chosen.current_load_today == min(t.current_load_today for t in all_candidates):
        reasons.append(f"lightest current workload ({chosen.current_load_today} periods today)")

    if len(reasons) == 1:
        reasons.append("only qualified teacher available at this timeslot")

    return f"Assigned {chosen.name}: " + ", ".join(reasons) + "."


def _unresolved_result(session: VacantSession, all_teachers: list[Teacher]) -> dict:
    """
    Graceful degradation: even if no valid assignment exists, surface the
    top-3 least-bad options (ignoring hard constraints like load cap) so
    an admin has somewhere to start instead of a dead end.
    """
    subject_qualified = [t for t in all_teachers if session.subject in t.subjects
                          and t.id != session.original_teacher_id]
    ranked = sorted(subject_qualified, key=lambda t: (t.substitution_count_month, t.current_load_today))
    fallback = [
        {
            "teacher_id": t.id,
            "teacher_name": t.name,
            "caveat": "would exceed daily load cap" if t.current_load_today >= t.max_periods_per_day else "may conflict with another slot",
        }
        for t in ranked[:3]
    ]
    return {
        "session_id": session.id,
        "teacher_id": None,
        "teacher_name": None,
        "reasoning": "No fully qualified, available substitute found without violating constraints.",
        "resolved": False,
        "fallback_candidates": fallback,
    }
