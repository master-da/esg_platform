"use client";

import { useState } from "react";
import { fmtNum } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CalcTrailSheet } from "@/components/app/calc-trail";
import { Missing } from "@/components/app/values";

export type ResultRow = {
  calculation_id: number; supplier_name: string | null; facility: string; input_quantity: string; input_unit: string;
  co2e_t: string | null; status: string; taxonomy_display: string | null;
};
export type ResultCategory = {
  terminal_key: string; category: string; scope: number; category_no: string | null; total_t: number | null; unknown: number; rows: ResultRow[];
};

export function ResultsView({ categories }: { categories: ResultCategory[] }) {
  const [scope, setScope] = useState<number | null>(null);
  const [trail, setTrail] = useState<number | null>(null);
  const shown = categories.filter((c) => scope === null || c.scope === scope);
  return (
    <>
      <div className="mb-4 flex gap-1">
        <Button size="sm" variant={scope === null ? "default" : "outline"} onClick={() => setScope(null)}>All categories</Button>
        {[1, 2, 3].map((s) => (
          <Button key={s} size="sm" variant={scope === s ? "default" : "outline"} onClick={() => setScope(s)}>Scope {s}</Button>
        ))}
      </div>
      {shown.length === 0 && <p className="text-sm text-muted-foreground">No calculated results yet. Results appear once data is categorized.</p>}
      <div className="grid gap-4">
        {shown.map((c) => (
          <Card key={c.terminal_key}>
            <CardHeader className="flex flex-row items-baseline justify-between">
              <CardTitle>Scope {c.scope} · {c.category}</CardTitle>
              <span className="text-sm text-muted-foreground">
                Category total: <span className="font-semibold text-foreground tabular-nums">{c.total_t === null ? "—" : fmtNum(c.total_t, 4)}</span> tCO₂e
                {c.unknown > 0 && <span className="ml-2 text-red-700">· {c.unknown} UNKNOWN (excluded, not zero)</span>}
              </span>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Supplier name</TableHead><TableHead className="text-right">Input</TableHead><TableHead>Input unit</TableHead><TableHead className="text-right">GHG</TableHead><TableHead>GHG unit</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {c.rows.map((r) => (
                    <TableRow key={r.calculation_id} onClick={() => setTrail(r.calculation_id)} className={cn("cursor-pointer", trail === r.calculation_id && "bg-accent")}>
                      <TableCell>{r.supplier_name ?? <span className="text-muted-foreground">{r.facility}</span>}</TableCell>
                      <TableCell className="text-right tabular-nums">{fmtNum(r.input_quantity, 4)}</TableCell>
                      <TableCell>{r.input_unit}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.status === "CALCULATED" ? fmtNum(r.co2e_t, 4) : <Missing label="UNKNOWN" />}</TableCell>
                      <TableCell>t CO₂e</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ))}
      </div>
      <CalcTrailSheet calculationId={trail} onClose={() => setTrail(null)} />
    </>
  );
}
