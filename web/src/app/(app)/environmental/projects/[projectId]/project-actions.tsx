"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import type { Project, Stage } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";

const NEXT: Record<Stage, { to: Stage; label: string; approve?: boolean; variant?: "outline" }[]> = {
  DRAFT: [{ to: "DATA_COLLECTION", label: "Start data collection" }],
  DATA_COLLECTION: [{ to: "REVIEW", label: "Send for review" }],
  REVIEW: [{ to: "DATA_COLLECTION", label: "Back to data collection", variant: "outline" }, { to: "APPROVED", label: "Approve", approve: true }],
  APPROVED: [{ to: "REVIEW", label: "Reopen review", approve: true, variant: "outline" }, { to: "LOCKED", label: "Lock project", approve: true }],
  LOCKED: [],
};

export function ProjectActions({ project, canWrite, canApprove }: { project: Project; canWrite: boolean; canApprove: boolean }) {
  const router = useRouter();
  const [recalcOpen, setRecalcOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function move(to: Stage) {
    if (to === "LOCKED" && !window.confirm("Lock this project? Its data can no longer be changed; later corrections create a new calculation version.")) return;
    try {
      await engine(`/projects/${project.id}/transition`, { method: "POST", json: { to } });
      toast.success(`Project moved to ${to}`);
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function recalc(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const reason = String(new FormData(e.currentTarget).get("reason") ?? "");
    setBusy(true);
    try {
      const r = await engine<{ version_no: number; calculated: number; unknown_factor: number }>(`/projects/${project.id}/recalculate`, {
        method: "POST", json: { reason, confirm: project.stage === "LOCKED" },
      });
      toast.success(`Version ${r.version_no} created: ${r.calculated} calculated, ${r.unknown_factor} without a factor`);
      setRecalcOpen(false);
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const allowed = NEXT[project.stage].filter((a) => (a.approve ? canApprove : canWrite));
  const canRecalc = project.stage === "LOCKED" ? canApprove : canWrite;
  return (
    <>
      {allowed.map((a) => (
        <Button key={a.to} variant={a.variant} onClick={() => move(a.to)}>{a.label}</Button>
      ))}
      {canRecalc && <Button variant="outline" onClick={() => setRecalcOpen(true)}>Recalculate</Button>}
      <Dialog open={recalcOpen} onOpenChange={setRecalcOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Recalculate {project.stage === "LOCKED" ? "a LOCKED project" : "the project"}</DialogTitle>
            <DialogDescription>
              Creates a new calculation version using the emission factor library as it is now. The current version and its
              results are kept unchanged{project.stage === "LOCKED" ? "; the locked data itself is not edited" : ""}.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={recalc} className="grid gap-4">
            <Field label="Reason (recorded in the audit log)" htmlFor="rc-reason">
              <Input id="rc-reason" name="reason" required minLength={3} placeholder="e.g. Library factor updated" />
            </Field>
            <DialogFooter>
              <Button type="submit" disabled={busy}>{project.stage === "LOCKED" ? "I confirm: create a new version" : "Recalculate"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
