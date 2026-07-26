import { useRef, useEffect } from 'react';
import { useDashboardStore } from './store';
import { AlertFeed } from './AlertFeed';
import { TimetableGrid } from './TimetableGrid';
import { ReviewQueue } from './ReviewQueue';
import { LedgerDiff } from './LedgerDiff';

function UploadControl() {
  const demoStage = useDashboardStore((s) => s.demoStage);
  const errorMessage = useDashboardStore((s) => s.errorMessage);
  const uploadForm = useDashboardStore((s) => s.uploadForm);
  const inputRef = useRef<HTMLInputElement>(null);

  const isBusy = demoStage === 'uploading';

  const label = isBusy
    ? 'Extracting & resolving…'
    : demoStage === 'resolved'
      ? 'Resolved — upload another form'
      : demoStage === 'needs_review'
        ? 'Needs review — upload another form'
        : demoStage === 'error'
          ? 'Failed — try again'
          : 'Upload leave form';

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadForm(file);
    e.target.value = '';
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
        className="hidden"
      />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={isBusy}
        className="font-mono text-sm uppercase tracking-wide bg-brass text-ink font-bold px-4 py-2 rounded-sm hover:brightness-110 disabled:opacity-60 disabled:cursor-wait transition-all"
      >
        {label}
      </button>
      {errorMessage && (
        <p className="font-mono text-xs text-rust-light max-w-xs text-right">{errorMessage}</p>
      )}
    </div>
  );
}

function App() {
  const timetableVersion = useDashboardStore((s) => s.timetableVersion);
  const loadTimetable = useDashboardStore((s) => s.loadTimetable);

  useEffect(() => {
    loadTimetable();
  }, [loadTimetable]);

  return (
    <div className="min-h-screen bg-ink">
      <header className="border-b border-paper/10 px-8 py-5 flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-brass">
            Command Center
          </p>
          <h1 className="font-display text-3xl font-semibold text-paper mt-0.5">
            The Staffroom Ledger
          </h1>
        </div>
        <UploadControl />
      </header>

      <main className="max-w-6xl mx-auto px-8 py-8 space-y-10">
        <AlertFeed />

        {timetableVersion && <LedgerDiff version={timetableVersion} />}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <ReviewQueue />
          <TimetableGrid />
        </div>
      </main>
    </div>
  );
}

export default App;