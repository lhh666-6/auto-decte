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
