"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

export type TerminalColumn = { key: string; header: string; type: string; required: boolean; options?: string[] };

/** One-row entry generated from a terminal's column configuration; validated by the same rules as uploads. */
export function ManualEntryForm({ projectId, terminalKey, columns, facilities, submitLabel = "Save record", onSaved }: {
  projectId: string; terminalKey: string; columns: TerminalColumn[]; facilities: string[]; submitLabel?: string; onSaved?: () => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const values = Object.fromEntries(columns.map((c) => [c.key, (String(f.get(c.key) ?? "").trim() || null)]));
    setBusy(true);
    try {
      await engine(`/projects/${projectId}/terminals/${terminalKey}/manual`, { method: "POST", json: { values } });
      toast.success("Record saved");
      (e.target as HTMLFormElement).reset();
      onSaved?.();
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message, { duration: 10000 });
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {columns.map((c) => (
        <Field key={c.key} label={`${c.header}${c.required ? "" : " (optional)"}`} htmlFor={`me-${terminalKey}-${c.key}`}>
          {c.type === "facility" ? (
            <NativeSelect id={`me-${terminalKey}-${c.key}`} name={c.key} required={c.required}>{facilities.map((n) => <option key={n}>{n}</option>)}</NativeSelect>
          ) : c.type === "enum" || c.type === "unit" ? (
            <NativeSelect id={`me-${terminalKey}-${c.key}`} name={c.key} required={c.required}>
              {!c.required && <option value="">—</option>}
              {(c.options ?? []).map((o) => <option key={o}>{o}</option>)}
            </NativeSelect>
          ) : (
            <Input id={`me-${terminalKey}-${c.key}`} name={c.key} required={c.required}
              type={c.type === "date" ? "date" : c.type === "decimal" || c.type === "integer" ? "number" : "text"}
              step={c.type === "decimal" ? "any" : undefined} min={c.type === "decimal" || c.type === "integer" ? 0 : undefined} />
          )}
        </Field>
      ))}
      <div className="flex items-end"><Button type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button></div>
    </form>
  );
}
