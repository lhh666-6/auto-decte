/** Shared API error class — used by all API client modules. */

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}
