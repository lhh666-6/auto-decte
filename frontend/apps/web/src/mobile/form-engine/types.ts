import type { ReactNode } from "react";

import type { FormFieldDef } from "../types";

export interface ConditionalRule {
  fieldName: string;
  dependsOn: string;
  showWhen: (triggerValue: unknown) => boolean;
}

export interface ComputeRule {
  fieldName: string;
  compute: (values: Record<string, unknown>) => number | string;
}

export interface MobileFormEngineProps {
  fields: FormFieldDef[];
  initialValues?: Record<string, unknown>;
  conditionalRules?: ConditionalRule[];
  computeRules?: ComputeRule[];
  onSubmit: (values: Record<string, unknown>) => void;
  submitting?: boolean;
  submitLabel?: string;
  onSaveDraft?: (values: Record<string, unknown>) => void;
  draftLabel?: string;
  children?: ReactNode;
}

export type FieldStrategy =
  | "hidden"
  | "readonly"
  | "editable"
  | "required"
  | "choice"
  | "conditional"
  | "computed";

export type ConditionalMap = Map<string, ConditionalRule>;
export type ComputeMap = Map<string, (values: Record<string, unknown>) => number | string>;

export function classifyStrategy(strategy: string): FieldStrategy {
  switch (strategy) {
    case "AUTO_HIDDEN": return "hidden";
    case "AUTO_READ_ONLY": return "readonly";
    case "DEFAULT_EDITABLE": return "editable";
    case "MANUAL_REQUIRED": return "required";
    case "REQUIRED_CHOICE": return "choice";
    case "CONDITIONAL_INPUT": return "conditional";
    case "COMPUTED_READ_ONLY": return "computed";
    default: return "readonly";
  }
}
