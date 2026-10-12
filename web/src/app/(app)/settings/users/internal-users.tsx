"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";

type Row = {
  user_id: string;
  internal_role: string;
  can_edit_library: boolean;
  active: boolean;
  profiles: { full_name: string | null; email: string } | null;
};

export function InternalUsers({ rows, isPlatformAdmin }: { rows: Row[]; isPlatformAdmin: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggleLibrary(r: Row) {
    try {
      await engine(`/admin/internal-users/${r.user_id}`, { method: "PATCH", json: { can_edit_library: !r.can_edit_library } });
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      await engine("/admin/internal-users", {
        method: "POST",
        json: {
          email: f.get("email"),
          full_name: f.get("full_name") || null,
          internal_role: f.get("internal_role"),
          can_edit_library: f.get("can_edit_library") === "on",
        },
      });
      toast.success("Internal user invited");
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Internal users (platform staff)</CardTitle>
        {isPlatformAdmin && (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}><Plus /> Add internal user</Button>
        )}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Library editor</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.user_id}>
                <TableCell>
                  <div className="font-medium">{r.profiles?.full_name ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">{r.profiles?.email}</div>
                </TableCell>
                <TableCell>{r.internal_role}</TableCell>
                <TableCell>
                  <Checkbox
                    checked={r.internal_role === "PLATFORM_ADMIN" || r.can_edit_library}
                    disabled={!isPlatformAdmin || r.internal_role === "PLATFORM_ADMIN"}
                    onCheckedChange={() => toggleLibrary(r)}
                    aria-label="Can edit the emission factor library"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add internal user</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="grid gap-4">
            <Field label="Full name" htmlFor="iu-name"><Input id="iu-name" name="full_name" /></Field>
            <Field label="Email" htmlFor="iu-email"><Input id="iu-email" name="email" type="email" required /></Field>
            <Field label="Internal role" htmlFor="iu-role">
              <NativeSelect id="iu-role" name="internal_role" defaultValue="INTERNAL_USER">
                <option value="INTERNAL_USER">Internal user (reviewer)</option>
                <option value="PLATFORM_ADMIN">Platform admin</option>
              </NativeSelect>
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="can_edit_library" /> Can edit the emission factor library
            </label>
            <DialogFooter><Button type="submit" disabled={busy}>Send invitation</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
