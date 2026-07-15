/**
 * API Client — re-exports.
 */
export type { ProblemDetails } from "./problem_ds.js";
export { isProblemDetails } from "./problem_ds.js";
export {
  TemplateApi,
  type PreflightReport,
  type TemplateArtifact,
  type TemplateDraftSummary,
  type TemplateField,
  type TemplateFieldInput,
  type TemplateLibraryItem,
  type TemplatePage,
  type TemplateRect,
  type TemplateStatus,
  type TemplateVersion,
  isEditableTemplateStatus,
} from "./templates_ds.js";
export {
  ApiRequestError,
  ReviewWorkbenchApi,
  type AuditEvent,
  type ClassificationOption,
  type ConfirmAndClaimNextResult,
  type EvidenceItem,
  type FormSummary,
  type RecognitionCandidate,
  type RecordVersion,
  type ReviewField,
  type ReviewDraft,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "./review-workbench.js";

// When generated types exist, uncomment:
// export type * from "./generated_ds.js";
