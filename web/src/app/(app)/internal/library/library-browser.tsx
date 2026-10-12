"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Upload } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { fmtDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/app/status-badge";
import { FactorForm } from "./factor-form";
import { ImportDialog } from "./import-dialog";

export type TreeNode = {
  id: string; code: string; parent_id: string | null; path: string; name: string; scope: number;
  ghg_category: string | null; is_leaf: boolean; sort: number; active_factors: number; draft_factors: number;
};
type Conversion = { id: string; from_unit: string; to_unit: string; multiplier: string; source_name: string; note: string | null };
export type FactorRow = {
  id: string; factor_code: string; version: number; geography_code: string; activity_unit: string; co2e: string;
  co2e_co2: string | null; co2e_ch4: string | null; co2e_n2o: string | null; gwp_version: string; source_name: string;
  source_url: string | null; source_year: number; source_ref: string | null; methodology: string | null;
  quality_rating: string | null; valid_from: string; valid_to: string; status: string; advisor_reviewed: boolean;
  notes: string | null; conversions: Conversion[];
};
type Detail = { node: TreeNode & { display_path: string }; factors: FactorRow[] };

export function LibraryBrowser({ tree, canEdit, units, geographies }: {
  tree: TreeNode[]; canEdit: boolean; units: { code: string; name: string; dimension: string }[];
  geographies: { code: string; name: string; level: string }[];
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Set<string>>(() => new Set(tree.filter((n) => !n.parent_id).map((n) => n.id)));
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const children = useMemo(() => {
    const m = new Map<string | null, TreeNode[]>();
    for (const n of tree) m.set(n.parent_id, [...(m.get(n.parent_id) ?? []), n]);
    for (const list of m.values()) list.sort((a, b) => a.sort - b.sort);
    return m;
  }, [tree]);

  const matches = useMemo(() => {
    if (!query.trim()) return null;
    const q = query.toLowerCase();
    return tree.filter((n) => n.name.toLowerCase().includes(q) || n.code.includes(q) || n.path.includes(q));
  }, [query, tree]);

  async function load(id: string) {
    setSelected(id);
    try {
      setDetail(await engine<Detail>(`/library/nodes/${id}`));
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  function renderNode(n: TreeNode, depth: number) {
    const kids = children.get(n.id) ?? [];
    const isOpen = open.has(n.id);
    return (
      <div key={n.id}>
        <button
          onClick={() => {
            if (kids.length) setOpen((s) => { const next = new Set(s); if (isOpen) next.delete(n.id); else next.add(n.id); return next; });
            load(n.id);
          }}
          className={cn("flex w-full items-center gap-1 rounded px-1.5 py-1 text-left text-sm hover:bg-accent", selected === n.id && "bg-accent font-medium")}
          style={{ paddingLeft: depth * 14 + 6 }}
        >
          {kids.length ? <ChevronRight className={cn("size-3.5 shrink-0 transition-transform", isOpen && "rotate-90")} /> : <span className="w-3.5" />}
          <span className="truncate">{n.name}</span>
          {n.is_leaf && (
            <span className={cn("ml-auto shrink-0 text-xs", n.active_factors ? "text-emerald-700" : "text-red-600")}>
              {n.active_factors ? `${n.active_factors}` : "none"}
            </span>
          )}
        </button>
        {isOpen && kids.map((k) => renderNode(k, depth + 1))}
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <Card className="self-start">
        <CardContent className="grid gap-3">
          <Input placeholder="Search name, code or path" value={query} onChange={(e) => setQuery(e.target.value)} />
          <div className="max-h-[70vh] overflow-y-auto">
            {matches
              ? matches.map((n) => (
                  <button key={n.id} onClick={() => load(n.id)} className={cn("block w-full rounded px-2 py-1 text-left text-sm hover:bg-accent", selected === n.id && "bg-accent")}>
                    <div>{n.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{n.code}</div>
                  </button>
                ))
              : (children.get(null) ?? []).map((n) => renderNode(n, 0))}
          </div>
          {canEdit && (
            <Button variant="outline" size="sm" onClick={() => setImportOpen(true)}><Upload /> Import draft factors (CSV)</Button>
          )}
        </CardContent>
      </Card>

      <div className="grid content-start gap-6">
        {!detail ? (
          <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Select a category to see its factor code and factors.</CardContent></Card>
        ) : (
          <NodeDetail key={detail.node.id} detail={detail} canEdit={canEdit} units={units} geographies={geographies} reload={() => load(detail.node.id)} />
        )}
      </div>
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}

function NodeDetail({ detail, canEdit, units, geographies, reload }: {
  detail: Detail; canEdit: boolean; units: { code: string; name: string; dimension: string }[];
  geographies: { code: string; name: string; level: string }[]; reload: () => void;
}) {
  const { node, factors } = detail;
  const [adding, setAdding] = useState(false);

  async function act(path: string, label: string, json?: unknown) {
    try {
      await engine(path, { method: path.endsWith("/delete") ? "DELETE" : "POST", json });
      toast.success(label);
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  async function remove(id: string) {
    try {
      await engine(`/library/factors/${id}`, { method: "DELETE" });
      toast.success("Draft deleted");
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{node.name}</CardTitle>
          <p className="text-sm text-muted-foreground">{node.display_path}</p>
        </CardHeader>
        <CardContent className="grid gap-1 text-sm sm:grid-cols-3">
          <div><span className="text-muted-foreground">Factor code:</span> <span className="font-mono">{node.code}</span></div>
          <div><span className="text-muted-foreground">Roll-up path:</span> <span className="font-mono text-xs">{node.path}</span></div>
          <div><span className="text-muted-foreground">Category:</span> {node.ghg_category ?? "—"} {node.is_leaf ? "· leaf" : ""}</div>
        </CardContent>
      </Card>

      {node.is_leaf && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Factors</CardTitle>
            {canEdit && <Button size="sm" onClick={() => setAdding((a) => !a)}>{adding ? "Cancel" : "Add factor"}</Button>}
          </CardHeader>
          <CardContent className="grid gap-4">
            {adding && (
              <FactorForm nodeId={node.id} units={units} geographies={geographies} onSaved={() => { setAdding(false); reload(); }} />
            )}
            {factors.length === 0 ? (
              <p className="text-sm text-red-700">
                No factor exists for this category. Calculations that use it show UNKNOWN until a cited factor is added and activated.
              </p>
            ) : (
              <div className="grid gap-3">
                {factors.map((f) => (
                  <div key={f.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
                        <span className="font-mono text-xs">{f.factor_code} · v{f.version}</span>
                        <span className="text-lg font-semibold tabular-nums">
                          {f.co2e} <span className="text-sm font-normal text-muted-foreground">kg CO₂e / {f.activity_unit}</span>
                        </span>
                        <span className="text-sm">{f.geography_code}</span>
                        <span className="text-sm text-muted-foreground">{fmtDate(f.valid_from)} – {fmtDate(f.valid_to)}</span>
                        <span className="text-xs text-muted-foreground">GWP {f.gwp_version}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        <StatusBadge status={f.status} label={f.status} tone={f.status === "active" ? "green" : f.status === "draft" ? "amber" : "gray"} />
                        {f.advisor_reviewed ? <StatusBadge status="VERIFIED" label="Advisor reviewed" /> : <StatusBadge status="NEEDS_REVIEW" label="Advisor review pending" />}
                      </div>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                      <div>
                        {f.source_url ? <a href={f.source_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{f.source_name}</a> : f.source_name}
                        {f.source_ref && <div className="text-muted-foreground">{f.source_ref}</div>}
                        {f.quality_rating && <div className="text-muted-foreground">Quality: {f.quality_rating}</div>}
                        {f.notes && <div className="text-muted-foreground italic">{f.notes}</div>}
                      </div>
                      <div className="tabular-nums">
                        {(f.co2e_co2 || f.co2e_ch4 || f.co2e_n2o) && (
                          <div>CO₂ {f.co2e_co2 ?? "—"} · CH₄ {f.co2e_ch4 ?? "—"} · N₂O {f.co2e_n2o ?? "—"}</div>
                        )}
                        {f.conversions.map((c) => (
                          <div key={c.id} className="font-mono" title={c.note ?? c.source_name}>
                            1 {c.from_unit} = {Number(c.multiplier).toPrecision(8)} {c.to_unit}
                          </div>
                        ))}
                      </div>
                    </div>
                    {canEdit && (
                      <div className="mt-2 flex flex-wrap gap-1 border-t pt-2">
                        {f.status === "draft" && (
                          <>
                            <Button size="xs" onClick={() => act(`/library/factors/${f.id}/activate`, "Factor activated")}>Activate</Button>
                            <Button size="xs" variant="ghost" onClick={() => remove(f.id)}>Delete draft</Button>
                          </>
                        )}
                        {f.status === "active" && (
                          <Button size="xs" variant="outline" onClick={() => act(`/library/factors/${f.id}/retire`, "Factor retired")}>Retire</Button>
                        )}
                        <Button size="xs" variant="ghost" onClick={() => act(`/library/factors/${f.id}/new-version`, "Draft version created")}>New version</Button>
                        <Button size="xs" variant="ghost" onClick={() => act(`/library/factors/${f.id}/review`, "Review status updated", { advisor_reviewed: !f.advisor_reviewed })}>
                          {f.advisor_reviewed ? "Unmark reviewed" : "Mark advisor-reviewed"}
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
