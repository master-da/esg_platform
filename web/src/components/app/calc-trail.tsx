"use client";

import { useEffect, useState } from "react";
import { engine } from "@/lib/engine-client";
import { fmtDate, fmtDateTime, fmtNum } from "@/lib/format";
import type { Trail } from "@/lib/types";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Grade, Missing } from "@/components/app/values";
import { StatusBadge } from "@/components/app/status-badge";

/** "View calculation": activity -> factor -> source -> formula -> result, in full (PRD F7). */
export function CalcTrailSheet({ calculationId, onClose }: { calculationId: number | null; onClose: () => void }) {
  const [trail, setTrail] = useState<Trail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (calculationId === null) return;
    let cancelled = false;
    engine<Trail>(`/calculations/${calculationId}`)
      .then((t) => { if (!cancelled) { setTrail(t); setError(null); } })
      .catch((e) => { if (!cancelled) setError((e as Error).message); });
    return () => { cancelled = true; };
  }, [calculationId]);

  const t = trail && trail.id === calculationId ? trail : null;
  return (
    <Sheet open={calculationId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{t ? `${t.supplier_name ?? t.facility} · ${t.category}` : "Calculation"}</SheetTitle>
          <SheetDescription>{t?.taxonomy_display ?? "Loading…"}</SheetDescription>
        </SheetHeader>
        {error && <p className="px-4 text-sm text-destructive">{error}</p>}
        {t && (
          <div className="grid gap-4 px-4 pb-6 text-sm">
            <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-2">
              <dt className="text-muted-foreground">Source file</dt>
              <dd>{t.file_name ? <>{t.file_name}{t.source_row ? ` · row ${t.source_row}` : ""}</> : t.source_type.replace("_", " ")}</dd>
              <dt className="text-muted-foreground">Facility · period</dt>
              <dd>{t.facility} · {fmtDate(t.period_start)} – {fmtDate(t.period_end)}</dd>
              <dt className="text-muted-foreground">Input data</dt>
              <dd className="tabular-nums">{fmtNum(t.input_quantity, 6)}</dd>
              <dt className="text-muted-foreground">Input unit</dt>
              <dd>{t.input_unit}</dd>
              {t.conversion_multiplier && (
                <>
                  <dt className="text-muted-foreground">Conversion factor</dt>
                  <dd>
                    <span className="tabular-nums">{fmtNum(t.conversion_multiplier, 8)}</span> {t.conversion_to}/{t.conversion_from}
                    <span className="block text-xs text-muted-foreground">
                      {t.conversion_from} → {t.conversion_to} = {fmtNum(t.factor_unit_quantity, 6)} {t.conversion_to}. {t.conversion_source}
                    </span>
                  </dd>
                </>
              )}
              <dt className="text-muted-foreground">Emission factor</dt>
              <dd>
                {t.factor_value ? <><span className="tabular-nums">{t.factor_value}</span> kg CO₂e / {t.factor_unit}</> : <Missing label="UNKNOWN" />}
                {t.gwp_version && <span className="block text-xs text-muted-foreground">GWP {t.gwp_version} · geography {t.factor_geography}</span>}
              </dd>
              <dt className="text-muted-foreground">Emission factor database</dt>
              <dd>
                {t.factor_source_name ? (
                  <>
                    {t.factor_source_url ? <a className="text-primary hover:underline" href={t.factor_source_url} target="_blank" rel="noreferrer">{t.factor_source_name}</a> : t.factor_source_name}
                    <span className="block text-xs text-muted-foreground">Year {t.factor_source_year} · library version {t.factor_version}</span>
                  </>
                ) : "—"}
              </dd>
              {t.factor_code && (
                <>
                  <dt className="text-muted-foreground">Factor code (internal)</dt>
                  <dd className="font-mono text-xs">{t.factor_code}</dd>
                </>
              )}
              <dt className="text-muted-foreground">Data quality</dt>
              <dd className="flex items-center gap-2"><Grade grade={t.quality_grade} /> {t.data_basis}</dd>
            </dl>

            <div className="rounded-lg bg-primary p-4 text-primary-foreground">
              <div className="text-xs opacity-80">Calculated GHG</div>
              {t.status === "CALCULATED" ? (
                <div className="text-2xl font-semibold tabular-nums">{fmtNum(t.co2e_t, 6)} t CO₂e</div>
              ) : (
                <div className="text-lg font-semibold">{t.status.replace("_", " ")}</div>
              )}
              {t.co2_kg && (
                <div className="mt-1 text-xs opacity-80">
                  of which CO₂ {fmtNum(t.co2_kg, 4)} kg · CH₄ {fmtNum(t.ch4_kg, 4) ?? "—"} kg CO₂e · N₂O {fmtNum(t.n2o_kg, 4) ?? "—"} kg CO₂e
                </div>
              )}
            </div>
            {t.message && <p className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{t.message}</p>}
            {t.formula && (
              <div>
                <div className="mb-1 text-xs font-medium text-muted-foreground">Formula</div>
                <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs whitespace-pre-wrap">{t.formula.split("; ").join("\n")}</pre>
              </div>
            )}
            <div className="text-xs text-muted-foreground">
              Calculation version {t.version_no}{t.frozen_at ? " (frozen)" : ""}, library as of {fmtDateTime(t.library_as_of)} · {t.engine_version} ·
              calculated {fmtDateTime(t.calculated_at)}{t.calculated_by_name ? ` by ${t.calculated_by_name}` : ""}
            </div>
            {t.history.length > 1 && (
              <div>
                <div className="mb-1 text-xs font-medium text-muted-foreground">History of this record</div>
                <ul className="space-y-1 text-xs">
                  {t.history.map((h) => (
                    <li key={h.id} className="flex items-center gap-2">
                      v{h.version_no} · {fmtDateTime(h.calculated_at)} · <StatusBadge status={h.status} label={h.status} tone={h.status === "CALCULATED" ? "green" : "red"} />
                      {h.co2e_t !== null && <span className="tabular-nums">{fmtNum(h.co2e_t, 6)} t</span>}
                      {h.id === t.id && <span className="text-muted-foreground">(shown)</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
