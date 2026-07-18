import { ApiRequestError } from "@form-detection/api-client";

const BUSINESS_ERROR_COPY: Readonly<Record<string, string>> = {
  PERMISSION_DENIED:
    "当前操作未能完成：系统没有授予所需业务权限。请刷新页面后重试；如仍失败，请检查运行模式配置。",
  INTERNAL_ERROR:
    "服务暂时无法完成操作。请稍后重试；如问题持续，请记录发生时间并查看追溯详情。",
  INVALID_LIFECYCLE:
    "该模板版本当前不能修改。已发布版本请先克隆为新草稿，再调整版面或字段。",
  INVALID_FIELD:
    "字段设置不符合模板规则。请检查纸面填写方式、识别方式和审核填入方式后重试。",
  INVALID_PAGE_SIZE:
    "纸张尺寸不符合要求。请检查毫米宽高、方向和允许范围后重试。",
  INVALID_TEMPLATE:
    "模板设置不符合要求。请检查模板编号和纸张配置后重试。",
};

const INTERNAL_TERM = /(?:\b(?:actor|role|permission|payload|schema)\b|\blacks\b|[a-z_]+\.(?:read|write|create|download|confirm|correct|void|return)\b)/i;
const CHINESE_TEXT = /[\u3400-\u9fff]/;

export function businessErrorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiRequestError) {
    const mapped = BUSINESS_ERROR_COPY[cause.code];
    if (mapped) return mapped;
    if (CHINESE_TEXT.test(cause.message) && !INTERNAL_TERM.test(cause.message)) {
      return cause.message;
    }
    return `${fallback} 请稍后重试；如问题持续，请查看追溯详情。`;
  }
  if (cause instanceof Error && CHINESE_TEXT.test(cause.message)) {
    return cause.message;
  }
  return fallback;
}

export function businessProblemMessage(
  problem: { code?: string; detail?: string | { code?: string } },
  fallback: string,
): string {
  const detail = typeof problem.detail === "string" ? problem.detail : undefined;
  return businessErrorMessage(
    new ApiRequestError(
      0,
      problem.code ?? (typeof problem.detail === "object" ? problem.detail.code : undefined) ?? "REQUEST_FAILED",
      detail ?? "",
    ),
    fallback,
  );
}
