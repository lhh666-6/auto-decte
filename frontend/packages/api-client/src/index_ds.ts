/**
 * API Client — re-exports.
 */
export type { ProblemDetails } from "./problem_ds.js";
export { isProblemDetails } from "./problem_ds.js";
export {
  MasterDataApi,
  type CreateMasterDataInput,
  type MasterDataAudit,
  type MasterDataCatalog,
  type MasterDataRecord,
  type UpdateMasterDataInput,
} from "./master-data_ds.js";
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
  type ReviewFieldRules,
  type ReviewRuleFailure,
  type ReviewDraft,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "./review-workbench.js";
export {
  ExportApi,
  type CreateExportInput,
  type CreateExportResponse,
  type ExportApiRequestDefaults,
  type ExportBatch,
  type ExportExclusionReason,
  type ExportFilters,
  type ExportMapping,
  type ExportPreview,
  type ExportPreviewItem,
  type ExportReviewStatus,
  type ExportStatus,
  type ExportTask,
  type ExportTaskStatus,
  type IncludedExportRecord,
  type WaitForExportTaskOptions,
} from "./exports_ds.js";

// When generated types exist, uncomment:
// export type * from "./generated_ds.js";
