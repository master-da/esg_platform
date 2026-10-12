import type { Ctx } from "@/lib/permissions";

export type NavItem = { label: string; href: string; internalOnly?: boolean };
export type NavSection = { label: string; items: NavItem[]; internalOnly?: boolean };

// Left navigation (PRD "Navigation & Information Architecture").
// Social / Governance sub-sections are not defined in the PRD; their placement here is provisional.
export const NAV: NavSection[] = [
  {
    label: "Home",
    items: [
      { label: "Overview", href: "/home" },
      { label: "Insights", href: "/home/insights" },
      { label: "Results", href: "/home/results" },
      { label: "Reports & exports", href: "/home/reports" },
      { label: "Reporting frameworks", href: "/home/frameworks" },
      { label: "Company & facilities", href: "/home/company" },
    ],
  },
  {
    label: "Environmental",
    items: [
      { label: "Projects", href: "/environmental/projects" },
      { label: "Energy", href: "/environmental/energy" },
      { label: "Water", href: "/environmental/water" },
      { label: "Waste", href: "/environmental/waste" },
    ],
  },
  {
    label: "Social",
    items: [
      { label: "Labour", href: "/social/labour" },
      { label: "Health & safety", href: "/social/safety" },
    ],
  },
  {
    label: "Governance",
    items: [
      { label: "Regulatory requirements", href: "/governance/regulations" },
      { label: "Permits & licences", href: "/governance/permits" },
    ],
  },
  {
    label: "Settings",
    items: [
      { label: "Users & roles", href: "/settings/users" },
      { label: "Organizations", href: "/settings/organizations", internalOnly: true },
    ],
  },
  {
    label: "Internal",
    internalOnly: true,
    items: [
      { label: "Review queue", href: "/internal/review" },
      { label: "Emission factor library", href: "/internal/library" },
      { label: "Reference data", href: "/internal/reference" },
      { label: "Audit log", href: "/internal/audit-log" },
    ],
  },
];

export function visibleNav(ctx: Pick<Ctx, "isInternal">): NavSection[] {
  return NAV.filter((s) => !s.internalOnly || ctx.isInternal).map((s) => ({
    ...s,
    items: s.items.filter((i) => !i.internalOnly || ctx.isInternal),
  }));
}
