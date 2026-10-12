"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { engine } from "@/lib/engine-client";
import { ROLE_LABELS, type ExternalRole } from "@/lib/permissions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Field } from "@/components/app/field";
import { NativeSelect } from "@/components/app/native-select";
import { StatusBadge } from "@/components/app/status-badge";

type Row = {
  id: string;
  role: ExternalRole;
  status: string;
  user_id: string;
  profiles: { full_name: string | null; email: string } | null;
};

const ROLES = Object.keys(ROLE_LABELS) as ExternalRole[];

export function CompanyUsers({ companyId, rows, canAdmin, currentUserId }: {
  companyId: string; rows: Row[]; canAdmin: boolean; currentUserId: string;
}) {
  const router = useRouter();
  const [inviteOpen, setInviteOpen] = useState(false);

  async function update(id: string, body: { role?: string; status?: string }) {
    try {
      await engine(`/memberships/${id}`, { method: "PATCH", json: body });
      toast.success("Membership updated");
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Company users</CardTitle>
        {canAdmin && (
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            <Plus /> Invite user
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Group</TableHead>
              <TableHead>Status</TableHead>
              {canAdmin && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.profiles?.full_name ?? "—"}</TableCell>
                <TableCell>{r.profiles?.email}</TableCell>
                <TableCell>
                  {canAdmin && r.user_id !== currentUserId ? (
                    <NativeSelect className="w-56" value={r.role} onChange={(e) => update(r.id, { role: e.target.value })}>
                      {ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}
                    </NativeSelect>
                  ) : (
                    ROLE_LABELS[r.role]
                  )}
                </TableCell>
                <TableCell>External</TableCell>
                <TableCell><StatusBadge status={r.status} /></TableCell>
                {canAdmin && (
                  <TableCell>
                    {r.user_id !== currentUserId &&
                      (r.status === "disabled" ? (
                        <Button size="xs" variant="outline" onClick={() => update(r.id, { status: "active" })}>Enable</Button>
                      ) : (
                        <Button size="xs" variant="ghost" onClick={() => update(r.id, { status: "disabled" })}>Disable</Button>
                      ))}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} companyId={companyId} onDone={() => router.refresh()} />
    </Card>
  );
}

function InviteDialog({ open, onOpenChange, companyId, onDone }: {
  open: boolean; onOpenChange: (o: boolean) => void; companyId: string; onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const res = await engine<{ invitation_sent: boolean }>(`/companies/${companyId}/invitations`, {
        method: "POST",
        json: { email: f.get("email"), role: f.get("role"), full_name: f.get("full_name") || null },
      });
      toast.success(res.invitation_sent ? "Invitation sent" : "Existing user added to the company");
      onOpenChange(false);
      onDone();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Invite user</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="grid gap-4">
          <Field label="Full name" htmlFor="inv-name"><Input id="inv-name" name="full_name" /></Field>
          <Field label="Email" htmlFor="inv-email"><Input id="inv-email" name="email" type="email" required /></Field>
          <Field label="Role" htmlFor="inv-role">
            <NativeSelect id="inv-role" name="role" defaultValue="DATA_ENTRY">
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </NativeSelect>
          </Field>
          <DialogFooter>
            <Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send invitation"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
