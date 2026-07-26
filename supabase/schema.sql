-- ============================================================
-- School ERP — Core Schema
-- Target: Supabase (Postgres 15+)
-- ============================================================

-- Extensions
create extension if not exists "uuid-ossp";

-- ------------------------------------------------------------
-- TEACHERS
-- ------------------------------------------------------------
create table teachers (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  subjects text[] not null default '{}',        -- e.g. ['Physics','Math']
  max_periods_per_day int not null default 6,
  current_load_today int not null default 0,     -- periods assigned today
  substitution_count_month int not null default 0, -- fairness tracker
  is_available boolean not null default true,     -- toggled off when on leave
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- ROOMS
-- ------------------------------------------------------------
create table rooms (
  id uuid primary key default uuid_generate_v4(),
  name text not null,                -- e.g. 'Room 204', 'Lab 2'
  capacity int not null default 40,
  room_type text not null default 'classroom', -- classroom / lab / hall
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- SECTIONS (a grade-section group, e.g. "Grade 9 - B")
-- ------------------------------------------------------------
create table sections (
  id uuid primary key default uuid_generate_v4(),
  grade int not null,
  section_label text not null,       -- 'A', 'B', 'C'
  student_count int not null default 30,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- TIMESLOTS (fixed periods in a school day)
-- ------------------------------------------------------------
create table timeslots (
  id uuid primary key default uuid_generate_v4(),
  day_of_week int not null,          -- 1=Mon ... 5=Fri
  period_number int not null,        -- 1..8
  start_time time not null,
  end_time time not null
);

-- ------------------------------------------------------------
-- CLASS_SESSIONS — the atomic schedulable unit
-- This is what the solver reads/writes.
-- ------------------------------------------------------------
create table class_sessions (
  id uuid primary key default uuid_generate_v4(),
  section_id uuid not null references sections(id),
  subject text not null,
  teacher_id uuid references teachers(id),   -- nullable: unassigned slot
  room_id uuid references rooms(id),
  timeslot_id uuid not null references timeslots(id),
  is_substitute boolean not null default false, -- true if teacher != original
  original_teacher_id uuid references teachers(id), -- who it was before a sub
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Prevent the two hard constraints at the DB level as a safety net
-- (solver should never violate these, but DB enforces it regardless)
create unique index uq_teacher_slot on class_sessions (teacher_id, timeslot_id)
  where teacher_id is not null;
create unique index uq_room_slot on class_sessions (room_id, timeslot_id)
  where room_id is not null;
create unique index uq_section_slot on class_sessions (section_id, timeslot_id);

-- ------------------------------------------------------------
-- FORM_SUBMISSIONS — raw scanned forms + AI extraction results
-- ------------------------------------------------------------
create table form_submissions (
  id uuid primary key default uuid_generate_v4(),
  form_type text not null default 'leave_application',
  raw_image_url text,
  extracted_json jsonb not null default '{}',    -- { teacher_name: {value, confidence}, date: {...}, reason: {...} }
  overall_confidence numeric(4,3),               -- 0.000 - 1.000
  status text not null default 'pending',        -- pending | auto_applied | needs_review | rejected | applied
  reviewed_by text,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- TIMETABLE_VERSIONS — every solve produces a new version + diff
-- ------------------------------------------------------------
create table timetable_versions (
  id uuid primary key default uuid_generate_v4(),
  triggered_by_form_id uuid references form_submissions(id),
  triggered_by_reason text,                      -- human-readable trigger summary
  diff_json jsonb not null default '[]',          -- array of {session_id, field, old_value, new_value}
  solver_status text,                             -- OPTIMAL | FEASIBLE | INFEASIBLE
  soft_constraints_violated jsonb default '[]',   -- list of relaxed constraints, if any
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- SUBSTITUTION_LOG — explainability trail for the agent's decisions
-- ------------------------------------------------------------
create table substitution_log (
  id uuid primary key default uuid_generate_v4(),
  class_session_id uuid references class_sessions(id),
  original_teacher_id uuid references teachers(id),
  substitute_teacher_id uuid references teachers(id),
  reasoning_text text,                 -- e.g. "Subject match + lowest monthly sub count"
  timetable_version_id uuid references timetable_versions(id),
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- ALERTS — proactive dashboard alerts
-- ------------------------------------------------------------
create table alerts (
  id uuid primary key default uuid_generate_v4(),
  alert_type text not null,            -- bottleneck | conflict | anomaly | info
  severity text not null default 'info', -- info | watch | critical
  message text not null,
  related_entity_type text,            -- 'teacher' | 'room' | 'section' | 'form_submission'
  related_entity_id uuid,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Realtime: enable replication for tables the dashboard subscribes to
-- ------------------------------------------------------------
alter publication supabase_realtime add table class_sessions;
alter publication supabase_realtime add table alerts;
alter publication supabase_realtime add table form_submissions;
alter publication supabase_realtime add table timetable_versions;
