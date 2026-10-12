"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Receipt } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import type { TerminalInfo } from "./types";

/** Method 2 (PRD F5): upload a bill PDF or photo; the AI proposes values and a person confirms them. */
export function BillUpload({ projectId, terminal }: { projectId: string; terminal: TerminalInfo }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await engine<{ file_id: string; status: string }>(`/projects/${projectId}/terminals/${terminal.key}/bills`, { method: "POST", body: form });
      toast.success(r.status === "AI_EXTRACTED" ? "Values extracted. Review and confirm them." : "Bill stored. Enter the values from the bill.");
      router.push(`/environmental/projects/${projectId}/${terminal.key}/bills/${r.file_id}`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-sm">
      <span className="flex items-center gap-2"><Receipt className="size-4" /> Or upload an electricity bill (PDF or photo). AI proposes the values; nothing is saved until you confirm.</span>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Reading bill…" : "Upload bill"}</Button>
      <input ref={input} type="file" accept="application/pdf,image/jpeg,image/png,image/webp" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
    </div>
  );
}
