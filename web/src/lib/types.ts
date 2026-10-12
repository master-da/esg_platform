// Shapes returned by the engine API (see engine/app/api/*).

export type Stage = "DRAFT" | "DATA_COLLECTION" | "REVIEW" | "APPROVED" | "LOCKED";

export type Project = {
  id: string;
  company_id: string;
  name: string;
  period_type: "year" | "half_year" | "quarter";
  start_date: string;
  end_date: string;
  boundary: "organization" | "division";
  division_name: string | null;
  upload_deadline: string | null;
  stage: Stage;
  current_version_id: string | null;
  locked_at: string | null;
};

export type ProjectListItem = Project & {
  co2e_t: number | null;
  calc_status: string;
  open_tasks: number;
  file_status_counts: Record<string, number>;
};

export type CategoryRow = {
  terminal_key: string;
  name: string;
  scope: number | null;
  category_no: string | null;
  module: string;
  enabled: boolean;
  disabled_reason: string | null;
  in_scope: boolean;
  na_reason: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  open_tasks: number;
  status: string;
  files: number;
  records: number;
  calculated: number;
  co2e_t: number | null;
  needs_categorization: number;
  need_attention_files: number;
  accepts_bills: boolean;
};

export type ProjectDetail = {
  project: Project;
  categories: CategoryRow[];
  versions: { id: string; version_no: number; library_as_of: string; reason: string; created_at: string; frozen_at: string | null; created_by_name: string | null }[];
  co2e_t: number | null;
  open_tasks: number;
  progress: Record<string, number>;
};

export type FileStatus = {
  file_id: string;
  terminal_key: string;
  kind: "template" | "bill";
  original_name: string;
  uploaded_at: string;
  uploaded_by_name?: string | null;
  row_count: number;
  records: number;
  calculated: number;
  calc_errors: number;
  validation_passed: boolean;
  last_review_action: string | null;
  last_review_comment: string | null;
  status: string;
};

export type Trail = {
  id: number;
  status: string;
  message: string | null;
  file_name: string | null;
  source_row: number | null;
  source_type: string;
  supplier_name: string | null;
  facility: string;
  period_start: string;
  period_end: string;
  category: string;
  taxonomy_display: string | null;
  input_quantity: string;
  input_unit: string;
  conversion_from: string | null;
  conversion_to: string | null;
  conversion_multiplier: string | null;
  conversion_kind: string | null;
  conversion_source: string | null;
  factor_unit_quantity: string | null;
  factor_value: string | null;
  factor_unit: string | null;
  factor_geography: string | null;
  factor_source_name: string | null;
  factor_source_url: string | null;
  factor_source_year: number | null;
  factor_version: number | null;
  gwp_version: string | null;
  co2e_kg: string | null;
  co2e_t: string | null;
  co2_kg: string | null;
  ch4_kg: string | null;
  n2o_kg: string | null;
  quality_grade: string | null;
  data_basis: string | null;
  formula: string | null;
  engine_version: string;
  version_no: number;
  library_as_of: string;
  frozen_at: string | null;
  calculated_at: string;
  calculated_by_name: string | null;
  factor_code?: string;
  history: { id: number; status: string; co2e_t: string | null; calculated_at: string; version_no: number }[];
};
