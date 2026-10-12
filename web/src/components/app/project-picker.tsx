"use client";

import { usePathname, useRouter } from "next/navigation";
import { NativeSelect } from "@/components/app/native-select";

export function ProjectPicker({ projects, selected }: { projects: { id: string; name: string; stage: string }[]; selected?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  return (
    <NativeSelect className="w-64" value={selected} onChange={(e) => router.push(`${pathname}?project=${e.target.value}`)} aria-label="Project">
      {projects.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.stage}</option>)}
    </NativeSelect>
  );
}
