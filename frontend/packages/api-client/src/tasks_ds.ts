import { ApiRequestError } from "./api-error_ds.js";

export interface TaskStatusDetail {
  task_id: string;
  operation: string;
  resource_id: string;
  status:
    | "PENDING"
    | "RUNNING"
    | "SUCCEEDED"
    | "FAILED"
    | "CANCELLED"
    | "INTERRUPTED"
    | string;
  progress: number;
  step: string | null;
  error: string | null;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class TaskApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  async getTask(taskId: string, signal?: AbortSignal): Promise<TaskStatusDetail> {
    const response = await this.fetcher(
      `${this.baseUrl}/tasks/${encodeURIComponent(taskId)}`,
      {
        method: "GET",
        credentials: "same-origin",
        headers: {},
        ...(signal ? { signal } : {}),
      },
    );
    if (!response.ok) await throwApiError(response);
    return (await response.json()) as TaskStatusDetail;
  }
}

async function throwApiError(response: Response): Promise<never> {
  const problem = await response.json().catch(() => ({})) as {
    code?: string;
    detail?: string | { code?: string; detail?: string };
  };
  const nested = typeof problem.detail === "object" ? problem.detail : undefined;
  const detail = typeof problem.detail === "string"
    ? problem.detail
    : nested?.detail ?? `Request failed with status ${response.status}`;
  throw new ApiRequestError(
    response.status,
    problem.code ?? nested?.code ?? "REQUEST_FAILED",
    detail,
  );
}
