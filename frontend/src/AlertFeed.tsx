// AlertFeed.tsx
// Proactive alerts, per the brief's explicit requirement: admins should
// see bottlenecks surfaced to them, not go hunting for data. Severity is
// encoded structurally (left border color + label), not just by color
// alone, so it reads even without relying on hue perception.

import { useDashboardStore } from './store';
import type { Alert } from './mockData';

const severityConfig: Record<Alert['severity'], { label: string; border: string; text: string }> = {
  critical: { label: 'CRITICAL', border: 'border-rust', text: 'text-rust-light' },
  watch: { label: 'WATCH', border: 'border-brass', text: 'text-brass' },
  info: { label: 'INFO', border: 'border-sage', text: 'text-sage-light' },
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ago`;
}

export function AlertFeed() {
  const alerts = useDashboardStore((s) => s.alerts);
  const resolveAlert = useDashboardStore((s) => s.resolveAlert);

  return (
    <div className="space-y-3">
      <h2 className="font-display text-xl font-semibold text-paper mb-3">
        Operational alerts
      </h2>
      {alerts.length === 0 && (
        <p className="text-paper/50 font-mono text-sm italic">No active alerts. All clear.</p>
      )}
      {alerts.map((alert) => {
        const config = severityConfig[alert.severity];
        return (
          <div
            key={alert.id}
            className={`bg-ink-light border-l-4 ${config.border} rounded-r-sm px-4 py-3 flex items-start justify-between gap-4 ${
              alert.resolved ? 'opacity-50' : ''
            }`}
          >
            <div>
              <span className={`font-mono text-xs font-bold tracking-widest ${config.text}`}>
                {config.label}
              </span>
              <p className="text-paper mt-1 text-sm leading-snug">{alert.message}</p>
              <span className="font-mono text-xs text-paper/40 mt-1 block">
                {timeAgo(alert.created_at)}
              </span>
            </div>
            {!alert.resolved && (
              <button
                onClick={() => resolveAlert(alert.id)}
                className="shrink-0 font-mono text-xs uppercase tracking-wide text-paper/60 hover:text-brass border border-paper/20 hover:border-brass rounded-sm px-2 py-1 transition-colors"
              >
                Dismiss
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
