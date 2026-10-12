import { cn } from "@/lib/utils";
import { fmtNum } from "@/lib/format";

/** Renders "Missing" for absent data. Never renders an absent value as 0. */
export function Missing({ label = "Missing", className }: { label?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200 ring-inset",
        className,
      )}
    >
      {label}
    </span>
  );
}

export function Num({
  value,
  unit,
  digits = 2,
  missingLabel,
}: {
  value: number | string | null | undefined;
  unit?: string | null;
  digits?: number;
  missingLabel?: string;
}) {
  const text = fmtNum(value, digits);
  if (text === null) return <Missing label={missingLabel} />;
  return (
    <span className="tabular-nums">
      {text}
      {unit ? <span className="ml-1 text-muted-foreground">{unit}</span> : null}
    </span>
  );
}

const GRADE_STYLE: Record<string, string> = {
  A: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  B: "bg-sky-50 text-sky-800 ring-sky-200",
  C: "bg-amber-50 text-amber-800 ring-amber-200",
};

/** Data-quality grade (PRD 5.1): A primary/verified, B reliable secondary, C estimated/default. */
export function Grade({ grade }: { grade: string | null | undefined }) {
  if (!grade) return <Missing label="No grade" />;
  return (
    <span
      title={grade === "A" ? "Primary, verified data" : grade === "B" ? "Reliable secondary data" : "Estimated or default"}
      className={cn("inline-flex size-5 items-center justify-center rounded text-xs font-semibold ring-1 ring-inset", GRADE_STYLE[grade])}
    >
      {grade}
    </span>
  );
}
