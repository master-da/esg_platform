"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

export function NewProjectDialog({ companyId }: { companyId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [boundary, setBoundary] = useState("organization");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => (String(f.get(k) ?? "").trim() || null);
    setBusy(true);
    try {
      const res = await engine<{ id: string }>("/projects", {
        method: "POST",
        json: {
          company_id: companyId, name: v("name"), period_type: v("period_type"), start_date: v("start_date"),
          end_date: v("end_date"), boundary, division_name: boundary === "division" ? v("division_name") : null,
          upload_deadline: v("upload_deadline"),
        },
      });
      toast.success("Project created");
      setOpen(false);
      router.push(`/environmental/projects/${res.id}`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}><Plus /> Create project</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Create project</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="grid gap-4">
            <Field label="Name" htmlFor="p-name"><Input id="p-name" name="name" placeholder="FY 2025" required /></Field>
            <Field label="Reporting period" htmlFor="p-type">
              <NativeSelect id="p-type" name="period_type" defaultValue="year">
                <option value="year">Year (financial or calendar)</option>
                <option value="half_year">Half-year</option>
                <option value="quarter">Quarter</option>
              </NativeSelect>
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Start date" htmlFor="p-start"><Input id="p-start" name="start_date" type="date" required /></Field>
              <Field label="End date" htmlFor="p-end"><Input id="p-end" name="end_date" type="date" required /></Field>
            </div>
            <Field label="Boundary" htmlFor="p-boundary">
              <NativeSelect id="p-boundary" value={boundary} onChange={(e) => setBoundary(e.target.value)}>
                <option value="organization">Whole organization</option>
                <option value="division">A division or entity</option>
              </NativeSelect>
            </Field>
            {boundary === "division" && (
              <Field label="Division / entity name" htmlFor="p-div"><Input id="p-div" name="division_name" required /></Field>
            )}
            <Field label="Upload deadline (optional)" htmlFor="p-deadline"><Input id="p-deadline" name="upload_deadline" type="date" /></Field>
            <DialogFooter><Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create project"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
