import Link from "next/link";
import { PageHeader } from "@/components/app/page-header";
import { ProjectPicker } from "@/components/app/project-picker";
import { StatTile } from "@/components/app/stat-tile";
import { StatusBadge } from "@/components/app/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { engineGet } from "@/lib/engine-server";
import { fmtDate, fmtNum } from "@/lib/format";
import { requireCompany } from "@/lib/session";

type Delta = { pct: number | null; months: number };
type Home = {
  project: { id: string; name: string; stage: string; start_date: string; end_date: string } | null;
  previous: { name: string } | null;
  projects: { id: string; name: string; stage: string }[];
  carbon?: { total_t: number | null; by_scope: { key: string; co2e_t: number }[]; unknown: number; delta: Delta };
  energy?: { total_kwh: number | null; renewable_share_pct: number | null; missing_months: string[]; delta: Delta };
  water?: { withdrawal_m3: number | null; delta: Delta };
  waste?: { total_t: number | null; recycling_rate_pct: number | null; hazardous_t: number | null; delta: Delta };
  compliance: { applicable: number; needs_review: number; permit_alerts: number; expired_permits: number };
};
type Alert = { id: string; permit_type: string; permit_number: string | null; facility: string | null; expiry_date: string; days_to_expiry: number; alert: string };

function vs(home: Home, d: Delta | undefined) {
  if (!d) return null;
  return { pct: d.pct, vs: home.previous ? `same ${d.months} month${d.months === 1 ? "" : "s"} of ${home.previous.name}` : "no earlier comparable project" };
}

export default async function HomePage(props: PageProps<"/home">) {
  const ctx = await requireCompany();
  const sp = await props.searchParams;
  const pid = typeof sp.project === "string" ? sp.project : "";
  const [home, alerts] = await Promise.all([
    engineGet<Home>(`/companies/${ctx.activeCompany.id}/home${pid ? `?project_id=${pid}` : ""}`),
    engineGet<Alert[]>(`/companies/${ctx.activeCompany.id}/permits/alerts`),
  ]);
  const scope = (k: string) => home.carbon?.by_scope.find((s) => s.key === k)?.co2e_t ?? null;
  return (
    <>
      <PageHeader
        title={ctx.activeCompany.legal_name}
        description={home.project ? <>Reporting period {fmtDate(home.project.start_date)} – {fmtDate(home.project.end_date)} · <StatusBadge status={home.project.stage} /></> : "No organization-wide project yet."}
        actions={home.projects.length > 0 && <ProjectPicker projects={home.projects} selected={home.project?.id} />}
      />
      {home.project ? (
        <div className="grid gap-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <StatTile label="Carbon (Scopes 1-3)" value={home.carbon?.total_t == null ? null : fmtNum(home.carbon.total_t, 1)} unit="t CO₂e"
              delta={vs(home, home.carbon?.delta)} upIsGood={false} href={`/home/insights?project=${home.project.id}`}
              hint={home.carbon?.unknown ? `${home.carbon.unknown} rows UNKNOWN (no factor), excluded` : undefined} />
            <StatTile label="Energy" value={home.energy?.total_kwh == null ? null : fmtNum(home.energy.total_kwh / 1000, 0)} unit="MWh"
              delta={vs(home, home.energy?.delta)} upIsGood={false} href={`/environmental/energy?project=${home.project.id}`}
              hint={home.energy?.renewable_share_pct != null ? `${fmtNum(home.energy.renewable_share_pct, 1)}% renewable` : undefined} />
            <StatTile label="Water withdrawal" value={home.water?.withdrawal_m3 == null ? null : fmtNum(home.water.withdrawal_m3, 0)} unit="m³"
              delta={vs(home, home.water?.delta)} upIsGood={false} href={`/environmental/water?project=${home.project.id}`} />
            <StatTile label="Waste" value={home.waste?.total_t == null ? null : fmtNum(home.waste.total_t, 1)} unit="t"
              delta={vs(home, home.waste?.delta)} upIsGood={false} href={`/environmental/waste?project=${home.project.id}`}
              hint={home.waste?.recycling_rate_pct != null ? `${fmtNum(home.waste.recycling_rate_pct, 1)}% recycled` : undefined} />
            <StatTile label="Compliance" value={String(home.compliance.applicable)} unit="requirements apply" href="/governance/regulations"
              hint={`${home.compliance.needs_review} need review · ${home.compliance.permit_alerts} permit alert${home.compliance.permit_alerts === 1 ? "" : "s"}`} />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Emissions by scope</CardTitle></CardHeader>
              <CardContent className="grid gap-2 text-sm">
                {["Scope 1", "Scope 2", "Scope 3"].map((s) => (
                  <div key={s} className="flex items-center justify-between border-b pb-2">
                    <span>{s}</span>
                    <span className="tabular-nums">{scope(s) === null ? <span className="text-muted-foreground">No calculated data</span> : `${fmtNum(scope(s), 2)} t CO₂e`}</span>
                  </div>
                ))}
                <Link className="text-primary hover:underline" href={`/home/insights?project=${home.project.id}`}>Open Insights →</Link>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Permit alerts</CardTitle></CardHeader>
              <CardContent className="text-sm">
                {alerts.length === 0 ? <p className="text-muted-foreground">No permits are due for renewal.</p> : (
                  <ul className="grid gap-2">
                    {alerts.map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-2 border-b pb-2">
                        <span>{a.permit_type}{a.permit_number ? ` (${a.permit_number})` : ""}<span className="block text-xs text-muted-foreground">{a.facility ?? "Company"} · expires {fmtDate(a.expiry_date)}</span></span>
                        <StatusBadge status={a.alert} label={a.alert === "expired" ? `✕ Expired ${-a.days_to_expiry} days ago` : `! Due in ${a.days_to_expiry} days`} tone={a.alert === "expired" ? "red" : "amber"} />
                      </li>
                    ))}
                  </ul>
                )}
                <Link className="mt-2 inline-block text-primary hover:underline" href="/governance/permits">Permits & licences →</Link>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <Card><CardContent className="py-8 text-sm text-muted-foreground">Create an organization-wide project in <Link className="underline" href="/environmental/projects">Projects</Link> to see the dashboard.</CardContent></Card>
      )}
    </>
  );
}
