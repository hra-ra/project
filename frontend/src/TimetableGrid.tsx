// TimetableGrid.tsx
// A compact period-grid strip. Substituted sessions are visually marked
// (brass left-border + small "SUB" tag) so the effect of a resolved
// conflict is visible in-place, not just in the diff ledger above it.

import { useDashboardStore } from './store';

export function TimetableGrid() {
  const grid = useDashboardStore((s) => s.timetableGrid);
  const periods = Object.keys(grid);

  return (
    <div>
      <h2 className="font-display text-xl font-semibold text-paper mb-3">
        Monday · Live schedule
      </h2>
      {periods.length === 0 && (
        <p className="text-paper/50 font-mono text-sm italic">
          Loading schedule from the database…
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {periods.map((period) => (
          <div key={period} className="bg-ink-light rounded-sm p-4">
            <p className="font-mono text-xs uppercase tracking-widest text-brass mb-3">
              {period}
            </p>
            <div className="space-y-2">
              {grid[period].map((cell, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between text-sm border-l-2 pl-3 py-1.5 ${cell.is_substitute ? 'border-brass' : 'border-paper/10'
                    }`}
                >
                  <div>
                    <span className="text-paper font-medium">{cell.section}</span>
                    <span className="text-paper/50"> · {cell.subject}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-paper/70 text-xs">{cell.teacher}</span>
                    {cell.is_substitute && (
                      <span className="font-mono text-[10px] uppercase bg-brass text-ink px-1.5 py-0.5 rounded-sm font-bold">
                        Sub
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}