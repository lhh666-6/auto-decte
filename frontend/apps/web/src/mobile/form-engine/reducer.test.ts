import { describe, expect, it } from "vitest";

import { createFormState, formReducer } from "./reducer";

describe("formReducer", () => {
  it("sets a value, touches the field, and clears its previous error", () => {
    const state = createFormState({ quantity: "" });
    state.errors.quantity = "请填写数量";

    const next = formReducer(state, { type: "SET_VALUE", field: "quantity", value: 3 });

    expect(next.values.quantity).toBe(3);
    expect(next.touched.quantity).toBe(true);
    expect(next.errors.quantity).toBeUndefined();
  });

  it("marks every invalid field touched on validation failure", () => {
    const next = formReducer(createFormState({}), {
      type: "VALIDATION_FAILED",
      errors: { quantity: "请填写数量", result: "请选择结果" },
    });

    expect(next.touched).toEqual({ quantity: true, result: true });
  });

  it("clears values that became conditionally hidden", () => {
    const next = formReducer(createFormState({ result: "EXCEPTION", exception_note: "旧异常" }), {
      type: "SET_VALUE",
      field: "result",
      value: "NORMAL",
      clearFields: ["exception_note"],
    });

    expect(next.values.exception_note).toBeUndefined();
  });
});
