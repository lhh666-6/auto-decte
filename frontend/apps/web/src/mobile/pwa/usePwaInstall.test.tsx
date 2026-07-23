// @vitest-environment jsdom

import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { usePwaInstall } from "./usePwaInstall";

function InstallProbe() {
  const install = usePwaInstall();
  return <button onClick={() => void install.install()}>{install.installed ? "已安装" : install.canInstall ? "可安装" : "不可安装"}</button>;
}

afterEach(cleanup);

it("opens the Android install prompt once and remembers acceptance", async () => {
  const prompt = vi.fn().mockResolvedValue(undefined);
  const event = new Event("beforeinstallprompt") as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: "accepted" }>;
  };
  event.prompt = prompt;
  event.userChoice = Promise.resolve({ outcome: "accepted" });

  render(<InstallProbe />);
  act(() => window.dispatchEvent(event));
  expect(screen.getByRole("button", { name: "可安装" })).toBeTruthy();

  await userEvent.setup().click(screen.getByRole("button", { name: "可安装" }));
  expect(prompt).toHaveBeenCalledTimes(1);
  expect(await screen.findByRole("button", { name: "已安装" })).toBeTruthy();
});
