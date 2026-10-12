// UI-side mirror of the database role checks (app.can_* in the foundation migration).
// These only decide what to show; Postgres RLS and the engine enforce every action.

export type ExternalRole =
  | "COMPANY_ADMIN"
  | "SUSTAINABILITY_MANAGER"
  | "FACILITY_MANAGER"
  | "DATA_ENTRY"
  | "AUDITOR"
  | "VIEWER";

export type Ctx = {
  userId: string;
  email: string;
  fullName: string | null;
  internalRole: "PLATFORM_ADMIN" | "INTERNAL_USER" | null;
  isInternal: boolean;
  canEditLibrary: boolean;
  companies: { id: string; legal_name: string }[];
  activeCompany: { id: string; legal_name: string } | null;
  role: ExternalRole | null;
};

export const ROLE_LABELS: Record<ExternalRole, string> = {
  COMPANY_ADMIN: "Company admin",
  SUSTAINABILITY_MANAGER: "Sustainability manager",
  FACILITY_MANAGER: "Facility manager",
  DATA_ENTRY: "Data entry",
  AUDITOR: "Auditor (read-only)",
  VIEWER: "Viewer (read-only)",
};

type Perms = Pick<Ctx, "isInternal" | "internalRole" | "role">;

export const canWrite = (c: Perms) =>
  c.isInternal || ["COMPANY_ADMIN", "SUSTAINABILITY_MANAGER", "FACILITY_MANAGER", "DATA_ENTRY"].includes(c.role ?? "");
export const canManage = (c: Perms) => c.isInternal || ["COMPANY_ADMIN", "SUSTAINABILITY_MANAGER"].includes(c.role ?? "");
export const canApprove = (c: Perms) =>
  c.internalRole === "PLATFORM_ADMIN" || ["COMPANY_ADMIN", "SUSTAINABILITY_MANAGER"].includes(c.role ?? "");
export const canAdminUsers = (c: Perms) => c.internalRole === "PLATFORM_ADMIN" || c.role === "COMPANY_ADMIN";
