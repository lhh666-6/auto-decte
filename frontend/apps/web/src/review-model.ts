export interface ReviewValueField {
  fieldId: string;
  currentValue: unknown;
}

export function buildConfirmValues(
  fields: readonly ReviewValueField[],
  edits: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [
      field.fieldId,
      Object.hasOwn(edits, field.fieldId) ? edits[field.fieldId] : field.currentValue,
    ]),
  );
}
