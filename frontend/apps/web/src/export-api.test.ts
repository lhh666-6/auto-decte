import { describe, expect, it, vi } from "vitest";

import { ExportApi } from "../../../packages/api-client/src/exports_ds";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ExportApi", () => {
  it("encodes preview filters and preserves configured identity credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      included: [],
      excluded: [],
      mapping_snapshot: [],
    }));
    const api = new ExportApi("/api/v1", fetcher, {
      credentials: "include",
      headers: { "X-Roles": "FINANCE", "X-Actor-ID": "finance-user" },
    });

    await api.preview({
      form_id: " FORM/一 ",
      employee_id: "E&01",
      work_order_id: "",
      review_status: "CONFIRMED",
      export_status: "REEXPORT_REQUIRED",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/exports/preview?form_id=FORM%2F%E4%B8%80&employee_id=E%2601&review_status=CONFIRMED&export_status=REEXPORT_REQUIRED",
      {
        method: "GET",
        credentials: "include",
        headers: { "X-Roles": "FINANCE", "X-Actor-ID": "finance-user" },
        body: undefined,
      },
    );
  });

  it("passes AbortSignal to preview fetches", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      included: [], excluded: [], mapping_snapshot: [],
    }));
    const controller = new AbortController();

    await new ExportApi("/api/v1", fetcher).preview(
      { export_status: "NOT_EXPORTED" },
      controller.signal,
    );

    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
  });

  it("creates an export with an idempotency key and a real superseded batch id", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      task_id: "TASK-1",
      status: "PENDING",
      status_url: "/api/v1/tasks/TASK-1",
      events_url: "/api/v1/tasks/TASK-1/events",
    }, 202));
    const api = new ExportApi("/api/v1", fetcher, {
      headers: { "X-Roles": "FINANCE" },
    });

    const created = await api.create({
      export_type: "PAYROLL",
      filters: { form_id: "FORM-1", employee_id: "" },
      supersedes_batch_id: "BATCH-OLD",
    }, "export-once");

    expect(created.task_id).toBe("TASK-1");
    expect(fetcher).toHaveBeenCalledWith("/api/v1/exports", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-Roles": "FINANCE",
        "Idempotency-Key": "export-once",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        export_type: "PAYROLL",
        filters: { form_id: "FORM-1" },
        supersedes_batch_id: "BATCH-OLD",
      }),
    });
  });

  it("polls task status until a terminal result while reporting progress", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        task_id: "TASK/1", operation: "XLSX_EXPORT", resource_id: "EXPORTS",
        status: "RUNNING", progress: 35, step: "WRITE_WORKBOOK", error: null,
      }))
      .mockResolvedValueOnce(jsonResponse({
        task_id: "TASK/1", operation: "XLSX_EXPORT", resource_id: "EXPORTS",
        status: "SUCCEEDED", progress: 100, step: "COMPLETE", error: null,
      }));
    const updates = vi.fn();
    const api = new ExportApi("/api/v1", fetcher);

    const task = await api.waitForTask("TASK/1", { intervalMs: 0, onUpdate: updates });

    expect(task.status).toBe("SUCCEEDED");
    expect(updates.mock.calls.map(([update]) => update.progress)).toEqual([35, 100]);
    expect(fetcher.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/tasks/TASK%2F1",
      "/api/v1/tasks/TASK%2F1",
    ]);
  });

  it("passes AbortSignal to task requests and rejects polling with AbortError", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      task_id: "TASK-1", operation: "XLSX_EXPORT", resource_id: "EXPORTS",
      status: "RUNNING", progress: 10, step: "VALIDATING", error: null,
    }));
    const controller = new AbortController();
    const waiting = new ExportApi("/api/v1", fetcher).waitForTask("TASK-1", {
      intervalMs: 1_000,
      signal: controller.signal,
    });
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    controller.abort();

    await expect(waiting).rejects.toEqual(expect.objectContaining({ name: "AbortError" }));
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
  });

  it("lists batches and loads an encoded batch detail", async () => {
    const batch = {
      export_batch_id: "BATCH/1",
      export_type: "PAYROLL",
      task_id: "TASK-1",
      template_snapshot: {},
      mapping_snapshot: [],
      mapping_hash: "hash",
      filters: {},
      included_records: [{ form_id: "FORM-1", record_version: 2 }],
      file_sha256: "sha",
      exported_by: "finance-user",
      exported_at: "2026-07-16T00:00:00Z",
      supersedes_batch_id: null,
      download_url: "/api/v1/exports/batches/BATCH%2F1/download",
      download_name: "payroll.xlsx",
    };
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse([batch]))
      .mockResolvedValueOnce(jsonResponse(batch));
    const api = new ExportApi("/api/v1", fetcher);

    expect(await api.listBatches()).toEqual([batch]);
    expect((await api.getBatch("BATCH/1")).supersedes_batch_id).toBeNull();
    expect(fetcher.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/exports/batches",
      "/api/v1/exports/batches/BATCH%2F1",
    ]);
  });

  it("downloads an authorized batch as a Blob without accepting a local path", async () => {
    const workbook = new Blob(["xlsx-bytes"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const fetcher = vi.fn().mockResolvedValue(new Response(workbook, { status: 200 }));
    const api = new ExportApi("/api/v1", fetcher, {
      credentials: "include",
      headers: { Authorization: "Bearer demo" },
    });

    const downloaded = await api.downloadBatch("BATCH/1");

    expect(downloaded).toBeInstanceOf(Blob);
    expect(await downloaded.text()).toBe("xlsx-bytes");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/exports/batches/BATCH%2F1/download",
      {
        method: "GET",
        credentials: "include",
        headers: { Authorization: "Bearer demo" },
        body: undefined,
      },
    );
  });
});
