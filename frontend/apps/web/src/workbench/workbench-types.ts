export type MobilePane = "evidence" | "fields";

export type QueueKey = "classification" | "review" | "exceptions";

export type ReviewAction = "return" | "void";

export interface DuplicateImportInfo {
  code: "DUPLICATE_EVIDENCE";
  detail: string;
  existing_form: {
    form_id: string;
    review_status: string;
  };
  actions: {
    can_open: boolean;
    can_reopen_for_test: boolean;
    can_purge_for_test: boolean;
  };
}
