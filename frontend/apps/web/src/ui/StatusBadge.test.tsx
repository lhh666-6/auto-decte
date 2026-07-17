// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";

afterEach(cleanup);

describe("StatusBadge", () => {
  it.each([
    ["success", "已确认", "成功"],
    ["warning", "待重新拍照", "需要注意"],
    ["danger", "识别失败", "失败"],
    ["neutral", "等待处理", "一般"],
  ] as const)("renders %s with text and explicit semantic meaning", (tone, label, meaning) => {
    render(<StatusBadge tone={tone}>{label}</StatusBadge>);

    const badge = screen.getByRole("status", { name: `${label}，${meaning}状态` });
    expect(badge.textContent).toContain(label);
    expect(badge.getAttribute("data-tone")).toBe(tone);
    expect(screen.getByText(`${meaning}状态`)).toBeTruthy();
  });
});
