/** Shared TypeScript types mirroring backend mobile dataclasses. */

export interface FormFieldDef {
  field_name: string;
  field_type: string; // IDENTITY_LOCKED | TEAM_LOCKED | SYSTEM_TIME_DEFAULT | PROCESS_SELECTED | CONTEXT_DEFAULT | PRESET_SINGLE | PRESET_MULTI | MANUAL_NUMERIC | MANUAL_SHORT_TEXT | CALCULATED_LOCKED | RESOURCE_SELECT | PREVIOUS_VALUE_DEFAULT
  label: string;
  strategy: string; // AUTO_HIDDEN | AUTO_READ_ONLY | DEFAULT_EDITABLE | MANUAL_REQUIRED | REQUIRED_CHOICE | CONDITIONAL_INPUT | COMPUTED_READ_ONLY
  source: string;
  required: boolean;
  preset_options: string[] | null;
  default_value: unknown;
  editable: boolean;
  input_type: string; // text | number | select | multi-select
}

export interface FormSchema {
  form_type: string;
  title: string;
  modes: string[];
  allowed_processes: string[];
  fields: FormFieldDef[];
  version: string;
}

export interface ProductionContext {
  context_id: string;
  team_id: string;
  date: string;
  shift: string;
  work_orders: string[];
  products: string[];
  specs: string[];
  pieces_per_block: number | null;
}

export interface MobileSession {
  employee_name: string;
  employee_code: string;
  team_name: string;
  position: string;
  roles: string[];
  allowed_form_types: string[];
  allowed_processes: string[];
}

export interface CageResource {
  resource_id: string;
  short_code: string;
  variety: string;
  grade: string;
  supplier: string;
  current_status: string;
  last_process: string;
  last_process_time: string;
}

export interface FormSession {
  session_id: string;
  form_type: string;
  mode: string;
  prefill: Record<string, unknown>;
  locked_fields: string[];
  editable_defaults: Record<string, unknown>;
  preset_options: Record<string, string[]>;
}

export interface AvailableForm {
  form_type: string;
  title: string;
  modes: string[];
  allowed_processes?: string[];
}

/** Determines how a field should be rendered in the mobile form engine. */
export type FieldRenderStrategy =
  | "hidden"
  | "readonly"
  | "editable"
  | "required"
  | "choice"
  | "conditional"
  | "computed";
