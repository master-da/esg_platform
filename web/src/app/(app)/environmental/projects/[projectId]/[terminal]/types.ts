import type { FileStatus, Project } from "@/lib/types";

export type TerminalInfo = {
  key: string; name: string; label: string; scope: number | null; category_no: string | null; module: string;
  description: string; excludes: string | null; instructions: string | null; accepts_bills: boolean; enabled: boolean;
  disabled_reason: string | null; template_version: string;
  columns: { key: string; header: string; type: string; required: boolean; options: string[] }[];
  categorization_keys: string[]; bill_fields: Record<string, string>;
};

export type TerminalPageData = {
  project: Project;
  terminal: TerminalInfo;
  category: { in_scope: boolean; na_reason: string | null; assignee_name: string | null } | null;
  files: FileStatus[];
  needs_categorization: number;
  need_attention_files: number;
};

export type Categorization = {
  id: string; input_display: Record<string, string>; status: "NEEDS" | "SUGGESTED" | "ACCEPTED";
  suggested_by: "rule" | "ai" | "user" | null; suggestion_note: string | null; suggested_path: string | null;
  accepted_path: string | null; accepted_by_name: string | null; accepted_at: string | null; records: number;
  files: string[] | null; factor_availability: "country" | "regional" | "global" | "none" | null;
  factor_requested_at: string | null;
};

export type RecordRow = {
  id: string; file_id: string | null; file_name: string | null; source_row: number | null; source_type: string;
  facility: string; supplier_name: string | null; period_start: string; period_end: string;
  attributes: Record<string, string | null>; category_input: Record<string, string> | null;
  original_quantity: string; original_unit: string; normalized_quantity: string; normalized_unit: string;
  quality_grade: string; review_status: string; categorization_status: string | null; categorized_as: string | null;
  calculation_id: number | null; calc_status: string | null; calc_message: string | null; co2e_t: string | null;
  file_status: string | null;
};

export type Task = { id: string; title: string; description: string | null; status: string; due_date: string | null; kind: string; assignee_id: string | null; profiles: { full_name: string | null } | null };
export type Note = { id: string; body: string; created_at: string; terminal_key: string | null; profiles: { full_name: string | null } | null };
export type Member = { user_id: string; profiles: { full_name: string | null; email: string } | null };
