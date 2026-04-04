import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { AppProviders } from "../../app/providers";
import { SearchPage } from "./search-page";
import * as searchApi from "../../lib/api/search";
import * as recentUpdatesApi from "../../lib/api/recent-updates";
import * as downloadsApi from "../../lib/api/downloads";

vi.mock("../../lib/api/search", () => ({
  searchManga: vi.fn(),
}));

vi.mock("../../lib/api/recent-updates", () => ({
  fetchRecentUpdates: vi.fn(),
}));

vi.mock("../../lib/api/downloads", () => ({
  addDownload: vi.fn(),
}));

describe("SearchPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("shows recent updates before search, hides them after search, and marks added item", async () => {
    const user = userEvent.setup();
    const search = vi.fn().mockResolvedValue({
      keyword: "abc",
      items: [{ id: "1", title: "Naruto", author: "Kishi", source: "local+api", status: "已完结", cover_url: "", description: "忍者故事" }],
    });
    const recent = vi.fn().mockResolvedValue({
      page: 1,
      items: [{ id: "2", title: "最近更新", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
    });
    const addTask = vi.fn().mockResolvedValue({ ok: true, message: "已加入下载队列" });

    (searchApi.searchManga as any).mockImplementation(search);
    (recentUpdatesApi.fetchRecentUpdates as any).mockImplementation(recent);
    (downloadsApi.addDownload as any).mockImplementation(addTask);

    render(
      <AppProviders>
        <SearchPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("最近更新")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("搜索作品名、作者或 ID..."), "abc");
    await user.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(screen.getByText("Naruto")).toBeInTheDocument();
    });
    expect(screen.queryByText("最近更新")).not.toBeInTheDocument();
    expect(screen.getByText("已完结")).toBeInTheDocument();
    expect(screen.getByText("搜索结果")).toBeInTheDocument();
    expect(screen.getByText("1 项")).toBeInTheDocument();
    expect(screen.getByText("abc")).toBeInTheDocument();

    const returnButton = screen.getByRole("button", { name: "返回推荐" });
    expect(returnButton).toBeInTheDocument();
    expect(returnButton.closest(".section-header__actions")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "下载" }));

    await waitFor(() => {
      expect(downloadsApi.addDownload).toHaveBeenCalledWith(expect.objectContaining({ id: "1", title: "Naruto" }));
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "已加入" })).toBeInTheDocument();
    });
  });
});
