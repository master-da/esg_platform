"use client";

import { useEffect, useState } from "react";
import { engine } from "@/lib/engine-client";
import { fmtDate, fmtNum } from "@/lib/format";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CalcTrailSheet } from "@/components/app/calc-trail";
import { Grade } from "@/components/app/values";

export type DrillQuery = { title: string; params: Record<string, string | number | undefined | null> } | null;
type Row = { calculation_id: number; supplier_name: string | null; facility: string; period_start: string; input_quantity: string; input_unit: string; co2e_t: string; taxonomy_display: string; quality_grade: string; category: string };

/** Click 1: the calculations behind a dashboard figure. Click 2 (a row): its full calculation trail. */
export function DrillSheet({ companyId, query, onClose }: { companyId: string; query: DrillQuery; onClose: () => void }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [trail, setTrail] = useState<number | null>(null);
  useEffect(() => {
    if (!query) return;
    const qs = new URLSearchParams(Object.entries(query.params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)]));
    let cancelled = false;
    engine<Row[]>(`/companies/${companyId}/insights/calcs?${qs}`).then((r) => { if (!cancelled) setRows(r); });
    return () => { cancelled = true; };
  }, [companyId, query]);
  return (
    <>
      <Sheet open={query !== null && trail === null} onOpenChange={(o) => !o && (setRows(null), onClose())}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{query?.title}</SheetTitle>
            <SheetDescription>The calculations behind this figure. Select a row to see how it was calculated.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            {rows === null ? <p className="text-sm text-muted-foreground">Loading…</p> : (
              <Table>
                <TableHeader><TableRow><TableHead>Category</TableHead><TableHead>Facility · supplier</TableHead><TableHead>Period</TableHead><TableHead className="text-right">Input</TableHead><TableHead className="text-right">t CO₂e</TableHead><TableHead /></TableRow></TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.calculation_id} className="cursor-pointer" onClick={() => setTrail(r.calculation_id)}>
                      <TableCell className="text-xs">{r.taxonomy_display.split(" > ").slice(1).join(" › ")}</TableCell>
                      <TableCell className="text-xs">{r.facility}{r.supplier_name ? ` · ${r.supplier_name}` : ""}</TableCell>
                      <TableCell className="text-xs">{fmtDate(r.period_start)}</TableCell>
                      <TableCell className="text-right text-xs tabular-nums">{fmtNum(r.input_quantity, 2)} {r.input_unit}</TableCell>
                      <TableCell className="text-right tabular-nums">{fmtNum(r.co2e_t, 4)}</TableCell>
                      <TableCell><Grade grade={r.quality_grade} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </SheetContent>
      </Sheet>
      <CalcTrailSheet calculationId={trail} onClose={() => setTrail(null)} />
    </>
  );
}
