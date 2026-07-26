// LedgerDiff.tsx
// The signature element of the dashboard: a resolved scheduling change
// renders as a literal ledger correction — old value struck through,
// new value written beneath it, with a rotated rubber-stamp badge.
// This is the one deliberately bold visual choice; everything else
// in the dashboard stays quiet around it.

import { motion } from 'framer-motion';
import type { TimetableVersion } from './mockData';

function StampBadge({ status }: { status: TimetableVersion['solver_status'] }) {
  const label = status === 'OPTIMAL' ? 'RESOLVED' : status === 'FEASIBLE' ? 'PARTIAL' : 'NEEDS REVIEW';
  const color = status === 'OPTIMAL' ? 'border-sage text-sage' : 'border-rust text-rust';

  return (
    <motion.div
      initial={{ scale: 1.4, opacity: 0, rotate: -20 }}
      animate={{ scale: 1, opacity: 1, rotate: -6 }}
      transition={{ type: 'spring', stiffness: 200, damping: 12, delay: 0.4 }}
      className={`stamp inline-block border-4 ${color} rounded-md px-3 py-1 font-mono font-bold tracking-widest text-sm uppercase select-none`}
      style={{ mixBlendMode: 'multiply' }}
    >
      {label}
    </motion.div>
  );
}

export function LedgerDiff({ version }: { version: TimetableVersion }) {
  return (
    <div className="bg-paper paper-texture text-ink rounded-sm shadow-lg p-6 relative overflow-hidden">
      {/* ledger spine line */}
      <div className="absolute left-10 top-0 bottom-0 w-px bg-ink/15" />

      <div className="flex items-start justify-between mb-4 pl-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-ink/50">
            Timetable revision
          </p>
          <h3 className="font-display text-2xl font-semibold mt-1">
            {version.triggered_by_reason}
          </h3>
        </div>
        <StampBadge status={version.solver_status} />
      </div>

      <div className="space-y-4 pl-4">
        {version.diff.map((entry, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 * i }}
            className="border-l-2 border-ink/10 pl-4 py-2"
          >
            <p className="font-mono text-xs uppercase tracking-wide text-ink/50 mb-1">
              {entry.session_label}
            </p>
            <p className="font-mono text-base">
              <span className="line-through decoration-rust decoration-2 text-ink/40">
                {entry.old_value}
              </span>
              {' → '}
              <span className="text-sage-light font-semibold" style={{ color: '#3D6350' }}>
                {entry.new_value}
              </span>
            </p>
            <p className="text-sm text-ink/70 mt-1 italic">{entry.reasoning}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
