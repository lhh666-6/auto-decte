import type { MasterDataCatalog } from "@form-detection/api-client";

export interface BusinessFieldDefinition {
  key: string;
  attribute: string;
  label: string;
  type?: "number" | "date" | "tel";
}

export const MASTER_DATA_FORM: Record<MasterDataCatalog, {
  codeLabel: string;
  nameLabel: string;
  fields: BusinessFieldDefinition[];
}> = {
  employees: {
    codeLabel: "员工编号",
    nameLabel: "姓名",
    fields: [
      { key: "team", attribute: "team", label: "班组" },
      { key: "position", attribute: "position", label: "岗位" },
      { key: "phone", attribute: "phone", label: "联系电话", type: "tel" },
      { key: "notes", attribute: "notes", label: "备注" },
    ],
  },
  "work-orders": {
    codeLabel: "工单编号",
    nameLabel: "工单名称",
    fields: [
      { key: "product", attribute: "product", label: "关联产品" },
      { key: "plannedQuantity", attribute: "planned_quantity", label: "计划数量", type: "number" },
      { key: "startDate", attribute: "start_date", label: "开始日期", type: "date" },
      { key: "endDate", attribute: "end_date", label: "结束日期", type: "date" },
      { key: "owner", attribute: "owner", label: "负责人" },
    ],
  },
  products: {
    codeLabel: "产品编码",
    nameLabel: "产品名称",
    fields: [
      { key: "specification", attribute: "specification", label: "规格型号" },
      { key: "unit", attribute: "unit", label: "计量单位" },
    ],
  },
  processes: {
    codeLabel: "工序编码",
    nameLabel: "工序名称",
    fields: [
      { key: "standardSequence", attribute: "standard_sequence", label: "标准顺序", type: "number" },
      { key: "workstation", attribute: "workstation", label: "工作站" },
    ],
  },
};

export function businessFormFromRecord(
  catalog: MasterDataCatalog,
  attributes: Readonly<Record<string, unknown>>,
): { values: Record<string, string>; extra: Record<string, unknown> } {
  const definitions = MASTER_DATA_FORM[catalog].fields;
  const known = new Set(definitions.map((field) => field.attribute));
  return {
    values: Object.fromEntries(definitions.map((field) => [
      field.key,
      attributes[field.attribute] === null || attributes[field.attribute] === undefined
        ? ""
        : String(attributes[field.attribute]),
    ])),
    extra: Object.fromEntries(Object.entries(attributes).filter(([key]) => !known.has(key))),
  };
}

export function attributesFromBusinessForm(
  catalog: MasterDataCatalog,
  values: Readonly<Record<string, string>>,
  extra: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  const attributes: Record<string, unknown> = { ...extra };
  for (const field of MASTER_DATA_FORM[catalog].fields) {
    const value = values[field.key] ?? "";
    if (value === "") continue;
    attributes[field.attribute] = field.type === "number" ? Number(value) : value;
  }
  return attributes;
}
