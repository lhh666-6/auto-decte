import { describe, expect, it, vi } from "vitest";

import { MobileApiClient } from "./mobile_ds.js";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MobileApiClient", () => {
  it("does not call the default browser fetch with the client as its receiver", async () => {
    const originalFetch = globalThis.fetch;
    const browserFetch = vi.fn(function (this: unknown) {
      if (this instanceof MobileApiClient) {
        throw new TypeError("Illegal invocation");
      }
      return Promise.resolve(jsonResponse({
        employee_name: "张三",
        employee_code: "E001",
        team_name: "甲班",
        position: "操作工",
        roles: ["WORKER"],
        allowed_form_types: [],
        allowed_processes: [],
      }));
    });
    vi.stubGlobal("fetch", browserFetch);

    try {
      const client = new MobileApiClient();

      await expect(client.getSession()).resolves.toMatchObject({ employee_code: "E001" });
      expect(browserFetch.mock.instances[0]).not.toBe(client);
    } finally {
      vi.stubGlobal("fetch", originalFetch);
    }
  });

  it("uses same-origin cookies and never returns an auth token from login", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      employee_name: "张三",
      employee_code: "E001",
      team_name: "甲班",
      position: "操作工",
      roles: ["WORKER"],
      expires_at: null,
    }));
    const client = new MobileApiClient("/api/v1/mobile", fetcher);

    const result = await client.login("E001", "1234", "device-1");

    expect(result).not.toHaveProperty("token");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/mobile/auth/login",
      expect.objectContaining({ credentials: "same-origin", method: "POST" }),
    );
  });

  it("adds the CSRF cookie and idempotency key to submission writes", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      submission_id: "receipt-1",
      status: "ACCEPTED",
      submitted_at: "2026-07-21T00:00:00Z",
      idempotent: false,
    }));
    const client = new MobileApiClient(
      "/api/v1/mobile",
      fetcher,
      () => "csrf-value",
    );

    await client.createSubmission({
      form_type: "SELF_SHEET_PIECE",
      definition_version_id: "definition-1",
      mode: "SELF",
      subject_employee_code: "E001",
      device_id: "device-1",
      values: { quantity: 3 },
    }, "submission-key");

    const init = fetcher.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(init.credentials).toBe("same-origin");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-value");
    expect(headers.get("Idempotency-Key")).toBe("submission-key");
  });

  it("loads bamboo task buckets with the current session cookie", async () => {
    const fetcher = vi.fn().mockResolvedValue(jsonResponse({
      bucket: "available",
      tasks: [],
    }));
    const client = new MobileApiClient("/api/v1/mobile", fetcher);

    await client.listBambooTasks("available");

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/mobile/bamboo/tasks?bucket=available",
      expect.objectContaining({ credentials: "same-origin", method: "GET" }),
    );
  });

  it("writes bamboo records and signatures with CSRF and idempotency", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ record_id: "BR-1" }, 201))
      .mockResolvedValueOnce(jsonResponse({ record_id: "BR-1", revision: 2 }));
    const client = new MobileApiClient(
      "/api/v1/mobile",
      fetcher,
      () => "csrf-bamboo",
    );

    await client.createBambooRecord({ cage_no: "3-018" }, "create-1");
    await client.submitBambooStage("BR-1", "SORT", {
      expected_revision: 1,
      device_id: "phone-a",
      values: { moisture: [12, 13] },
    }, "sort-1");

    expect(fetcher.mock.calls[0]?.[0]).toBe("/api/v1/mobile/bamboo/records");
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      "/api/v1/mobile/bamboo/records/BR-1/stages/SORT/submit",
    );
    for (const call of fetcher.mock.calls) {
      const init = call[1] as RequestInit;
      const headers = new Headers(init.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf-bamboo");
      expect(headers.get("Idempotency-Key")).toMatch(/^(create|sort)-1$/);
    }
  });
});
