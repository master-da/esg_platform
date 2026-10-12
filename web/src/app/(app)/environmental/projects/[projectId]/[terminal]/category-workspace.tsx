"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalcTrailSheet } from "@/components/app/calc-trail";
import { CategorizationTab } from "./categorization-tab";
import { OverviewTab } from "./overview-tab";
import { SidePanel } from "./side-panel";
import type { Member, Note, Task, TerminalPageData } from "./types";
import { UploadTab } from "./upload-tab";

function Dot({ on }: { on: boolean }) {
  return on ? <span className="ml-1 inline-block size-1.5 rounded-full bg-red-600" aria-label="needs attention" /> : null;
}

export function CategoryWorkspace({ data, tasks, notes, members, canWrite, isInternal, initialTab }: {
  data: TerminalPageData; tasks: Task[]; notes: Note[]; members: Member[]; canWrite: boolean; isInternal: boolean; initialTab: string;
}) {
  const [tab, setTab] = useState(initialTab);
  const [trailId, setTrailId] = useState<number | null>(null);
  const t = data.terminal;

  if (!t.enabled) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900">
        {t.disabled_reason ?? "This category is not accepting data yet."}
      </div>
    );
  }
  if (data.category && !data.category.in_scope) {
    return (
      <div className="rounded-xl border bg-muted/50 p-6 text-sm">
        This category is marked <strong>not applicable</strong> for this project: {data.category.na_reason}
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList>
          <TabsTrigger value="upload">Data Upload<Dot on={data.need_attention_files > 0} /></TabsTrigger>
          {t.module === "ghg" && <TabsTrigger value="categorization">Data Categorization<Dot on={data.needs_categorization > 0} /></TabsTrigger>}
          <TabsTrigger value="overview">Data Overview</TabsTrigger>
        </TabsList>
        <TabsContent value="upload">
          <UploadTab data={data} canWrite={canWrite} isInternal={isInternal} onReviewCategorizations={() => setTab("categorization")} />
        </TabsContent>
        <TabsContent value="categorization">
          <CategorizationTab projectId={data.project.id} terminalKey={t.key} canWrite={canWrite} />
        </TabsContent>
        <TabsContent value="overview">
          <OverviewTab projectId={data.project.id} terminalKey={t.key} onOpenTrail={setTrailId} calculated={t.module === "ghg"} />
        </TabsContent>
      </Tabs>
      <SidePanel data={data} tasks={tasks} notes={notes} members={members} canWrite={canWrite} />
      <CalcTrailSheet calculationId={trailId} onClose={() => setTrailId(null)} />
    </div>
  );
}
