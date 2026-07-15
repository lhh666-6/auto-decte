import { describe, expect, it, vi } from "vitest";

import { MasterDataApi } from "../../../packages/api-client/src/master-data_ds";

describe("MasterDataApi", () => {
  it("lists inactive records and applies search", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );

    await new MasterDataApi("/api/v1", fetcher).list("employees", {
      includeInactive: true,
      query: " E001 ",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/master-data/employees?include_inactive=true&query=E001",
      { method: undefined, headers: {}, body: undefined },
    );
  });

  it("sends the current revision in If-Match when updating", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: "E001", revision: 4 }), { status: 200 }),
    );

    await new MasterDataApi("/api/v1", fetcher).update("employees", "E/001", {
      expected_revision: 3,
      display_name: "张三",
      attributes: { team: "A班" },
      reason: "调整班组",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/master-data/employees/E%2F001",
      {
        method: "PATCH",
        headers: { "If-Match": "\"3\"", "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_revision: 3,
          display_name: "张三",
          attributes: { team: "A班" },
          reason: "调整班组",
        }),
      },
    );
  });

  it("surfaces revision conflicts", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "MASTER_DATA_REVISION_CONFLICT",
          detail: "The record changed.",
        }),
        { status: 409 },
      ),
    );

    await expect(
      new MasterDataApi("/api/v1", fetcher).get("products", "P001"),
    ).rejects.toEqual(
      expect.objectContaining({
        status: 409,
        code: "MASTER_DATA_REVISION_CONFLICT",
      }),
    );
  });
});
