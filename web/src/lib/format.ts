// Number/date formatting. A missing value is never rendered as 0 (PRD 5.1: "Missing is never zero").

export function fmtNum(value: number | string | null | undefined, maxDigits = 2): string | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return null;
  return n.toLocaleString("en-US", { maximumFractionDigits: maxDigits });
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function fmtTonnes(kgOrT: number | string | null | undefined, digits = 2): string | null {
  return fmtNum(kgOrT, digits);
}
