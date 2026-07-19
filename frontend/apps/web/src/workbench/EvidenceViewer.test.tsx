// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EvidenceItem, ReviewField } from "@form-detection/api-client";

import { EvidenceViewer } from "./EvidenceViewer";

function evidence(
  fileId: string,
  type: "ORIGINAL_IMAGE" | "CORRECTED_IMAGE" | "FIELD_CROP",
  relatedFieldId: string | null = null,
): EvidenceItem {
  return {
    file_id: fileId,
    type,
    related_field_id: relatedFieldId,
    sha256: `${fileId}-sha`,
    immutable: true,
    created_at: "2026-07-17T00:00:00Z",
    download_url: `/${fileId}.png`,
  };
}

function field(fieldId: string, x: number): ReviewField {
  return {
    field_id: fieldId,
    field_name: fieldId,
    display_name: fieldId,
    data_type: "text",
    recognition_engine: "manual",
    paper_entry_mode: "HANDWRITTEN_TEXT",
    recognition_mode: "NONE",
    fill_policy: "MANUAL_ONLY",
    requires_manual_confirmation: false,
    review_group: "WORKER",
    rules: null,
    source_region: { x, y: 20, width: 30, height: 40 },
    current_value: "",
    current_value_source: null,
    current_record_version: 0,
    candidates: [],
  };
}

afterEach(cleanup);

describe("EvidenceViewer", () => {
  it("switches only to evidence variants that exist", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <EvidenceViewer
        evidence={[evidence("original", "ORIGINAL_IMAGE"), evidence("corrected", "CORRECTED_IMAGE")]}
        fields={[]}
        selectedFieldId={null}
        onSelectField={() => undefined}
      />,
    );

    expect(screen.getByRole("img", { name: "校正后的表单" }).getAttribute("src")).toBe("/corrected.png");
    expect((screen.getByRole("button", { name: "原图" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "校正图" }) as HTMLButtonElement).disabled).toBe(false);
    await user.click(screen.getByRole("button", { name: "原图" }));
    expect(screen.getByRole("img", { name: "原始表单" }).getAttribute("src")).toBe("/original.png");

    rerender(
      <EvidenceViewer
        evidence={[evidence("corrected-only", "CORRECTED_IMAGE")]}
        fields={[]}
        selectedFieldId={null}
        onSelectField={() => undefined}
      />,
    );
    expect((screen.getByRole("button", { name: "原图" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("supports zoom, wheel zoom, rotation, reset and field-box visibility", async () => {
    const user = userEvent.setup();
    render(
      <EvidenceViewer
        evidence={[evidence("corrected", "CORRECTED_IMAGE")]}
        fields={[field("FIELD-1", 10)]}
        selectedFieldId="FIELD-1"
        onSelectField={() => undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "放大" }));
    expect(screen.getByText("125%")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "缩小" }));
    expect(screen.getByText("100%")).toBeTruthy();
    fireEvent.wheel(screen.getByLabelText("图片查看区域"), { deltaY: -100 });
    expect(screen.getByText("125%")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "顺时针旋转" }));
    expect(screen.getByTestId("evidence-transform").getAttribute("style")).toContain("rotate(90deg)");
    await user.click(screen.getByRole("button", { name: "复位视图" }));
    expect(screen.getByText("100%")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "隐藏字段框" }));
    expect(screen.queryByRole("button", { name: "定位字段 FIELD-1" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "显示字段框" }));
    expect(screen.getByRole("button", { name: "定位字段 FIELD-1" })).toBeTruthy();
  });

  it("selects, dims and hovers canonical field boxes using image coordinates", async () => {
    const user = userEvent.setup();
    const onSelectField = vi.fn();
    render(
      <EvidenceViewer
        evidence={[
          evidence("corrected", "CORRECTED_IMAGE"),
          evidence("selected-crop", "FIELD_CROP", "FIELD-1"),
        ]}
        fields={[field("FIELD-1", 10), field("FIELD-2", 50)]}
        selectedFieldId="FIELD-1"
        onSelectField={onSelectField}
      />,
    );
    const image = screen.getByRole("img", { name: "校正后的表单" });
    Object.defineProperty(image, "naturalWidth", { configurable: true, value: 100 });
    Object.defineProperty(image, "naturalHeight", { configurable: true, value: 200 });
    fireEvent.load(image);

    const selected = screen.getByRole("button", { name: "定位字段 FIELD-1" });
    const other = screen.getByRole("button", { name: "定位字段 FIELD-2" });
    expect(selected.className).toContain("selected");
    expect(other.className).toContain("dimmed");
    expect(selected.getAttribute("style")).toContain("left: 10%");
    expect(selected.getAttribute("style")).toContain("height: 20%");
    fireEvent.mouseEnter(other);
    expect(other.className).toContain("hovered");
    fireEvent.mouseLeave(other);
    expect(other.className).not.toContain("hovered");
    await user.click(other);
    expect(onSelectField).toHaveBeenCalledWith("FIELD-2");
    expect(screen.getByRole("img", { name: "当前字段裁片" }).getAttribute("src")).toBe("/selected-crop.png");
  });

  it("falls back to the original image without canonical boxes or a missing crop", () => {
    render(
      <EvidenceViewer
        evidence={[evidence("original", "ORIGINAL_IMAGE")]}
        fields={[field("FIELD-1", 10)]}
        selectedFieldId="FIELD-1"
        onSelectField={() => undefined}
      />,
    );

    expect(screen.getByRole("img", { name: "原始表单" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "定位字段 FIELD-1" })).toBeNull();
    expect(screen.getByText("原图没有模板坐标字段框")).toBeTruthy();
    expect(screen.getByText("该字段没有可用裁片")).toBeTruthy();
  });
});
