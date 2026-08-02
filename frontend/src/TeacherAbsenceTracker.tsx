import React, { useEffect, useState } from 'react';

interface TeacherAbsenceSummary {
  teacher_name: string;
  leave_count: number;
}

export const TeacherAbsenceTracker: React.FC = () => {
  const [absenceData, setAbsenceData] = useState<TeacherAbsenceSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchAbsences = async () => {
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const res = await fetch(`${baseUrl}/analytics/teacher-absences`);
      const json = await res.json();
      if (json.status === 'success' && Array.isArray(json.data)) {
        setAbsenceData(json.data);
      }
    } catch (err) {
      console.error('Failed to load absence metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAbsences();
  }, []);

  const currentMonthName = new Date().toLocaleString('default', { month: 'long', year: 'numeric' });

  return (
    <div className="p-5 bg-[#F4F1EA] border border-black/20 rounded-md shadow-sm my-4">
      <div className="flex items-center justify-between mb-3 border-b border-black/10 pb-2">
        <div>
          <h2 className="font-serif text-lg font-bold text-[#111] flex items-center gap-2">
            <span>📋 Monthly Leave Counter</span>
          </h2>
          <p className="text-xs font-mono text-black/60">
            Resets Monthly • Active: {currentMonthName}
          </p>
        </div>
      </div>

      {loading ? (
        <p className="text-sm font-mono text-black/60 py-2">Loading leave counts...</p>
      ) : absenceData.length === 0 ? (
        <p className="text-sm text-black/70 italic py-2">
          No leave submissions recorded for this month yet.
        </p>
      ) : (
        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
          {absenceData.map((item, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-2.5 bg-white/80 rounded border border-black/10 shadow-xs"
            >
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-600"></span>
                <span className="font-semibold text-sm text-[#111] capitalize">
                  {item.teacher_name}
                </span>
              </div>
              <span className="text-xs font-mono font-bold px-2.5 py-1 bg-amber-100 text-amber-900 border border-amber-300 rounded-full">
                Leave Count: {item.leave_count}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TeacherAbsenceTracker;