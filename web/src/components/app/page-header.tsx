import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({
  crumbs = [],
  title,
  description,
  actions,
}: {
  crumbs?: { label: string; href?: string }[];
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {crumbs.length > 0 && (
          <nav className="mb-1 text-xs text-muted-foreground">
            {crumbs.map((c, i) => (
              <span key={i}>
                {i > 0 && <span className="mx-1">›</span>}
                {c.href ? (
                  <Link href={c.href} className="hover:underline">
                    {c.label}
                  </Link>
                ) : (
                  c.label
                )}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
