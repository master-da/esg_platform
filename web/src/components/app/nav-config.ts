import type { Ctx } from "@/lib/permissions";

export type NavItem = { label: string; href: string; internalOnly?: boolean };
export type NavSection = { label: string; items: NavItem[]; internalOnly?: boolean };

// Left navigation (PRD "Navigation & Information Architecture").
// Social / Governance sub-sections are not defined in the PRD; placement here is provisional.
export const NAV: NavSection[] = [
  {
    label: "Home",
    items: [
      { label: "Overview", href: "/home" },
      { label: "Company & facilities", href: "/home/company" },
      { label: "Results", href: "/home/results" },
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
      { label: "Emission factor library", href: "/internal/library" },
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
