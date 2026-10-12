"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { NativeSelect } from "@/components/app/native-select";

type Metric = { key: string; name: string; unit: string | null; module: string; formula: string | null; params: Record<string, unknown> };
type Framework = { key: string; name: string };
type Mapping = { framework_key: string; metric_key: string; disclosure_ref: string; disclosure_title: string | null };

export function ReferenceAdmin({ metrics, frameworks, mappings, canEdit }: { metrics: Metric[]; frameworks: Framework[]; mappings: Mapping[]; canEdit: boolean }) {
  const router = useRouter();
  async function call(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); toast.success(ok); router.refresh(); } catch (e) { toast.error((e as Error).message); }
  }
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader><CardTitle>Metric library</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Metric</TableHead><TableHead>Formula</TableHead><TableHead>Parameters</TableHead></TableRow></TableHeader>
            <TableBody>
              {metrics.map((m) => (
                <TableRow key={m.key}>
                  <TableCell>{m.name}<div className="font-mono text-xs text-muted-foreground">{m.key} · {m.unit} · {m.module}</div></TableCell>
                  <TableCell className="text-xs">{m.formula}</TableCell>
                  <TableCell>
                    {Object.keys(m.params).length === 0 ? <span className="text-muted-foreground">—</span> : canEdit ? (
                      <form className="flex gap-2" onSubmit={(e) => {
                        e.preventDefault();
                        const raw = String(new FormData(e.currentTarget).get("params"));
                        let params: unknown;
                        try { params = JSON.parse(raw); } catch { return toast.error("Parameters must be valid JSON"); }
                        call(() => engine(`/reference/metrics/${m.key}`, { method: "PATCH", json: { params } }), "Metric parameters saved");
                      }}>
                        <Input name="params" defaultValue={JSON.stringify(m.params)} className="font-mono text-xs" />
                        <Button size="sm" type="submit" variant="outline">Save</Button>
                      </form>
                    ) : <code className="text-xs">{JSON.stringify(m.params)}</code>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Frameworks and mappings</CardTitle></CardHeader>
        <CardContent className="grid gap-4">
          {canEdit && (
            <form className="grid gap-2 sm:grid-cols-[1fr_2fr_auto]" onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              call(() => engine("/reference/frameworks", { method: "POST", json: { key: String(f.get("key")).toUpperCase(), name: String(f.get("name")) } }), "Framework saved");
            }}>
              <Input name="key" placeholder="KEY (e.g. ISSB_S2)" required />
              <Input name="name" placeholder="Framework name" required />
              <Button type="submit" variant="outline">Add framework</Button>
            </form>
          )}
          {canEdit && (
            <form className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_1fr_auto]" onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              call(() => engine("/reference/mappings", { method: "POST", json: { framework_key: f.get("framework_key"), metric_key: f.get("metric_key"),
                disclosure_ref: f.get("disclosure_ref"), disclosure_title: f.get("disclosure_title") || null } }), "Mapping added");
            }}>
              <NativeSelect name="framework_key">{frameworks.map((x) => <option key={x.key} value={x.key}>{x.name}</option>)}</NativeSelect>
              <NativeSelect name="metric_key">{metrics.map((x) => <option key={x.key} value={x.key}>{x.name}</option>)}</NativeSelect>
              <Input name="disclosure_ref" placeholder="Disclosure ref" required />
              <Input name="disclosure_title" placeholder="Title (optional)" />
              <Button type="submit" variant="outline">Add mapping</Button>
            </form>
          )}
          <Table>
            <TableHeader><TableRow><TableHead>Framework</TableHead><TableHead>Disclosure</TableHead><TableHead>Metric</TableHead>{canEdit && <TableHead />}</TableRow></TableHeader>
            <TableBody>
              {mappings.map((m) => (
                <TableRow key={`${m.framework_key}-${m.metric_key}-${m.disclosure_ref}`}>
                  <TableCell>{frameworks.find((f) => f.key === m.framework_key)?.name}</TableCell>
                  <TableCell>{m.disclosure_ref}</TableCell>
                  <TableCell>{metrics.find((x) => x.key === m.metric_key)?.name}</TableCell>
                  {canEdit && <TableCell><Button size="xs" variant="ghost" onClick={() => call(() => engine(`/reference/mappings?${new URLSearchParams({ framework_key: m.framework_key, metric_key: m.metric_key, disclosure_ref: m.disclosure_ref })}`, { method: "DELETE" }), "Mapping removed")}>Remove</Button></TableCell>}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
