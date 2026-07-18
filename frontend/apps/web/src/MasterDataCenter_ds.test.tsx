// @vitest-environment jsdom

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MasterDataApi } from "@form-detection/api-client";

import { MasterDataCenter } from "./MasterDataCenter_ds";

afterEach(cleanup);

function api(items: unknown[] = []) {
  return {
    list: vi.fn().mockResolvedValue(items),
    audits: vi.fn().mockResolvedValue([]),
  } as unknown as MasterDataApi;
}

describe("MasterDataCenter", () => {
  it("opens the catalog from the URL and exposes four compact business tabs", async () => {
    const user = userEvent.setup();
    const client = api();
    const onCatalogChange = vi.fn();
    render(<MasterDataCenter api={client} initialCatalog="products" onCatalogChange={onCatalogChange} />);

    const tabs = within(screen.getByRole("navigation", { name: "主数据类型" }));
    for (const name of ["员工", "工单", "产品", "工序"]) {
      expect(tabs.getByRole("button", { name })).toBeTruthy();
    }
    expect(tabs.getByRole("button", { name: "产品" }).className).toContain("active");
    expect(client.list).toHaveBeenCalledWith("products", expect.anything());
    expect(client.list).not.toHaveBeenCalledWith("employees", expect.anything());

    await user.click(tabs.getByRole("button", { name: "工序" }));
    expect(onCatalogChange).toHaveBeenCalledWith("processes");
  });

  it("distinguishes an empty directory from a search with no results", async () => {
    const user = userEvent.setup();
    render(<MasterDataCenter api={api()} initialCatalog="employees" />);
    expect(await screen.findByText("员工目录为空")).toBeTruthy();

    await user.type(screen.getByLabelText("搜索主数据"), "E001");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(await screen.findByText("没有找到匹配的员工")).toBeTruthy();
  });

  it("uses business fields instead of a raw JSON editor", async () => {
    const user = userEvent.setup();
    render(<MasterDataCenter api={api()} initialCatalog="products" />);
    await user.click(screen.getByRole("button", { name: "新增产品" }));

    for (const label of ["产品编码", "产品名称", "规格型号", "计量单位", "更多信息", "变更原因"]) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.queryByLabelText(/扩展属性.*JSON/)).toBeNull();
  });
});
