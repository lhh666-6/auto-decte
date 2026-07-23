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
