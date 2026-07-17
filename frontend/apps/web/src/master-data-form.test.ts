import { describe, expect, it } from "vitest";

import { attributesFromBusinessForm, businessFormFromRecord } from "./master-data-form";

describe("master data business form mapping", () => {
  it("maps employee fields and preserves unknown attributes", () => {
    const mapped = businessFormFromRecord("employees", {
      team: "A班",
      position: "操作员",
      phone: "13800000000",
      notes: "夜班",
      legacy_flag: true,
    });

    expect(mapped.values).toEqual({ team: "A班", position: "操作员", phone: "13800000000", notes: "夜班" });
    expect(mapped.extra).toEqual({ legacy_flag: true });
    expect(attributesFromBusinessForm("employees", mapped.values, mapped.extra)).toEqual({
      legacy_flag: true,
      team: "A班",
      position: "操作员",
      phone: "13800000000",
      notes: "夜班",
    });
  });

  it.each([
    ["work-orders", { product: "P001", planned_quantity: 100, start_date: "2026-07-01", end_date: "2026-07-31", owner: "张三" }],
    ["products", { specification: "M8", unit: "件" }],
    ["processes", { standard_sequence: 20, workstation: "WS-2" }],
  ] as const)("round trips %s without losing extra keys", (catalog, attributes) => {
    const source = { ...attributes, external_id: "legacy" };
    const mapped = businessFormFromRecord(catalog, source);
    expect(attributesFromBusinessForm(catalog, mapped.values, mapped.extra)).toEqual(source);
  });
});
