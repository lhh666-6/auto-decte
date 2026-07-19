import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@form-detection/api-client";
import { businessErrorMessage, businessProblemMessage } from "./business-errors";

describe("business error boundary", () => {
  it("replaces permission codes and internal permission names with actionable Chinese", () => {
    const message = businessErrorMessage(
      new ApiRequestError(403, "PERMISSION_DENIED", "Actor local-operator lacks template.read"),
      "模板请求无法完成。",
    );

    expect(message).toContain("当前操作未能完成");
    expect(message).toContain("请刷新页面后重试");
    expect(message).not.toContain("PERMISSION_DENIED");
    expect(message).not.toContain("template.read");
    expect(message).not.toContain("Actor");
  });

  it("keeps safe Chinese business details and hides unknown technical details", () => {
    expect(businessProblemMessage(
      { code: "DUPLICATE_EVIDENCE", detail: "该图片已经导入，请打开已有表单。" },
      "图片导入失败。",
    )).toBe("该图片已经导入，请打开已有表单。");

    expect(businessProblemMessage(
      { code: "REQUEST_FAILED", detail: "schema parse failed" },
      "图片导入失败。",
    )).toBe("图片导入失败。 请稍后重试；如问题持续，请查看追溯详情。");
  });

  it("maps template lifecycle, field and page failures to actionable Chinese", () => {
    expect(businessErrorMessage(
      new ApiRequestError(409, "INVALID_LIFECYCLE", "published template versions cannot be mutated"),
      "模板请求无法完成。",
    )).toContain("基于此版本创建新草稿");
    expect(businessErrorMessage(
      new ApiRequestError(422, "INVALID_FIELD", "FIELD_BEHAVIOR_MISMATCH"),
      "模板请求无法完成。",
    )).toContain("纸面填写方式");
    expect(businessErrorMessage(
      new ApiRequestError(422, "INVALID_PAGE_SIZE", "custom page width must be between 80 and 420 mm"),
      "模板请求无法完成。",
    )).toContain("毫米宽高");
  });
});
