import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { AppProviders } from "../../app/providers";
import { ApiError } from "../../lib/api/http";
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

  test("shows recent update error when discovery feed request fails", async () => {
    (recentUpdatesApi.fetchRecentUpdates as any).mockRejectedValue(
      new ApiError(502, "最近更新加载失败，请稍后重试", {
        detail: "最近更新加载失败，请稍后重试",
      }),
    );

    render(
      <AppProviders>
        <SearchPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("最近更新加载失败，请稍后重试")).toBeInTheDocument();
    });
  });

  test("skips a duplicate-only discovery page and continues paging", async () => {
    const callbacks: IntersectionObserverCallback[] = [];
    const originalObserver = window.IntersectionObserver;

    class TriggerableIntersectionObserver {
      callback: IntersectionObserverCallback;

      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback;
        callbacks.push(callback);
      }

      observe() {}
      unobserve() {}
      disconnect() {}
    }

    Object.defineProperty(window, "IntersectionObserver", {
      writable: true,
      value: TriggerableIntersectionObserver,
    });

    (recentUpdatesApi.fetchRecentUpdates as any)
      .mockResolvedValueOnce({
        page: 1,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 2,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 3,
        items: [{ id: "3", title: "最近更新-第三页", cover: "", author: "B", status: "连载中", latest: "第2话", time: "今天" }],
      });

    try {
      render(
        <AppProviders>
          <SearchPage />
        </AppProviders>,
      );

      await waitFor(() => {
        expect(screen.getByText("最近更新-第一页")).toBeInTheDocument();
      });

      act(() => {
        callbacks[callbacks.length - 1]?.(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      await waitFor(() => {
        expect(recentUpdatesApi.fetchRecentUpdates).toHaveBeenCalledTimes(3);
      });

      await waitFor(() => {
        expect(screen.getByText("最近更新-第三页")).toBeInTheDocument();
      });

      expect(screen.queryByText("没有更多了")).not.toBeInTheDocument();
    } finally {
      Object.defineProperty(window, "IntersectionObserver", {
        writable: true,
        value: originalObserver,
      });
    }
  });

  test("stops paging after multiple duplicate-only discovery pages", async () => {
    const callbacks: IntersectionObserverCallback[] = [];
    const originalObserver = window.IntersectionObserver;

    class TriggerableIntersectionObserver {
      callback: IntersectionObserverCallback;

      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback;
        callbacks.push(callback);
      }

      observe() {}
      unobserve() {}
      disconnect() {}
    }

    Object.defineProperty(window, "IntersectionObserver", {
      writable: true,
      value: TriggerableIntersectionObserver,
    });

    (recentUpdatesApi.fetchRecentUpdates as any)
      .mockResolvedValueOnce({
        page: 1,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 2,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 3,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 4,
        items: [{ id: "2", title: "最近更新-第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      });

    try {
      render(
        <AppProviders>
          <SearchPage />
        </AppProviders>,
      );

      await waitFor(() => {
        expect(screen.getByText("最近更新-第一页")).toBeInTheDocument();
      });

      act(() => {
        callbacks[callbacks.length - 1]?.(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      await waitFor(() => {
        expect(recentUpdatesApi.fetchRecentUpdates).toHaveBeenCalledTimes(4);
      });

      await waitFor(() => {
        expect(screen.getByText("没有更多了")).toBeInTheDocument();
      });
    } finally {
      Object.defineProperty(window, "IntersectionObserver", {
        writable: true,
        value: originalObserver,
      });
    }
  });
});
