import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Missing } from "@/components/app/values";

/** Stat tile: label, value (never 0 for missing), optional signed delta coloured by whether up is good. */
export function StatTile({ label, value, unit, hint, delta, upIsGood = false, href, children }: {
  label: string; value: string | null; unit?: string; hint?: ReactNode;
  delta?: { pct: number | null; vs: string } | null; upIsGood?: boolean; href?: string; children?: ReactNode;
}) {
  const body = (
    <div className={cn("rounded-xl border bg-card p-4", href && "transition-colors hover:bg-accent/40")}>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold">
        {value === null ? <Missing /> : <>{value}{unit && <span className="ml-1 text-base font-normal text-muted-foreground">{unit}</span>}</>}
      </div>
      {delta && (
        <div className="mt-1 text-xs">
          {delta.pct === null ? (
            <span className="text-muted-foreground">No comparison ({delta.vs})</span>
          ) : (
            <span className={(delta.pct > 0) === upIsGood || delta.pct === 0 ? "text-emerald-800" : "text-red-700"}>
              {delta.pct > 0 ? "▲" : delta.pct < 0 ? "▼" : "■"} {Math.abs(delta.pct).toFixed(1)}% <span className="text-muted-foreground">vs {delta.vs}</span>
            </span>
          )}
        </div>
      )}
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      {children}
    </div>
  );
  return href ? <a href={href}>{body}</a> : body;
}
