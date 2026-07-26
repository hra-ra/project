// api.ts
// Thin client for the FastAPI backend. Kept separate from the store so
// the fetch/error-handling concerns don't leak into component logic.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export interface ApiDiffEntry {
  session_id: string;
  session_label: string;
  field: string;
  old_value: string;
  new_value: string | null;
  reasoning: string;
  resolved: boolean;
  fallback_candidates?: { teacher_name: string; caveat: string }[];
}

export interface ApiFormResult {
  form_id: string;
  status: 'applied' | 'needs_review';
  solver_status?: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE';
  reason: string;
  diff: ApiDiffEntry[] | null;
  extracted_fields: Record<string, { value: string | null; confidence: number }>;
  overall_confidence: number;
  flagged_fields?: string[];
}

export class ApiError extends Error {}

export interface ApiTimetableCell {
  section: string;
  subject: string;
  teacher: string;
  room: string;
  is_substitute: boolean;
}

export type ApiTimetableGrid = Record<string, ApiTimetableCell[]>;

export async function fetchTimetable(): Promise<ApiTimetableGrid> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/timetable`);
  } catch (err) {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE}. Is it running? (${(err as Error).message})`
    );
  }
  if (!response.ok) {
    throw new ApiError(`Failed to fetch timetable: ${response.status}`);
  }
  return response.json();
}

export interface ReviewCorrectionPayload {
  teacher_name: string;
  date: string;
  reason?: string;
  submitted_by?: string;
  sections_affected?: string;
}

export async function submitReviewCorrection(
  formId: string,
  correction: ReviewCorrectionPayload
): Promise<ApiFormResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/forms/${formId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(correction),
    });
  } catch (err) {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE}. Is it running? (${(err as Error).message})`
    );
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new ApiError(`Backend returned ${response.status}: ${text || response.statusText}`);
  }
  return response.json();
}

export async function uploadLeaveForm(file: File): Promise<ApiFormResult> {
  const formData = new FormData();
  formData.append('file', file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/forms/upload`, {
      method: 'POST',
      body: formData,
    });
  } catch (err) {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE}. Is it running? (${(err as Error).message})`
    );
  }

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new ApiError(`Backend returned ${response.status}: ${text || response.statusText}`);
  }

  return response.json();
}