import { describe, expect, it } from "vitest";

import { buildConfirmValues } from "./review-model";

describe("buildConfirmValues", () => {
  it("uses an edited field value without mutating the source fields", () => {
    const fields = [
      { fieldId: "quantity", currentValue: 8 },
      { fieldId: "work_order", currentValue: "WO-100" },
    ];

    const values = buildConfirmValues(fields, { quantity: "10" });

    expect(values).toEqual({ quantity: "10", work_order: "WO-100" });
    expect(fields[0].currentValue).toBe(8);
  });
});
