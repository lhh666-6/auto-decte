export type WorkspaceRole = "ADMIN" | "FINANCE" | "PLANT_MANAGER";

export interface WebSession {
  employee_code: string;
  employee_name: string;
  workspace_role: WorkspaceRole;
  workspace_roles: WorkspaceRole[];
  factory_id: string;
  factory_name: string;
  landing_path: string;
}

export interface WorkspaceOverviewCard {
  key: string;
  label: string;
  value: number;
}

export interface WorkspaceOverview {
  workspace: WorkspaceRole;
  title: string;
  scope: string;
  factory_id: string;
  factory_name: string;
  cards: WorkspaceOverviewCard[];
}

export interface ManagedFormField {
  key: string;
  label: string;
  type: string;
  required?: boolean;
}

export interface ManagedFormVersion {
  definition_id: string;
  form_key: string;
  name: string;
  owner_role: string;
  version_id: string;
  version: number;
  schema_json: { fields?: ManagedFormField[] };
  content_hash: string;
  status: string;
  revision: number;
  created_by: string;
  created_at: string;
  review_comment: string;
  activation_status?: string;
  plant_id?: string;
}

export interface ManagementNotification {
  notification_id: string;
  category: string;
  title: string;
  body: string;
  link: string;
  payload: Record<string, unknown>;
  created_at: string;
  read_at?: string;
}

export interface BambooProductionRecord {
  record_id: string;
  display_no: string;
  factory_id: string;
  form_type: "SORTING" | "DIPPING_DRYING";
  source_record_id?: string;
  base_info: Record<string, unknown>;
  cage_no: string;
  current_stage?: string;
  status: string;
  revision: number;
  created_at: string;
  updated_at: string;
}

export interface BambooStageSubmission {
  submission_id: string;
  stage: string;
  version: number;
  values: Record<string, unknown>;
  actor_id: string;
  actor_name: string;
  role_code: string;
  factory_id?: string;
  submitted_at?: string;
  invalidated?: boolean;
}

export interface BambooInspectionEvidence {
  asset_id: string;
  evidence_type: string;
  file_id?: string;
  uri?: string;
  mime_type?: string;
  text_content?: string;
}

export interface BambooInspection {
  inspection_id: string;
  conclusion: string;
  note?: string;
  actor_name: string;
  signed_at?: string;
  moisture_points?: number[];
  average_value?: number;
  evidence: BambooInspectionEvidence[];
}

export interface BambooInspectionWindow {
  status: string;
  opened_at: string;
  deadline_at: string;
  inside_window: boolean;
  remaining_seconds: number;
  claimed_by?: string;
  completed_at?: string;
  terminated_by?: string;
  terminated_at?: string;
  appeal_deadline_at?: string;
  appeal_payload?: {
    text_evidence?: string;
    target_stage?: string;
  };
  appeal_decision?: string;
  appeal_decision_note?: string;
  revision: number;
}

export interface BambooPayrollFact {
  fact_id: string;
  record_id: string;
  fact_type: string;
  amount: string;
  period_start: string;
  period_end: string;
  rule_key: string;
  metric_value: string;
  rate: string;
  base_amount: string;
  allocations?: Array<{ employee_code: string; amount: string; rate?: string }>;
  total_amount?: string;
  version: number;
}

export interface BambooCorrectionCase {
  case_id: string;
  status: string;
  reason: string;
  created_at: string;
}

export interface BambooProductionDetail extends BambooProductionRecord {
  source_type?: string;
  source_snapshot?: Record<string, unknown>;
  submissions: BambooStageSubmission[];
  upstream_record?: {
    record_id: string;
    display_no: string;
    revision: number;
    base_info: Record<string, unknown>;
    submissions: BambooStageSubmission[];
  };
  inspection_window?: BambooInspectionWindow;
  signature_gate: {
    can_sign: boolean;
    reason: string;
  };
  inspections: BambooInspection[];
  payroll_facts: BambooPayrollFact[];
  corrections: BambooCorrectionCase[];
}

export interface BambooInspectionQueueItem {
  record_id: string;
  display_no: string;
  cage_no?: string;
  status: string;
  deadline_at: string;
  appeal_deadline_at?: string;
  appeal_payload?: { text_evidence?: string; target_stage?: string };
}

export interface BambooEmployee {
  employee_code: string;
  employee_name: string;
  factory_id: string;
  role_code: string;
  role_name: string;
}

export interface BambooPersonnelTransfer {
  transfer_id: string;
  employee_code: string;
  transfer_type: string;
  source_factory_id: string;
  target_factory_id: string;
  from_role: string;
  to_role: string;
  reason: string;
  status: string;
  revision: number;
}

export interface BambooPayrollItem {
  employee_code: string;
  amount: string;
}

export interface BambooWorkflowStage {
  stage: string;
  label: string;
  editable_by_plant_manager: boolean;
  returnable: boolean;
}

export interface ProposedBusinessRule {
  rule_id: string;
  content_json: { statement: string; questions?: string[] };
  confidence: number;
  status: string;
  executable: boolean;
}

export interface WorkflowNode {
  id: string;
  type: string;
  role?: string;
  form_version_id?: string;
}

export interface WorkflowVersion {
  workflow_key: string;
  name: string;
  version_id: string;
  version: number;
  graph_json: {
    nodes: WorkflowNode[];
    edges: Array<{ source: string; target: string; branch?: string }>;
    start_node_id: string;
  };
  status: string;
}

export interface FinanceRecord {
  root_submission_id: string;
  effective_submission_id: string;
  factory_id: string;
  subject_employee_code: string;
  definition_version_id: string;
  business_date: string;
  submitted_at: string;
  values: Record<string, unknown>;
  status: string;
}

export interface SubmissionCorrection {
  correction_id: string;
  root_submission_id: string;
  original_submission_id: string;
  replacement_submission_id?: string;
  factory_id: string;
  reason: string;
  delegate_reason: string;
  original_actor_id: string;
  actual_actor_id?: string;
  requested_by: string;
  reviewed_by?: string;
  review_note: string;
  status: string;
  idempotency_key: string;
  request_hash: string;
  correction_type: string;
  supplementary_note: string;
  created_at: string;
}

export interface BusinessTask {
  task_id: string;
  task_type: string;
  resource_id: string;
  factory_id: string;
  assigned_to: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface PayrollRuleVersion {
  rule_version_id: string;
  rule_key: string;
  name: string;
  factory_id: string;
  position: string;
  version: number;
  dsl: { metric: string; rate: string; base: string };
  content_hash: string;
  status: string;
  created_by: string;
  reviewed_by?: string;
  review_note: string;
}

export interface PayrollBatch {
  batch_id: string;
  batch_type: string;
  factory_id: string;
  period_start: string;
  period_end: string;
  data_watermark: string;
  rule_version_id: string;
  source_batch_id?: string;
  status: string;
  created_by: string;
  confirmed_by?: string;
}

export interface PayrollResult {
  result_id: string;
  batch_id: string;
  employee_code: string;
  factory_id: string;
  business_date: string;
  rule_version_id: string;
  amount: string;
  original_amount?: string;
  delta_amount?: string;
}

export interface ReportTemplateVersion {
  template_version_id: string;
  filename: string;
  format: string;
  file_hash: string;
  size_bytes: number;
  structure: {
    sheets: Array<{ name: string; max_row: number; max_column: number }>;
  };
  structure_hash: string;
  warnings: string[];
  status: string;
}

export interface ReportMappingVersion {
  mapping_version_id: string;
  template_version_id: string;
  version: number;
  mapping_json: {
    sheet: string;
    start_row: number;
    columns: Array<{ column: number; source_field: string }>;
  };
  status: string;
}

export interface GovernedExportBatch {
  export_batch_id: string;
  template_version_id: string;
  mapping_version_id: string;
  filters?: Record<string, unknown>;
  data_watermark: string;
  status: string;
  file_hash: string;
  download_name: string;
  created_by?: string;
  created_at?: string;
  record_count?: number | null;
  supersedes_batch_id?: string;
}

// ── V1 Quality Disposition ─────────────────────────────────────

export interface QualityDisposition {
  disposition_id: string;
  record_id: string;
  inspection_id: string | null;
  factory_id: string;
  cage_no: string;
  responsible_stage: string;
  responsible_submission_id: string | null;
  responsible_employee_code: string;
  responsible_employee_name_snapshot: string;
  responsible_position_snapshot: string;
  original_grade: string;
  effective_grade: string;
  decision: string;
  decision_note: string;
  decided_by: string;
  decided_at: string | null;
  revision: number;
}

export interface CreateDispositionInput {
  record_id: string;
  inspection_id?: string | null;
  factory_id: string;
  responsible_stage: string;
  original_grade: string;
  effective_grade: string;
  decision: string;
  decision_note?: string;
}

// ── V1 Employee Account State ──────────────────────────────────

export interface EmployeeAccountState {
  employee_code: string;
  account_state: string;
  active: boolean;
  factory_id: string;
  factory_name: string;
  position: string;
}
