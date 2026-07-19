// @vitest-environment jsdom

import { cleanup, fireEvent, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReviewLease, WorkbenchDetail } from "@form-detection/api-client";

import { WorkbenchActionBar } from "./WorkbenchActionBar";
import { WorkbenchEmptyState, WorkbenchErrorNotice } from "./WorkbenchEmptyState";
import { useWorkbenchShortcuts } from "./useWorkbenchShortcuts";

function Harness({ hasLease = true, hasUnsavedEdits = true }: {
  hasLease?: boolean;
  hasUnsavedEdits?: boolean;
}) {
  useWorkbenchShortcuts({
    fieldIds: ["FIELD-1", "FIELD-2", "FIELD-3"],
    issueFieldIds: ["FIELD-1", "FIELD-3"],
    selectedFieldId: "FIELD-1",
    hasLease,
    hasUnsavedEdits,
    onAcceptCandidate: ACCEPT,
    onSelectField: SELECT,
    onSaveDraft: SAVE,
    onImageCommand: IMAGE_COMMAND,
  });

  return (
    <>
      <input aria-label="字段输入" />
      <textarea aria-label="多行原因" />
      <select aria-label="选择项"><option>一</option></select>
      <div data-workbench-image-context tabIndex={0}>图片区域</div>
      <button type="button">普通按钮</button>
    </>
  );
}

const ACCEPT = vi.fn();
const SELECT = vi.fn();
const SAVE = vi.fn();
const IMAGE_COMMAND = vi.fn();

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("useWorkbenchShortcuts", () => {
  it("accepts the current candidate with Enter and selects the next issue", () => {
    const { getByLabelText } = render(<Harness />);

    fireEvent.keyDown(getByLabelText("字段输入"), { key: "Enter" });

    expect(ACCEPT).toHaveBeenCalledTimes(1);
    expect(SELECT).toHaveBeenCalledWith("FIELD-3");
  });

  it("does not accept while editing a textarea, using a select or composing text", () => {
    const { getByLabelText } = render(<Harness />);

    fireEvent.keyDown(getByLabelText("多行原因"), { key: "Enter" });
    fireEvent.keyDown(getByLabelText("选择项"), { key: "Enter" });
    fireEvent.keyDown(getByLabelText("字段输入"), { key: "Enter", isComposing: true });

    expect(ACCEPT).not.toHaveBeenCalled();
  });

  it("moves field selection with Tab without cancelling browser focus", () => {
    const { getByLabelText } = render(<Harness />);

    const next = fireEvent.keyDown(getByLabelText("字段输入"), { key: "Tab" });
    expect(next).toBe(true);
    expect(SELECT).toHaveBeenLastCalledWith("FIELD-2");

    const previous = fireEvent.keyDown(getByLabelText("字段输入"), { key: "Tab", shiftKey: true });
    expect(previous).toBe(true);
    expect(SELECT).toHaveBeenLastCalledWith("FIELD-3");
  });

  it("saves with Ctrl+S only when a lease and unsaved edits exist", () => {
    const first = render(<Harness />);
    const saved = fireEvent.keyDown(first.getByLabelText("字段输入"), { key: "s", ctrlKey: true });
    expect(saved).toBe(false);
    expect(SAVE).toHaveBeenCalledTimes(1);
    first.unmount();

    const second = render(<Harness hasLease={false} />);
    expect(fireEvent.keyDown(second.getByLabelText("字段输入"), { key: "s", ctrlKey: true })).toBe(true);
    expect(SAVE).toHaveBeenCalledTimes(1);
  });

  it("runs image shortcuts only from the image viewer context", () => {
    const { getByText, getByRole } = render(<Harness />);
    const image = getByText("图片区域");

    fireEvent.keyDown(image, { key: "+" });
    fireEvent.keyDown(image, { key: "-" });
    fireEvent.keyDown(image, { key: "0" });
    fireEvent.keyDown(image, { key: "r" });
    expect(IMAGE_COMMAND.mock.calls.map(([command]) => command)).toEqual([
      "zoom-in", "zoom-out", "reset", "rotate",
    ]);

    fireEvent.keyDown(getByRole("button", { name: "普通按钮" }), { key: "+" });
    expect(IMAGE_COMMAND).toHaveBeenCalledTimes(4);
  });
});

describe("workbench empty and error states", () => {
  it.each([
    ["classification", "没有待确认类型的表单"],
    ["review", "没有待审核的表单"],
    ["exceptions", "没有待重新拍照的表单"],
  ] as const)("shows the dedicated %s empty state without an empty grid", (queue, heading) => {
    const { getByRole, queryByTestId } = render(
      <WorkbenchEmptyState queue={queue} onUpload={vi.fn()} onFind={vi.fn()} />,
    );

    expect(getByRole("heading", { name: heading })).toBeTruthy();
    expect(getByRole("button", { name: "上传表单照片" })).toBeTruthy();
    expect(getByRole("button", { name: "查找表单" })).toBeTruthy();
    expect(queryByTestId("review-workbench-grid")).toBeNull();
  });

  it("turns a technical request error into guidance and keeps its code in trace details", async () => {
    const user = userEvent.setup();
    const { getByText, queryByText } = render(
      <WorkbenchErrorNotice error="LEASE_CONFLICT：审核锁已被其他人获取" />,
    );

    expect(getByText("操作没有完成")).toBeTruthy();
    expect(getByText(/正在由其他工作人员审核/)).toBeTruthy();
    expect(getByText(/请刷新状态后重试/)).toBeTruthy();
    expect(queryByText("LEASE_CONFLICT")).toBeNull();
    await user.click(getByText("追溯详情"));
    expect(getByText("LEASE_CONFLICT")).toBeTruthy();
  });
});

const LEASE = {
  form_id: "FORM-1",
  owner_id: "reviewer",
  lease_token: "lease",
  expires_at: "2099-01-01T00:00:00Z",
} satisfies ReviewLease;

function actionDetail(status: string, version: number): WorkbenchDetail {
  return {
    form: { review_status: status, current_record_version: version },
  } as unknown as WorkbenchDetail;
}

function renderActions(detail: WorkbenchDetail | null, isCorrection = false) {
  return render(
    <WorkbenchActionBar
      detail={detail}
      lease={LEASE}
      loading={false}
      hasUnsavedEdits
      warningCount={0}
      isCorrection={isCorrection}
      selectedQueue="review"
      onReturn={vi.fn()}
      onVoid={vi.fn()}
      onSaveDraft={vi.fn()}
      onPrimary={vi.fn()}
    />,
  );
}

describe("WorkbenchActionBar", () => {
  it("does not leave irrelevant disabled review actions on an empty workbench", () => {
    const { queryByRole } = renderActions(null);
    expect(queryByRole("contentinfo")).toBeNull();
  });

  it("shows the review actions for a form waiting for review", () => {
    const { getByRole } = renderActions(actionDetail("NEEDS_REVIEW", 0));
    expect(getByRole("button", { name: "退回" })).toBeTruthy();
    expect(getByRole("button", { name: "作废" })).toBeTruthy();
    expect(getByRole("button", { name: "保存草稿" })).toBeTruthy();
    expect(getByRole("button", { name: "确认并下一张" })).toBeTruthy();
  });

  it("uses the correction action language after confirmation", () => {
    const { getByRole, queryByRole } = renderActions(actionDetail("CONFIRMED", 1), true);
    expect(getByRole("button", { name: "保存本次修改" })).toBeTruthy();
    expect(queryByRole("button", { name: "确认并下一张" })).toBeNull();
  });

  it.each(["NEEDS_CLASSIFICATION", "RECAPTURE_REQUIRED"])("hides review actions for %s", (status) => {
    const { queryByRole } = renderActions(actionDetail(status, 0));
    expect(queryByRole("contentinfo")).toBeNull();
  });
});
