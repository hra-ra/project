import React, { useEffect, useState } from 'react';

interface TeacherStat {
  teacher_name: string;
  total_leaves: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
}

export const TeacherAbsenceTracker: React.FC = () => {
  const [stats, setStats] = useState<TeacherStat[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const res = await fetch(`${baseUrl}/analytics/teacher-absences`);
        const json = await res.json();
        if (json.status === 'success') {
          setStats(json.data);
        }
      } catch (err) {
        console.error('Failed to load absence analytics', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  const getRiskBadge = (level: 'LOW' | 'MEDIUM' | 'HIGH') => {
    switch (level) {
      case 'HIGH':
        return <span className="px-2 py-0.5 text-xs font-bold bg-[var(--color-rust)] text-white rounded">HIGH ABSENTEEISM</span>;
      case 'MEDIUM':
        return <span className="px-2 py-0.5 text-xs font-bold bg-[var(--color-brass)] text-black rounded">MODERATE</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-bold bg-[var(--color-sage)] text-white rounded">NORMAL</span>;
    }
  };

  return (
    <div className="p-4 bg-[var(--color-paper)] border border-[var(--color-ink)]/20 rounded-lg shadow-sm">
      <h2 className="font-serif text-lg font-bold text-[var(--color-ink)] mb-3 flex items-center justify-between">
        <span>📊 Teacher Absence & Leave Tracker</span>
        <span className="text-xs font-mono font-normal text-[var(--color-ink)]/60">Ledger Metrics</span>
      </h2>

      {loading ? (
        <p className="text-sm font-mono text-[var(--color-ink)]/60">Loading metrics...</p>
      ) : stats.length === 0 ? (
        <p className="text-sm text-[var(--color-ink)]/70 italic">No historical absence flags recorded yet.</p>
      ) : (
        <div className="space-y-2">
          {stats.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between p-2 bg-white/60 rounded border border-[var(--color-ink)]/10">
              <div>
                <p className="font-medium text-sm text-[var(--color-ink)]">{item.teacher_name}</p>
                <p className="text-xs font-mono text-[var(--color-ink)]/70">{item.total_leaves} leave form(s) recorded</p>
              </div>
              <div>{getRiskBadge(item.risk_level)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};