// ReviewQueue.tsx
// Surfaces the extracted form with per-field confidence. When status is
// "needs_review", renders an editable correction form pre-filled with
// whatever was extracted — the admin fixes the flagged/blank fields and
// submits, which re-runs the solver via POST /forms/{id}/review.

import { useState, useEffect } from 'react';
import { useDashboardStore } from './store';

const FIELD_LABELS: Record<string, string> = {
  teacher_name: 'Teacher',
  date: 'Date',
  reason: 'Reason',
  submitted_by: 'Submitted by',
  sections_affected: 'Sections affected',
};

function CorrectionForm() {
  const form = useDashboardStore((s) => s.formSubmission);
  const submitCorrection = useDashboardStore((s) => s.submitCorrection);
  const demoStage = useDashboardStore((s) => s.demoStage);

  const [values, setValues] = useState<Record<string, string>>({});

  // Pre-fill from whatever was extracted, every time a new form arrives
  useEffect(() => {
    if (!form) return;
    const initial: Record<string, string> = {};
    for (const key of Object.keys(FIELD_LABELS)) {
      initial[key] = form.extracted_fields[key]?.value ?? '';
    }
    setValues(initial);
  }, [form]);

  if (!form) return null;
  const isBusy = demoStage === 'uploading';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!values.teacher_name || !values.date) return;
    submitCorrection({
      teacher_name: values.teacher_name,
      date: values.date,
      reason: values.reason || undefined,
      submitted_by: values.submitted_by || undefined,
      sections_affected: values.sections_affected || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="mt-4 pt-4 border-t border-ink/10">
      <p className="font-mono text-xs uppercase tracking-widest text-rust font-bold mb-3">
        Correct the fields below to resolve
      </p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {Object.entries(FIELD_LABELS).map(([key, label]) => (
          <div key={key}>
            <label className="font-mono text-xs uppercase tracking-wide text-ink/50 block mb-1">
              {label}
              {(key === 'teacher_name' || key === 'date') && (
                <span className="text-rust"> *</span>
              )}
            </label>
            <input
              type="text"
              value={values[key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
              placeholder={key === 'date' ? 'YYYY-MM-DD' : ''}
              className="w-full bg-paper-dark border border-ink/20 rounded-sm px-2 py-1 font-mono text-sm text-ink focus:outline-none focus:border-brass"
            />
          </div>
        ))}
      </div>
      <button
        type="submit"
        disabled={isBusy || !values.teacher_name || !values.date}
        className="mt-4 font-mono text-xs uppercase tracking-wide bg-brass text-ink font-bold px-4 py-2 rounded-sm hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {isBusy ? 'Resolving…' : 'Submit correction'}
      </button>
      <p className="font-mono text-[11px] text-ink/40 mt-2">* required to resolve</p>
    </form>
  );
}

export function ReviewQueue() {
  const form = useDashboardStore((s) => s.formSubmission);

  if (!form) {
    return (
      <div className="bg-ink-light rounded-sm p-6 text-center">
        <p className="font-mono text-sm text-paper/40 italic">
          No form submissions yet. Upload a scanned form to begin.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-paper paper-texture text-ink rounded-sm shadow-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-ink/50">
            Scanned form · {form.form_type.replace('_', ' ')}
          </p>
          <h3 className="font-display text-xl font-semibold mt-1">Extraction result</h3>
        </div>
        <span
          className={`font-mono text-xs uppercase font-bold px-2 py-1 rounded-sm ${
            form.status === 'auto_applied' || form.status === 'applied'
              ? 'bg-sage text-paper'
              : 'bg-rust text-paper'
          }`}
        >
          {form.status.replace('_', ' ')}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        {Object.entries(form.extracted_fields).map(([key, field]) => {
          const flagged = field.confidence < 0.75 || field.value === null;
          return (
            <div key={key}>
              <p className="font-mono text-xs uppercase tracking-wide text-ink/50">
                {FIELD_LABELS[key] ?? key}
              </p>
              <p
                className={`font-mono text-sm mt-0.5 ${
                  flagged ? 'text-rust font-semibold' : 'text-ink'
                }`}
              >
                {field.value ?? '— illegible —'}
                <span className="text-ink/40 ml-2 text-xs">
                  {(field.confidence * 100).toFixed(0)}%
                </span>
              </p>
            </div>
          );
        })}
      </div>

      <p className="font-mono text-xs text-ink/50 mt-4 pt-4 border-t border-ink/10">
        Overall confidence: {(form.overall_confidence * 100).toFixed(0)}%
      </p>

      {form.status === 'needs_review' && <CorrectionForm />}
    </div>
  );
}