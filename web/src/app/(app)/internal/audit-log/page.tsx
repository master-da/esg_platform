import Link from "next/link";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createClient } from "@/lib/supabase/server";
import { requireInternal } from "@/lib/session";
import { fmtDateTime } from "@/lib/format";
import { AuditDiff } from "./audit-diff";

const PAGE = 50;

export default async function AuditLogPage(props: PageProps<"/internal/audit-log">) {
  const ctx = await requireInternal();
  const sp = await props.searchParams;
  const page = Math.max(0, Number(sp.page ?? 0) || 0);
  const scope = sp.scope === "all" ? "all" : "company";
  const entity = typeof sp.entity === "string" ? sp.entity : "";
  const action = typeof sp.action === "string" ? sp.action : "";

  const supabase = await createClient();
  let q = supabase.from("audit_log").select("*").order("id", { ascending: false }).range(page * PAGE, page * PAGE + PAGE);
  if (scope === "company" && ctx.activeCompany) q = q.eq("company_id", ctx.activeCompany.id);
  if (entity) q = q.ilike("entity", `%${entity}%`);
  if (action) q = q.eq("action", action.toUpperCase());
  const { data } = await q;
  const rows = data ?? [];
  const hasMore = rows.length > PAGE;

  const actorIds = [...new Set(rows.map((r) => r.actor_user_id).filter(Boolean))];
  const { data: actors } = actorIds.length
    ? await supabase.from("profiles").select("user_id, email").in("user_id", actorIds)
    : { data: [] };
  const email = new Map((actors ?? []).map((a) => [a.user_id, a.email]));
  const link = (p: Record<string, string | number>) =>
    `?${new URLSearchParams({ scope, entity, action, page: String(page), ...Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v)])) })}`;

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Internal" }, { label: "Audit log" }]}
        title="Audit log"
        description="Every create, change, delete, upload, calculation, approval and report. Append-only, and visible to internal users only."
      />
      <form className="mb-4 flex flex-wrap items-end gap-2 text-sm">
        <select name="scope" defaultValue={scope} className="h-8 rounded-lg border px-2">
          <option value="company">Active company only</option>
          <option value="all">All companies and reference data</option>
        </select>
        <input name="entity" defaultValue={entity} placeholder="Entity, e.g. facilities" className="h-8 rounded-lg border px-2" />
        <input name="action" defaultValue={action} placeholder="Action, e.g. UPDATE" className="h-8 rounded-lg border px-2" />
        <button className="h-8 rounded-lg bg-primary px-3 text-primary-foreground">Filter</button>
      </form>
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-44">When</TableHead>
                <TableHead>Who</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Change</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.slice(0, PAGE).map((r) => (
                <TableRow key={r.id} className="align-top">
                  <TableCell className="whitespace-nowrap">{fmtDateTime(r.at)}</TableCell>
                  <TableCell>
                    <div>{r.actor_user_id ? email.get(r.actor_user_id) ?? r.actor_user_id : "system"}</div>
                    <div className="text-xs text-muted-foreground">via {r.source}</div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{r.action}</TableCell>
                  <TableCell>
                    <div className="font-mono text-xs">{r.entity}</div>
                    <div className="max-w-56 truncate text-xs text-muted-foreground">{r.entity_id}</div>
                  </TableCell>
                  <TableCell><AuditDiff oldValue={r.old_value} newValue={r.new_value} detail={r.detail} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="mt-4 flex justify-between text-sm">
            {page > 0 ? <Link href={link({ page: page - 1 })} className="hover:underline">← Newer</Link> : <span />}
            {hasMore && <Link href={link({ page: page + 1 })} className="hover:underline">Older →</Link>}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
