"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { NavSection } from "@/components/app/nav-config";

export function Sidebar({ sections }: { sections: NavSection[] }) {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/home" ? pathname === "/home" : pathname === href || pathname.startsWith(`${href}/`));
  return (
    <aside className="hidden w-60 shrink-0 border-r bg-sidebar md:block">
      <div className="sticky top-0 flex h-dvh flex-col">
        <Link href="/home" className="flex h-14 items-center gap-2 border-b px-4">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            CO₂
          </span>
          <span className="text-sm font-semibold leading-tight">ESG & Carbon<br />
            <span className="font-normal text-muted-foreground">Compliance platform</span>
          </span>
        </Link>
        <nav className="flex-1 overflow-y-auto p-3">
          {sections.map((s) => (
            <div key={s.label} className="mb-4">
              <div className="mb-1 px-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                {s.label}
              </div>
              {s.items.map((i) => (
                <Link
                  key={i.href}
                  href={i.href}
                  className={cn(
                    "block rounded-md px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
                    isActive(i.href) && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
                  )}
                >
                  {i.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
      </div>
    </aside>
  );
}
