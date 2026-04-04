import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { AppProviders } from "../../app/providers";
import type { BackendEvent } from "../../lib/api/contracts";
import { SettingsPage } from "./settings-page";
import * as settingsApi from "../../lib/api/settings";
import * as crawlerApi from "../../lib/api/crawler";
import * as eventsApi from "../../lib/ws/events";

vi.mock("../../lib/api/settings", () => ({
  fetchSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock("../../lib/api/crawler", () => ({
  fetchCrawlerStatus: vi.fn(),
  startCrawler: vi.fn(),
  stopCrawler: vi.fn(),
}));

vi.mock("../../lib/ws/events", () => ({
  connectEvents: vi.fn(),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("updates concurrency and reacts to crawler progress", async () => {
    const user = userEvent.setup();
    const fetchSettingsApi = vi.fn().mockResolvedValue({
      username: "hugo",
      has_token: true,
      max_books: 2,
      max_images: 8,
    });
    const updateSettingsApi = vi.fn().mockResolvedValue({
      username: "hugo",
      has_token: true,
      max_books: 4,
      max_images: 12,
    });
    const getCrawlerStatusApi = vi.fn().mockResolvedValue({
      running: false,
      last_message: "",
      max_known_id: 1234,
    });
    const startCrawlerApi = vi.fn().mockResolvedValue({
      running: true,
      last_message: "启动 1200-1234",
      max_known_id: 1234,
    });
    const stopCrawlerApi = vi.fn().mockResolvedValue({
      ok: true,
      message: "已停止索引更新",
    });

    (settingsApi.fetchSettings as any).mockImplementation(fetchSettingsApi);
    (settingsApi.updateSettings as any).mockImplementation(updateSettingsApi);
    (crawlerApi.fetchCrawlerStatus as any).mockImplementation(getCrawlerStatusApi);
    (crawlerApi.startCrawler as any).mockImplementation(startCrawlerApi);
    (crawlerApi.stopCrawler as any).mockImplementation(stopCrawlerApi);

    let emitProgress: ((event: BackendEvent) => void) | undefined;

    (eventsApi.connectEvents as any).mockImplementation((onEvent: any) => {
      emitProgress = onEvent;
      return { close: () => undefined };
    });

    render(
      <AppProviders>
        <SettingsPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("2")).toBeInTheDocument();
      expect(screen.getByDisplayValue("8")).toBeInTheDocument();
    });

    // Testing Library 不能直接支持查找 aria-label 不规范的定制组件，换种方式或直接查 value
    const numInputs = screen.getAllByRole("textbox").filter(el => el.getAttribute("inputmode") === "decimal");
    // 假设 numInputs[0] = books, numInputs[1] = images
    if (numInputs.length >= 2) {
      await user.clear(numInputs[1]);
      await user.type(numInputs[1], "12");
      await user.clear(numInputs[0]);
      await user.type(numInputs[0], "4");
    } else {
      // Fallback
      await user.clear(screen.getByLabelText("单本并行图片数"));
      await user.type(screen.getByLabelText("单本并行图片数"), "12");
      await user.clear(screen.getByLabelText("并行下载书籍数"));
      await user.type(screen.getByLabelText("并行下载书籍数"), "4");
    }
    
    await user.click(screen.getByRole("button", { name: "保存通用设置" }));

    await waitFor(() => {
      expect(settingsApi.updateSettings).toHaveBeenCalledWith(expect.objectContaining({ max_books: 4, max_images: 12 }));
    });

    await user.clear(screen.getByLabelText("起始 ID"));
    await user.type(screen.getByLabelText("起始 ID"), "1200");
    await user.click(screen.getByRole("button", { name: "启动索引更新" }));

    await waitFor(() => {
      expect(crawlerApi.startCrawler).toHaveBeenCalledWith(expect.objectContaining({ start_id: 1200 }));
    });

    emitProgress?.({
      type: "crawler.progress",
      payload: {
        running: true,
        last_message: "进度: 10/100",
        max_known_id: 1234,
      },
    });

    await waitFor(() => {
      expect(screen.getByText("进度: 10/100")).toBeInTheDocument();
    });
  });
});
