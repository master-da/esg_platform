type Json = Record<string, unknown> | null;

const IGNORE = new Set(["updated_at", "created_at"]);

export function AuditDiff({ oldValue, newValue, detail }: { oldValue: Json; newValue: Json; detail: Json }) {
  if (detail) {
    return <pre className="max-w-xl overflow-x-auto text-xs whitespace-pre-wrap">{JSON.stringify(detail, null, 1)}</pre>;
  }
  if (oldValue && newValue) {
    const keys = Object.keys(newValue).filter((k) => !IGNORE.has(k) && JSON.stringify(oldValue[k]) !== JSON.stringify(newValue[k]));
    return (
      <ul className="space-y-0.5 text-xs">
        {keys.map((k) => (
          <li key={k}>
            <span className="font-mono">{k}</span>: <span className="text-red-700 line-through">{String(oldValue[k] ?? "∅")}</span>{" "}
            → <span className="text-emerald-700">{String(newValue[k] ?? "∅")}</span>
          </li>
        ))}
      </ul>
    );
  }
  const v = newValue ?? oldValue;
  if (!v) return null;
  const summary = Object.entries(v).filter(([k, val]) => !IGNORE.has(k) && val !== null).slice(0, 6);
  return (
    <ul className="space-y-0.5 text-xs text-muted-foreground">
      {summary.map(([k, val]) => <li key={k}><span className="font-mono">{k}</span>: {typeof val === "object" ? JSON.stringify(val) : String(val)}</li>)}
    </ul>
  );
}
