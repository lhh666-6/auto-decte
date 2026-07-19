import { useEffect, useRef, useState } from "react";

import type { TaskStatusDetail } from "@form-detection/api-client";

import { TraceDetails } from "../ui/TraceDetails";
import { getTaskStatusCopy } from "../ui/business-language";

export interface TaskStatusReader {
  getTask(taskId: string, signal?: AbortSignal): Promise<TaskStatusDetail>;
}

interface RecognitionProgressProps {
  taskId: string;
  taskApi: TaskStatusReader;
  onSucceeded(task: TaskStatusDetail): void | Promise<void>;
  onFailure(task: TaskStatusDetail): void;
}

const FAILED_STATUSES = new Set(["FAILED", "CANCELLED", "INTERRUPTED"]);

function describeStep(step: string | null | undefined): string {
  const normalized = step?.toUpperCase() ?? "";

  if (normalized.includes("CORRECT")) {
    return "校正图片";
  }
  if (normalized.includes("CROP") || normalized.includes("FIELD")) {
    return "裁切字段";
  }
  if (normalized.includes("RESULT") || normalized.includes("RECOGN")) {
    return "生成识别结果";
  }
  return step || "准备识别";
}

export function RecognitionProgress({
  taskId,
  taskApi,
  onSucceeded,
  onFailure,
}: RecognitionProgressProps) {
  const [task, setTask] = useState<TaskStatusDetail | null>(null);
  const [requestError, setRequestError] = useState("");
  const onSucceededRef = useRef(onSucceeded);
  const onFailureRef = useRef(onFailure);

  onSucceededRef.current = onSucceeded;
  onFailureRef.current = onFailure;

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      try {
        const current = await taskApi.getTask(taskId, controller.signal);
        if (cancelled) {
          return;
        }

        setTask(current);
        setRequestError("");
        const status = current.status.toUpperCase();
        if (status === "SUCCEEDED") {
          await onSucceededRef.current(current);
          return;
        }
        if (FAILED_STATUSES.has(status)) {
          onFailureRef.current(current);
          return;
        }

        timer = window.setTimeout(() => {
          void poll();
        }, 500);
      } catch (cause) {
        if (cancelled || (cause instanceof DOMException && cause.name === "AbortError")) {
          return;
        }
        setRequestError(cause instanceof Error ? cause.message : "暂时无法读取识别进度");
        timer = window.setTimeout(() => {
          void poll();
        }, 500);
      }
    }

    setTask(null);
    setRequestError("");
    void poll();

    return () => {
      cancelled = true;
      controller.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [taskApi, taskId]);

  const status = task?.status.toUpperCase();
  const statusCopy = getTaskStatusCopy(status ?? "PENDING");
  const failed = status ? FAILED_STATUSES.has(status) : false;
  const progress = Math.max(0, Math.min(100, task?.progress ?? 0));

  return (
    <section className="classification-task" aria-live="polite">
      <strong>{failed ? "识别没有完成" : "正在识别表单"}</strong>
      {!failed ? (
        <>
          <p>{status === "SUCCEEDED" ? "识别完成，正在刷新工作台" : describeStep(task?.step)}</p>
          <progress max={100} value={progress} aria-label="识别进度" />
          <span>{progress}%</span>
          {requestError ? <p className="error-message">{requestError}，正在重试。</p> : null}
        </>
      ) : (
        <>
          <p>{task?.error || statusCopy.description}</p>
          <p>{statusCopy.nextAction}，并检查照片是否清晰完整。</p>
        </>
      )}
      <TraceDetails items={[
        { label: "任务 ID", value: taskId },
        { label: "任务状态代码", value: status ?? "PENDING" },
        { label: "任务步骤代码", value: task?.step ?? "无" },
      ]} />
    </section>
  );
}
