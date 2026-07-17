import { describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  TaskApi,
  type TaskStatusDetail,
} from "../../../packages/api-client/src/index_ds";

describe("TaskApi", () => {
  it("loads and parses a task status from the versioned task endpoint", async () => {
    const payload: TaskStatusDetail = {
      task_id: "TASK-1",
      operation: "FORM_RECOGNITION",
      resource_id: "FORM-1",
      status: "RUNNING",
      progress: 45,
      step: "FIELD_CROPPING",
      error: null,
    };
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const api = new TaskApi("/api/v1", fetcher);

    await expect(api.getTask("TASK-1")).resolves.toEqual(payload);
    expect(fetcher).toHaveBeenCalledWith("/api/v1/tasks/TASK-1", {
      method: "GET",
      credentials: "same-origin",
      headers: {},
    });
  });

  it("throws a structured ApiRequestError for non-success responses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: "TASK_NOT_FOUND",
        detail: "没有找到指定任务。",
      },
    }), {
      status: 404,
      headers: { "content-type": "application/problem+json" },
    }));
    const api = new TaskApi("/api/v1", fetcher);

    await expect(api.getTask("TASK/MISSING")).rejects.toEqual(expect.objectContaining({
      status: 404,
      code: "TASK_NOT_FOUND",
      message: "没有找到指定任务。",
    } satisfies Partial<ApiRequestError>));
    expect(fetcher).toHaveBeenCalledWith("/api/v1/tasks/TASK%2FMISSING", expect.any(Object));
  });
});
