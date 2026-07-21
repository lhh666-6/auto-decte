export interface FormState {
  values: Record<string, unknown>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  step: number;
  activity: "idle" | "submitting" | "saving-draft";
}

export type FormAction =
  | { type: "SET_VALUE"; field: string; value: unknown; clearFields?: string[] }
  | { type: "VALIDATION_FAILED"; errors: Record<string, string> }
  | { type: "SET_STEP"; step: number }
  | { type: "SET_ACTIVITY"; activity: FormState["activity"] }
  | { type: "INIT"; values: Record<string, unknown> };

export function createFormState(values: Record<string, unknown>): FormState {
  return { values: { ...values }, errors: {}, touched: {}, step: 1, activity: "idle" };
}

export function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "SET_VALUE": {
      const values = { ...state.values, [action.field]: action.value };
      const errors = { ...state.errors };
      delete errors[action.field];
      for (const field of action.clearFields ?? []) {
        delete values[field];
        delete errors[field];
      }
      return {
        ...state,
        values,
        errors,
        touched: { ...state.touched, [action.field]: true },
      };
    }
    case "VALIDATION_FAILED":
      return {
        ...state,
        errors: { ...action.errors },
        touched: {
          ...state.touched,
          ...Object.fromEntries(Object.keys(action.errors).map((field) => [field, true])),
        },
      };
    case "SET_STEP":
      return { ...state, step: action.step };
    case "SET_ACTIVITY":
      return { ...state, activity: action.activity };
    case "INIT":
      return createFormState(action.values);
  }
}
