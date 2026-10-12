const SEGMENTS = [
  { key: "CALCULATED", label: "Calculated", className: "bg-emerald-800" },
  { key: "PRELIMINARY", label: "Preliminary", className: "bg-emerald-500" },
  { key: "READY_TO_CATEGORIZE", label: "Ready to categorize", className: "bg-zinc-300" },
  { key: "NEED_ATTENTION", label: "Need attention", className: "bg-red-600" },
];

export function ProgressBar({ progress }: { progress: Record<string, number> }) {
  const total = SEGMENTS.reduce((n, s) => n + (progress[s.key] ?? 0), 0);
  return (
    <div className="mb-6 rounded-xl border bg-card p-4">
      <div className="mb-2 text-sm font-semibold">Overall calculation progress</div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label="Categories by calculation status">
        {total > 0 &&
          SEGMENTS.map((s) => (progress[s.key] ? (
            <div key={s.key} className={s.className} style={{ width: `${((progress[s.key] ?? 0) / total) * 100}%` }} />
          ) : null))}
      </div>
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {SEGMENTS.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className={`inline-block size-2.5 rounded-sm ${s.className}`} /> {s.label}: {progress[s.key] ?? 0}
          </span>
        ))}
        {total === 0 && <span>No data uploaded yet.</span>}
      </div>
    </div>
  );
}
