"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";
import { cn } from "@/lib/utils";
import type { Categorization } from "./types";

type Option = { id: string; display_path: string; name: string; factor_availability: string | null };

const AVAIL: Record<string, { text: string; className: string }> = {
  country: { text: "country factor available", className: "text-emerald-700" },
  regional: { text: "regional fallback", className: "text-amber-700" },
  global: { text: "global default factor", className: "text-amber-700" },
  none: { text: "no factor for this period: result will be UNKNOWN", className: "text-red-700" },
};

/** Wireframe "Data Categorization": only a person can accept a factor. Paths only, never codes. */
export function CategorizationTab({ projectId, terminalKey, canWrite }: { projectId: string; terminalKey: string; canWrite: boolean }) {
  const router = useRouter();
  const [rows, setRows] = useState<Categorization[] | null>(null);
  const [filter, setFilter] = useState<"all" | "pending" | "accepted">("all");
  const [by, setBy] = useState("any");
  const [picking, setPicking] = useState<Categorization | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    engine<Categorization[]>(`/projects/${projectId}/terminals/${terminalKey}/categorizations`).then(setRows).catch((e) => toast.error(e.message));
  }, [projectId, terminalKey]);
  useEffect(load, [load]);

  const visible = useMemo(() => (rows ?? []).filter((r) =>
    (filter === "all" || (filter === "accepted" ? r.status === "ACCEPTED" : r.status !== "ACCEPTED")) &&
    (by === "any" || r.suggested_by === by)), [rows, filter, by]);
  const accepted = (rows ?? []).filter((r) => r.status === "ACCEPTED").length;
  const suggested = (rows ?? []).filter((r) => r.status === "SUGGESTED").length;
  const total = rows?.length ?? 0;

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try {
      const r = await fn() as { calculated?: number; unknown_factor?: number };
      toast.success(r && typeof r.calculated === "number" ? `${ok}: ${r.calculated} rows calculated${r.unknown_factor ? `, ${r.unknown_factor} without a factor` : ""}` : ok);
      load();
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (rows === null) return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>;
  if (total === 0) return <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">Nothing to categorize yet. Upload a file that passes validation first.</CardContent></Card>;

  return (
    <div className="grid gap-4">
      <Card>
        <CardContent className="grid gap-2">
          <div className="text-sm font-medium">Categorization progress</div>
          <div className="h-2.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-emerald-700" style={{ width: `${total ? (accepted / total) * 100 : 0}%` }} />
          </div>
          <div className="text-xs text-muted-foreground">{accepted} of {total} accepted ({total ? Math.round((accepted / total) * 100) : 0}%)</div>
        </CardContent>
      </Card>
      <div className="flex flex-wrap items-center gap-2">
        {(["all", "pending", "accepted"] as const).map((f) => (
          <Button key={f} size="sm" variant={filter === f ? "default" : "outline"} onClick={() => setFilter(f)}>{f[0].toUpperCase() + f.slice(1)}</Button>
        ))}
        <NativeSelect className="w-44" value={by} onChange={(e) => setBy(e.target.value)} aria-label="Suggested by">
          <option value="any">Suggested by: any</option>
          <option value="rule">Suggested by rules</option>
          <option value="ai">Suggested by AI</option>
        </NativeSelect>
      </div>
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow><TableHead>Your input</TableHead><TableHead>Our categorization</TableHead><TableHead>Status</TableHead><TableHead className="w-48" /></TableRow>
            </TableHeader>
            <TableBody>
              {visible.length === 0 && <TableRow><TableCell colSpan={4} className="py-6 text-center text-muted-foreground">Nothing in this view.</TableCell></TableRow>}
              {visible.map((r) => {
                const path = r.accepted_path ?? r.suggested_path;
                const avail = r.factor_availability ? AVAIL[r.factor_availability] : null;
                return (
                  <TableRow key={r.id} className="align-top">
                    <TableCell>
                      {Object.entries(r.input_display).map(([k, v]) => <div key={k}><span className="text-muted-foreground">{k}:</span> {v}</div>)}
                      <div className="text-xs text-muted-foreground">{r.records} row{r.records === 1 ? "" : "s"}{r.files?.length ? ` · ${r.files.join(", ")}` : ""}</div>
                    </TableCell>
                    <TableCell>
                      {path ? <div>{path.split(" > ").slice(1).join(" › ")}</div> : <div className="text-muted-foreground">Uncategorized</div>}
                      {avail && <div className={cn("text-xs", avail.className)}>{avail.text}</div>}
                      {r.suggestion_note && r.status !== "ACCEPTED" && <div className="text-xs text-muted-foreground">AI note: {r.suggestion_note}</div>}
                    </TableCell>
                    <TableCell>
                      {r.status === "ACCEPTED" ? <StatusBadge status="ACCEPTED" label={`Accepted by ${r.accepted_by_name ?? "—"}`} /> :
                        r.status === "SUGGESTED" ? <StatusBadge status="SUGGESTED" label={`Suggested by ${r.suggested_by === "ai" ? "AI" : r.suggested_by === "rule" ? "rules" : "a user"}`} tone={r.suggested_by === "ai" ? "violet" : "amber"} /> :
                        <StatusBadge status="NEEDS" />}
                      {r.factor_requested_at && <div className="mt-1 text-xs text-muted-foreground">Factor requested</div>}
                    </TableCell>
                    <TableCell className="space-x-1 text-right">
                      {canWrite && r.status === "SUGGESTED" && (
                        <Button size="xs" disabled={busy} onClick={() => run(() => engine(`/categorizations/${r.id}/accept`, { method: "POST", json: {} }), "Accepted")}>Accept</Button>
                      )}
                      {canWrite && <Button size="xs" variant="outline" disabled={busy} onClick={() => setPicking(r)}>{r.status === "NEEDS" ? "Choose" : "Change"}</Button>}
                      {canWrite && (r.status === "NEEDS" || r.factor_availability === "none") && !r.factor_requested_at && (
                        <Button size="xs" variant="ghost" disabled={busy} onClick={() => run(() => engine(`/categorizations/${r.id}/request-factor`, { method: "POST" }), "Factor requested from the library team")}>Request factor</Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      {canWrite && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm">
          <span className="text-muted-foreground">Showing {visible.length} rows. Accepting is logged per row with your name and the time.</span>
          <Button disabled={!suggested || busy} onClick={() => run(() => engine(`/projects/${projectId}/terminals/${terminalKey}/categorizations/accept-suggested`, { method: "POST" }), "All suggestions accepted")}>
            Accept all suggested ({suggested})
          </Button>
        </div>
      )}
      <CategoryPicker projectId={projectId} terminalKey={terminalKey} target={picking} onClose={() => setPicking(null)}
        onPick={(node) => picking && run(() => engine(`/categorizations/${picking.id}/accept`, { method: "POST", json: { node_id: node } }), "Category accepted").then(() => setPicking(null))} />
    </div>
  );
}

function CategoryPicker({ projectId, terminalKey, target, onClose, onPick }: {
  projectId: string; terminalKey: string; target: Categorization | null; onClose: () => void; onPick: (id: string) => void;
}) {
  const [options, setOptions] = useState<Option[] | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    if (target && options === null) engine<Option[]>(`/projects/${projectId}/terminals/${terminalKey}/category-options`).then(setOptions);
  }, [target, options, projectId, terminalKey]);
  const shown = (options ?? []).filter((o) => o.display_path.toLowerCase().includes(q.toLowerCase()));
  return (
    <Dialog open={target !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader><DialogTitle>Choose the emission factor category</DialogTitle></DialogHeader>
        {target && <p className="text-sm text-muted-foreground">For: {Object.values(target.input_display).join(" · ")}</p>}
        <Input placeholder="Search categories" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="max-h-96 overflow-y-auto">
          {shown.map((o) => (
            <button key={o.id} onClick={() => onPick(o.id)} className="block w-full rounded-md px-2 py-2 text-left text-sm hover:bg-accent">
              <div>{o.display_path.split(" > ").slice(1).join(" › ")}</div>
              {o.factor_availability && <div className={cn("text-xs", AVAIL[o.factor_availability]?.className)}>{AVAIL[o.factor_availability]?.text}</div>}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
