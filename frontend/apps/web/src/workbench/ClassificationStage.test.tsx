// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClassificationOption, TaskStatusDetail } from "@form-detection/api-client";

import { ClassificationStage } from "./ClassificationStage";
import { RecognitionProgress } from "./RecognitionProgress";

const OPTIONS: ClassificationOption[] = [{
  template_key: "PAYROLL_HOURLY",
  version: 1,
  field_count: 8,
  page_size: "A4",
  orientation: "portrait",
}];

function task(status: string, progress: number, step: string | null, error: string | null = null): TaskStatusDetail {
  return {
    task_id: "TASK-1",
    operation: "FORM_RECOGNITION",
    resource_id: "FORM-1",
    status,
    progress,
    step,
    error,
  };
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ClassificationStage", () => {
  it("requires an exact published version and a classification reason", async () => {
    const assignTemplate = vi.fn();
    render(
      <ClassificationStage
        formId="FORM-1"
        options={OPTIONS}
        assignTemplate={assignTemplate}
        taskApi={{ getTask: vi.fn() }}
        onRecognitionSucceeded={() => undefined}
        onError={() => undefined}
      />,
    );

    const submit = screen.getByRole("button", { name: "确认表单类型并开始识别" }) as HTMLButtonElement;
    expect(screen.getByText("二维码未能确定表单类型")).toBeTruthy();
    expect(screen.getByText(/PAYROLL_HOURLY · V1 · 8 个字段/)).toBeTruthy();
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("已发布模板版本"), { target: { value: "PAYROLL_HOURLY@1" } });
    expect(submit.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("分类原因"), { target: { value: "二维码污损，依据标题确认" } });
    expect(submit.disabled).toBe(false);
  });

  it("keeps the classification in place and starts task progress after assignment", async () => {
    const assignTemplate = vi.fn().mockResolvedValue({
      form_id: "FORM-1",
      template_key: "PAYROLL_HOURLY",
      template_version: 1,
      review_status: "CLASSIFIED",
      recognition_task_id: "TASK-1",
      recognition_task_status: "PENDING",
    });
    render(
      <ClassificationStage
        formId="FORM-1"
        options={OPTIONS}
        assignTemplate={assignTemplate}
        taskApi={{ getTask: vi.fn().mockReturnValue(new Promise(() => undefined)) }}
        onRecognitionSucceeded={() => undefined}
        onError={() => undefined}
      />,
    );
    fireEvent.change(screen.getByLabelText("已发布模板版本"), { target: { value: "PAYROLL_HOURLY@1" } });
    fireEvent.change(screen.getByLabelText("分类原因"), { target: { value: "二维码污损" } });
    fireEvent.click(screen.getByRole("button", { name: "确认表单类型并开始识别" }));

    await waitFor(() => expect(assignTemplate).toHaveBeenCalledWith({
      templateKey: "PAYROLL_HOURLY",
      version: 1,
      reason: "二维码污损",
    }));
    expect(screen.getByText("二维码未能确定表单类型")).toBeTruthy();
    expect(await screen.findByText("识别任务 TASK-1")).toBeTruthy();
  });
});

describe("RecognitionProgress", () => {
  it("polls every 500ms, shows business steps and completes in place", async () => {
    vi.useFakeTimers();
    const getTask = vi.fn()
      .mockResolvedValueOnce(task("RUNNING", 35, "IMAGE_CORRECTION"))
      .mockResolvedValueOnce(task("RUNNING", 70, "FIELD_CROPPING"))
      .mockResolvedValueOnce(task("SUCCEEDED", 100, "RESULT_GENERATION"));
    const onSucceeded = vi.fn();
    render(
      <RecognitionProgress
        taskId="TASK-1"
        taskApi={{ getTask }}
        onSucceeded={onSucceeded}
        onFailure={() => undefined}
      />,
    );

    await act(async () => undefined);
    expect(screen.getByText("校正图片")).toBeTruthy();
    expect(screen.getByText("35%")).toBeTruthy();
    await act(async () => vi.advanceTimersByTimeAsync(500));
    expect(screen.getByText("裁切字段")).toBeTruthy();
    await act(async () => vi.advanceTimersByTimeAsync(500));
    expect(onSucceeded).toHaveBeenCalledTimes(1);
    expect(getTask).toHaveBeenCalledTimes(3);
  });

  it.each(["FAILED", "CANCELLED", "INTERRUPTED"])("stops and explains %s", async (status) => {
    const getTask = vi.fn().mockResolvedValue(task(status, 45, "FIELD_CROPPING", "识别服务中断"));
    const onFailure = vi.fn();
    render(
      <RecognitionProgress
        taskId="TASK-1"
        taskApi={{ getTask }}
        onSucceeded={() => undefined}
        onFailure={onFailure}
      />,
    );

    expect(await screen.findByText("识别没有完成")).toBeTruthy();
    expect(screen.getByText(/识别服务中断/)).toBeTruthy();
    expect(screen.getByText(/请检查照片后重试/)).toBeTruthy();
    expect(onFailure).toHaveBeenCalledWith(expect.objectContaining({ status }));
  });

  it("ignores an old response after switching tasks", async () => {
    let resolveOld!: (value: TaskStatusDetail) => void;
    const oldRequest = new Promise<TaskStatusDetail>((resolve) => { resolveOld = resolve; });
    const getTask = vi.fn().mockImplementation((taskId: string) => (
      taskId === "TASK-OLD" ? oldRequest : Promise.resolve({ ...task("RUNNING", 20, "IMAGE_CORRECTION"), task_id: "TASK-NEW" })
    ));
    const { rerender } = render(
      <RecognitionProgress
        taskId="TASK-OLD"
        taskApi={{ getTask }}
        onSucceeded={() => undefined}
        onFailure={() => undefined}
      />,
    );
    rerender(
      <RecognitionProgress
        taskId="TASK-NEW"
        taskApi={{ getTask }}
        onSucceeded={() => undefined}
        onFailure={() => undefined}
      />,
    );
    resolveOld({ ...task("FAILED", 10, "IMAGE_CORRECTION", "旧任务失败"), task_id: "TASK-OLD" });

    expect(await screen.findByText("校正图片")).toBeTruthy();
    expect(screen.queryByText(/旧任务失败/)).toBeNull();
  });
});
