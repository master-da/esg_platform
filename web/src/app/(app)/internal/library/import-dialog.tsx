"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function ImportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const [result, setResult] = useState<{ created: number; errors: string[] } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await engine<{ created: number; errors: string[] }>("/library/import", {
        method: "POST",
        body: new FormData(e.currentTarget),
      });
      setResult(res);
      toast.success(`${res.created} draft factors created`);
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setResult(null); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Import draft factors</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-3 text-sm">
          <p className="text-muted-foreground">
            CSV with the columns of <span className="font-mono">reference-data/lib/emission_factors.csv</span> (taxonomy_code, geography_code,
            activity_unit, co2e, gwp_version, source_name, source_year, valid_from, valid_to …). Rows become drafts; nothing is activated by an import.
          </p>
          <input type="file" name="file" accept=".csv,text/csv" required className="text-sm" />
          {result && (
            <div className="rounded-md border p-2">
              <div>{result.created} created</div>
              {result.errors.map((e) => <div key={e} className="text-destructive">{e}</div>)}
            </div>
          )}
          <DialogFooter><Button type="submit" disabled={busy}>{busy ? "Importing…" : "Import"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
