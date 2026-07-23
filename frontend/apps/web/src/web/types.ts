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
  type: string;
  plant_id: string;
  title: string;
  body: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
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
