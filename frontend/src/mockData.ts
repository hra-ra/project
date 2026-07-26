// mockData.ts
// Shape-matches the real Supabase schema exactly, so this is a drop-in
// swap for real queries later — components should never need to change
// when we wire up the live backend.

export type AlertSeverity = 'info' | 'watch' | 'critical';

export interface Alert {
  id: string;
  alert_type: 'bottleneck' | 'conflict' | 'anomaly' | 'info';
  severity: AlertSeverity;
  message: string;
  related_entity_type: string;
  resolved: boolean;
  created_at: string;
}

export interface FormSubmission {
  id: string;
  form_type: string;
  extracted_fields: Record<string, { value: string | null; confidence: number }>;
  overall_confidence: number;
  status: 'pending' | 'auto_applied' | 'needs_review' | 'rejected' | 'applied';
  created_at: string;
}

export interface DiffEntry {
  session_label: string;      // e.g. "Grade 9-A · Physics · Mon P1"
  field: string;              // e.g. "teacher"
  old_value: string;
  new_value: string;
  reasoning: string;
}

export interface TimetableVersion {
  id: string;
  triggered_by_reason: string;
  diff: DiffEntry[];
  solver_status: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE';
  created_at: string;
}

export interface TimetableCell {
  section: string;
  subject: string;
  teacher: string;
  room: string;
  is_substitute: boolean;
}

export const mockAlerts: Alert[] = [
  {
    id: 'a1',
    alert_type: 'bottleneck',
    severity: 'watch',
    message: 'Room 204 is booked for Grade 9-B (38 students) but has a capacity of 30.',
    related_entity_type: 'room',
    resolved: false,
    created_at: '2026-07-27T07:45:00Z',
  },
  {
    id: 'a2',
    alert_type: 'anomaly',
    severity: 'info',
    message: 'Mr. Singh has covered 6 substitute periods this month — highest of any teacher.',
    related_entity_type: 'teacher',
    resolved: false,
    created_at: '2026-07-27T07:40:00Z',
  },
];

export const mockFormSubmission: FormSubmission = {
  id: 'f1',
  form_type: 'leave_application',
  extracted_fields: {
    teacher_name: { value: 'Mr. Rao', confidence: 0.96 },
    date: { value: '2026-07-28', confidence: 0.94 },
    reason: { value: 'Medical leave', confidence: 0.91 },
    submitted_by: { value: 'Front Office', confidence: 0.98 },
    sections_affected: { value: 'Grade 9-A, 9-B', confidence: 0.89 },
  },
  overall_confidence: 0.94,
  status: 'auto_applied',
  created_at: '2026-07-27T08:02:00Z',
};

export const mockTimetableVersion: TimetableVersion = {
  id: 'v1',
  triggered_by_reason: "Mr. Rao — leave application, Mon 28 Jul",
  solver_status: 'OPTIMAL',
  created_at: '2026-07-27T08:02:14Z',
  diff: [
    {
      session_label: 'Grade 9-A · Physics · Mon P1',
      field: 'teacher',
      old_value: 'Mr. Rao',
      new_value: 'Ms. Fatima',
      reasoning: 'Physics-qualified, lowest substitution load this month (0), lightest current workload (2 periods today).',
    },
    {
      session_label: 'Grade 9-B · Physics · Mon P1',
      field: 'teacher',
      old_value: 'Mr. Rao',
      new_value: 'Ms. Iyer',
      reasoning: 'Physics-qualified, only qualified teacher remaining at this timeslot (Ms. Fatima already assigned to 9-A).',
    },
  ],
};

export const mockTimetableGrid: Record<string, TimetableCell[]> = {
  'Mon P1': [
    { section: 'Grade 9-A', subject: 'Physics', teacher: 'Ms. Fatima', room: 'Lab 2', is_substitute: true },
    { section: 'Grade 9-B', subject: 'Physics', teacher: 'Ms. Iyer', room: 'Room 204', is_substitute: true },
    { section: 'Grade 10-A', subject: 'History', teacher: 'Mr. Das', room: 'Room 101', is_substitute: false },
  ],
  'Mon P2': [
    { section: 'Grade 9-A', subject: 'Math', teacher: 'Mr. Rao', room: 'Room 101', is_substitute: false },
    { section: 'Grade 9-B', subject: 'Chemistry', teacher: 'Ms. Nair', room: 'Lab 2', is_substitute: false },
    { section: 'Grade 10-A', subject: 'English', teacher: 'Mr. Das', room: 'Room 101', is_substitute: false },
  ],
};
