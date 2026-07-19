import { describe, expect, it } from "vitest";

import {
  BUSINESS_ACTION_LABELS,
  getExportStatusCopy,
  getReviewStatusCopy,
  getTaskStatusCopy,
  getTemplateStatusCopy,
} from "./business-language";

type ExpectedCopy = {
  label: string;
  description: string;
  nextAction: string;
};

const REVIEW_STATUS_COPIES: Record<string, ExpectedCopy> = {
  IMPORTED: {
    label: "已导入",
    description: "表单照片已导入，正在等待后续处理。",
    nextAction: "等待系统处理",
  },
  NEEDS_CLASSIFICATION: {
    label: "待确认表单类型",
    description: "二维码未能确定模板，需要人工选择准确的已发布版本。",
    nextAction: "选择模板版本并说明原因",
  },
  CLASSIFIED: {
    label: "已确认表单类型",
    description: "已绑定准确的模板版本，正在等待识别结果。",
    nextAction: "等待识别完成",
  },
  RECOGNIZED: {
    label: "待核对",
    description: "系统已生成识别结果，需要逐项核对图片与填写值。",
    nextAction: "开始审核",
  },
  NEEDS_REVIEW: {
    label: "待核对",
    description: "识别结果中存在需要人工确认的内容。",
    nextAction: "开始审核",
  },
  RECAPTURE_REQUIRED: {
    label: "待重新拍照",
    description: "当前照片或填写内容无法继续，需要重新采集。",
    nextAction: "上传新的表单照片",
  },
  CONFIRMED: {
    label: "已确认",
    description: "字段已经人工确认，可以进入导出检查。",
    nextAction: "检查可导出的数据",
  },
  CORRECTED: {
    label: "已更正",
    description: "已确认记录已生成更正版本，需要重新检查导出状态。",
    nextAction: "检查重新导出",
  },
  VOIDED: {
    label: "已作废",
    description: "表单已退出正常处理流程，历史记录继续保留。",
    nextAction: "查看追溯详情",
  },
};

const EXPORT_STATUS_COPIES: Record<string, ExpectedCopy> = {
  NOT_EXPORTED: {
    label: "未导出",
    description: "记录尚未包含在成功生成的 Excel 文件中。",
    nextAction: "检查可导出的数据",
  },
  EXPORTED: {
    label: "已导出",
    description: "记录已包含在可追溯的导出批次中。",
    nextAction: "查看导出记录",
  },
  REEXPORT_REQUIRED: {
    label: "待重新导出",
    description: "记录在上次导出后发生修改，需要生成修正版。",
    nextAction: "选择原导出记录并重新导出",
  },
};

const TEMPLATE_STATUS_COPIES: Record<string, ExpectedCopy> = {
  DRAFT: {
    label: "草稿",
    description: "模板仍可编辑，尚未用于正式表单。",
    nextAction: "继续编辑模板",
  },
  PREFLIGHT_FAILED: {
    label: "预检未通过",
    description: "模板存在发布前问题，需要修改后重新检查。",
    nextAction: "修正问题并重新预检",
  },
  READY_TO_PUBLISH: {
    label: "可以发布",
    description: "模板已通过预检，可以发布为只读版本。",
    nextAction: "发布模板",
  },
  PUBLISHED: {
    label: "已发布",
    description: "模板版本只读，可用于分类、识别和打印。",
    nextAction: "查看只读版本",
  },
  DEPRECATED: {
    label: "已停用",
    description: "模板不再用于新业务，但历史记录继续保留。",
    nextAction: "查看历史版本",
  },
  RETIRED: {
    label: "已退役",
    description: "模板已退出使用，仅保留历史追溯。",
    nextAction: "查看历史版本",
  },
};

const TASK_STATUS_COPIES: Record<string, ExpectedCopy> = {
  PENDING: { label: "等待处理", description: "任务已经提交，正在等待系统开始处理。", nextAction: "等待任务开始" },
  RUNNING: { label: "正在处理", description: "系统正在处理当前任务。", nextAction: "查看处理进度" },
  SUCCEEDED: { label: "处理完成", description: "任务已经完成，可以继续下一步。", nextAction: "继续下一步" },
  FAILED: { label: "处理失败", description: "任务没有完成，请检查当前数据后重试。", nextAction: "检查后重试" },
  CANCEL_REQUESTED: { label: "正在取消", description: "系统正在停止当前任务。", nextAction: "等待任务停止" },
  CANCELLED: { label: "已取消", description: "任务已取消，没有生成最终结果。", nextAction: "按需重新开始" },
  INTERRUPTED: { label: "处理已中断", description: "任务在完成前中断，请检查当前数据后重试。", nextAction: "检查后重试" },
  RECOVERING: { label: "正在恢复", description: "系统正在恢复此前中断的任务。", nextAction: "等待恢复完成" },
};

function expectCompleteCopies(
  expected: Record<string, ExpectedCopy>,
  getCopy: (status: string) => ExpectedCopy & { technicalLabel: string },
) {
  for (const [status, copy] of Object.entries(expected)) {
    expect(getCopy(status), status).toEqual({ ...copy, technicalLabel: status });
  }
}

describe("business status language", () => {
  it("defines complete review status copy", () => {
    expectCompleteCopies(REVIEW_STATUS_COPIES, getReviewStatusCopy);
  });

  it("defines complete export status copy", () => {
    expectCompleteCopies(EXPORT_STATUS_COPIES, getExportStatusCopy);
  });

  it("defines complete template status copy", () => {
    expectCompleteCopies(TEMPLATE_STATUS_COPIES, getTemplateStatusCopy);
  });

  it("defines complete task status copy", () => {
    expectCompleteCopies(TASK_STATUS_COPIES, getTaskStatusCopy);
  });

  it.each([
    [getReviewStatusCopy, "FUTURE_REVIEW_STATE"],
    [getExportStatusCopy, "FUTURE_EXPORT_STATE"],
    [getTemplateStatusCopy, "FUTURE_TEMPLATE_STATE"],
    [getTaskStatusCopy, "FUTURE_TASK_STATE"],
  ])("keeps an unknown technical state traceable", (getCopy, status) => {
    expect(getCopy(status)).toEqual({
      label: "未知状态",
      description: "系统返回了尚未识别的状态。",
      nextAction: "查看追溯详情",
      technicalLabel: status,
    });
  });
});

describe("business action labels", () => {
  it("provides the approved action language from one source", () => {
    expect(BUSINESS_ACTION_LABELS).toEqual({
      uploadFormPhoto: "上传表单照片",
      findForm: "查找表单",
      startReview: "开始审核",
      pauseReview: "暂停审核",
      saveDraft: "暂存修改",
      confirmAndNext: "确认并审核下一张",
      saveCorrection: "保存本次修改",
      requestRecapture: "退回重新拍照",
      voidForm: "标记为无效",
      checkExportableData: "检查可导出的数据",
      generateExcel: "生成 Excel",
    });
  });
});
