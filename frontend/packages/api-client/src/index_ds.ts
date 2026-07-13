/**
 * API Client — re-exports.
 */
export type { ProblemDetails } from "./problem_ds.js";
export { isProblemDetails } from "./problem_ds.js";
export {
  ApiRequestError,
  ReviewWorkbenchApi,
  type AuditEvent,
  type EvidenceItem,
  type FormSummary,
  type RecognitionCandidate,
  type RecordVersion,
  type ReviewField,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "./review-workbench.js";

// When generated types exist, uncomment:
// export type * from "./generated_ds.js";
