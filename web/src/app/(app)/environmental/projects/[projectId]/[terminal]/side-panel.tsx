"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NativeSelect } from "@/components/app/native-select";
import { NotesPanel } from "../project-tabs";
import type { Member, Note, Task, TerminalPageData } from "./types";

export function SidePanel({ data, tasks, notes, members, canWrite }: {
  data: TerminalPageData; tasks: Task[]; notes: Note[]; members: Member[]; canWrite: boolean;
}) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const [statusFilter, setStatusFilter] = useState("open");
  const t = data.terminal;

  async function addTask(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const { error } = await createClient().from("tasks").insert({
      company_id: data.project.company_id, project_id: data.project.id, terminal_key: t.key, kind: "collection",
      title: String(f.get("title")), assignee_id: String(f.get("assignee_id") || "") || null, due_date: String(f.get("due_date") || "") || null,
    });
    if (error) return toast.error(error.message);
    setAdding(false);
    router.refresh();
  }
  async function toggle(task: Task) {
    const done = task.status !== "done";
    const { error } = await createClient().from("tasks").update({ status: done ? "done" : "open", completed_at: done ? new Date().toISOString() : null }).eq("id", task.id);
    if (error) return toast.error(error.message);
    router.refresh();
  }

  const shown = tasks.filter((k) => statusFilter === "all" || k.status === statusFilter);
  return (
    <Card className="self-start">
      <CardContent>
        <div className="mb-2 text-sm font-semibold">Side panel</div>
        <Tabs defaultValue="tasks">
          <TabsList>
            <TabsTrigger value="tasks">Tasks</TabsTrigger>
            <TabsTrigger value="notes">Notes</TabsTrigger>
            <TabsTrigger value="instructions">Instructions</TabsTrigger>
          </TabsList>
          <TabsContent value="tasks" className="grid gap-3">
            <div className="flex items-center gap-2">
              <NativeSelect className="w-28" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status">
                <option value="open">Open</option><option value="done">Done</option><option value="all">All</option>
              </NativeSelect>
              {canWrite && <Button size="sm" className="ml-auto" onClick={() => setAdding((a) => !a)}><Plus /> Add task</Button>}
            </div>
            {adding && (
              <form onSubmit={addTask} className="grid gap-2 rounded-md border p-2">
                <Input name="title" placeholder="e.g. Collect March fuel receipts" required />
                <NativeSelect name="assignee_id" defaultValue=""><option value="">Unassigned</option>{members.map((m) => <option key={m.user_id} value={m.user_id}>{m.profiles?.full_name ?? m.profiles?.email}</option>)}</NativeSelect>
                <Input name="due_date" type="date" />
                <Button size="sm" type="submit">Save task</Button>
              </form>
            )}
            {shown.length === 0 && <p className="text-sm text-muted-foreground">No tasks in this category yet.</p>}
            {shown.map((k) => (
              <label key={k.id} className="flex items-start gap-2 rounded-md border p-2 text-sm">
                <input type="checkbox" className="mt-1" checked={k.status === "done"} disabled={!canWrite} onChange={() => toggle(k)} />
                <span>
                  <span className={k.status === "done" ? "line-through" : undefined}>{k.title}</span>
                  <span className="block text-xs text-muted-foreground">
                    {k.kind === "factor_request" ? "Factor request · " : ""}{k.profiles?.full_name ?? "Unassigned"}{k.due_date ? ` · due ${fmtDate(k.due_date)}` : ""}
                  </span>
                </span>
              </label>
            ))}
          </TabsContent>
          <TabsContent value="notes">
            <NotesPanel pid={data.project.id} companyId={data.project.company_id} terminalKey={t.key} notes={notes} canWrite={canWrite} />
          </TabsContent>
          <TabsContent value="instructions" className="grid gap-2 text-sm">
            <p>{t.instructions}</p>
            <p className="text-muted-foreground">{t.excludes}</p>
            <div className="text-xs text-muted-foreground">Template columns:</div>
            <ul className="list-disc pl-5 text-xs">
              {t.columns.map((c) => <li key={c.key}>{c.header}{c.required ? " (required)" : ""}{c.options.length ? `: ${c.options.join(", ")}` : ""}</li>)}
            </ul>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
