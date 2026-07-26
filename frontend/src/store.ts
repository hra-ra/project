// store.ts
// Central reactive store. The design intent here: when a form is
// uploaded and the backend resolves it, EVERY subscribed component
// (alert feed, ledger diff, timetable grid) updates from a single
// state change — proving the "perfectly synced UI" requirement rather
// than each panel independently re-fetching or going stale relative
// to the others.
//
// The timetable grid is always fetched fresh from GET /timetable —
// the backend's Postgres data is the single source of truth. We don't
// try to infer grid changes client-side from a diff; after any action
// that might change the schedule, we just re-fetch.

import { create } from 'zustand';
import { mockAlerts, type Alert, type FormSubmission, type TimetableVersion, type TimetableCell } from './mockData';
import {
  uploadLeaveForm,
  fetchTimetable,
  submitReviewCorrection,
  ApiError,
  type ApiFormResult,
  type ReviewCorrectionPayload,
} from './api';

type DemoStage = 'idle' | 'uploading' | 'resolved' | 'needs_review' | 'error';

interface DashboardState {
  alerts: Alert[];
  formSubmission: FormSubmission | null;
  timetableVersion: TimetableVersion | null;
  timetableGrid: Record<string, TimetableCell[]>;
  demoStage: DemoStage;
  errorMessage: string | null;

  resolveAlert: (id: string) => void;
  uploadForm: (file: File) => Promise<void>;
  loadTimetable: () => Promise<void>;
  submitCorrection: (correction: ReviewCorrectionPayload) => Promise<void>;
}

function buildResolvedAlert(result: ApiFormResult): Alert {
  const resolvedCount = result.diff?.filter((d) => d.resolved).length ?? 0;
  const unresolvedCount = result.diff?.filter((d) => !d.resolved).length ?? 0;

  if (result.status === 'needs_review') {
    return {
      id: `alert_${result.form_id}`,
      alert_type: 'conflict',
      severity: unresolvedCount > 0 ? 'critical' : 'watch',
      message: unresolvedCount > 0
        ? `${result.reason} — ${unresolvedCount} session(s) could not be auto-resolved. Manual review needed.`
        : result.reason,
      related_entity_type: 'form_submission',
      resolved: false,
      created_at: new Date().toISOString(),
    };
  }

  return {
    id: `alert_${result.form_id}`,
    alert_type: 'conflict',
    severity: 'info',
    message: `Resolved: ${result.reason} — ${resolvedCount} session(s) reassigned automatically.`,
    related_entity_type: 'form_submission',
    resolved: true,
    created_at: new Date().toISOString(),
  };
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  alerts: mockAlerts,
  formSubmission: null,
  timetableVersion: null,
  timetableGrid: {},
  demoStage: 'idle',
  errorMessage: null,

  resolveAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, resolved: true } : a)),
    })),

  loadTimetable: async () => {
    try {
      const grid = await fetchTimetable();
      set({ timetableGrid: grid });
    } catch (err) {
      console.error('Failed to load timetable:', err);
    }
  },

  uploadForm: async (file: File) => {
    set({ demoStage: 'uploading', errorMessage: null });

    let result: ApiFormResult;
    try {
      result = await uploadLeaveForm(file);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unexpected error contacting the backend.';
      set({ demoStage: 'error', errorMessage: message });
      return;
    }

    applyResult(result, set, get);
    await get().loadTimetable();
  },

  submitCorrection: async (correction) => {
    const currentFormId = get().formSubmission?.id;
    if (!currentFormId) {
      set({ errorMessage: 'No form to correct — upload one first.' });
      return;
    }

    set({ demoStage: 'uploading', errorMessage: null });

    let result: ApiFormResult;
    try {
      result = await submitReviewCorrection(currentFormId, correction);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Unexpected error contacting the backend.';
      set({ demoStage: 'error', errorMessage: message });
      return;
    }

    applyResult(result, set, get);
    await get().loadTimetable();
  },
}));

// Shared logic for turning a backend response into store state — used by
// both the initial upload and a human's follow-up correction, so the
// dashboard reacts identically regardless of which path produced the result.
function applyResult(
  result: ApiFormResult,
  set: (partial: Partial<DashboardState>) => void,
  get: () => DashboardState
) {
  const formSubmission: FormSubmission = {
    id: result.form_id,
    form_type: 'leave_application',
    extracted_fields: result.extracted_fields,
    overall_confidence: result.overall_confidence,
    status: result.status,
    created_at: new Date().toISOString(),
  };

  const timetableVersion: TimetableVersion | null =
    result.diff && result.diff.length > 0
      ? {
          id: result.form_id,
          triggered_by_reason: result.reason,
          solver_status: result.solver_status ?? 'FEASIBLE',
          created_at: new Date().toISOString(),
          diff: result.diff.map((d) => ({
            session_label: d.session_label,
            field: d.field,
            old_value: d.old_value,
            new_value: d.new_value ?? '— unresolved —',
            reasoning: d.reasoning,
          })),
        }
      : null;

  set({
    demoStage: result.status === 'applied' ? 'resolved' : 'needs_review',
    formSubmission,
    timetableVersion,
    alerts: [buildResolvedAlert(result), ...get().alerts],
  });
}