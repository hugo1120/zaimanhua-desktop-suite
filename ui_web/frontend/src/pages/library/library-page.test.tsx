import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { AppProviders } from "../../app/providers";
import { queryClient } from "../../app/query-client";
import { LibraryPage } from "./library-page";
import * as libraryApi from "../../lib/api/library";
import * as downloadsApi from "../../lib/api/downloads";

vi.mock("../../lib/api/library", () => ({
  fetchLibrary: vi.fn(),
  refreshLibrary: vi.fn(),
  repairLibraryMetadata: vi.fn(),
  openLibraryFolder: vi.fn(),
}));

vi.mock("../../lib/api/downloads", () => ({
  addDownload: vi.fn(),
}));

import * as mangaApi from "../../lib/api/manga";

vi.mock("../../lib/api/manga", () => ({
  fetchMangaDetail: vi.fn(),
}));

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("LibraryPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("filters library items, refreshes library and can add download", async () => {
    const user = userEvent.setup();
    const listLibraryApi = vi.fn().mockResolvedValue({
      items: [
        {
          id: "42",
          title: "[A] Demo Manga",
          path: "D:/downloads/Demo Manga",
          author: "作者甲",
          status: "连载中",
          description: "",
          cover_path: "",
          mtime: 1000,
        },
        {
          id: "44",
          title: "2021：无限命运",
          path: "D:/downloads/2021",
          author: "作者丙",
          status: "连载中",
          description: "",
          cover_path: "",
          mtime: 2000,
        },
      ],
      total: 2,
      source: "cache",
    });
    const refreshLibraryApi = vi.fn().mockResolvedValue({
      items: [
        {
          id: "43",
          title: "Another Demo",
          path: "D:/downloads/Another Demo",
          author: "作者乙",
          status: "已完结",
          description: "",
          cover_path: "cover.jpg",
          mtime: 3000,
        },
      ],
      total: 1,
      source: "scan",
    });
    const addDownloadApi = vi.fn().mockResolvedValue({
      ok: true,
      message: "已加入下载队列",
    });
    const repairMetadataApi = vi.fn().mockResolvedValue({
      ok: true,
      message: "已补全 1 个目录",
      scanned: 1,
      fixed: 1,
      skipped: 0,
    });
    const fetchMangaDetailApi = vi.fn().mockResolvedValue({
      id: "42",
      title: "[A] Demo Manga",
      description: "Demo Description",
      author: "作者甲",
      status: "连载中",
      cover_url: "",
    });

    (libraryApi.fetchLibrary as any).mockImplementation(listLibraryApi);
    (libraryApi.refreshLibrary as any).mockImplementation(refreshLibraryApi);
    (libraryApi.repairLibraryMetadata as any).mockImplementation(repairMetadataApi);
    (downloadsApi.addDownload as any).mockImplementation(addDownloadApi);
    (mangaApi.fetchMangaDetail as any).mockImplementation(fetchMangaDetailApi);

    render(
      <AppProviders>
        <LibraryPage />
      </AppProviders>,
    );

    // 由于 React Query 会在第一次渲染就执行，可能需要等待 initial render
    await waitFor(() => {
      expect(libraryApi.fetchLibrary).toHaveBeenCalled();
    });

    // 实际上 MangaDescriptionHover 显示的是 text
    expect(await screen.findByText("[A] Demo Manga", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "0-9" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("搜索库中作品..."), "demo");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(libraryApi.fetchLibrary).toHaveBeenLastCalledWith("demo");
    });

    await user.click(screen.getByRole("button", { name: "刷新" }));

    await waitFor(() => {
      expect(screen.getByText("Another Demo")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "更新" }));

    await waitFor(() => {
      expect(downloadsApi.addDownload).toHaveBeenCalledWith(expect.objectContaining({ id: "43", title: "Another Demo" }));
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "已加入" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "补全" }));

    await waitFor(() => {
      expect(libraryApi.repairLibraryMetadata).toHaveBeenCalled();
    });

    // 验证更新全部按钮
    expect(screen.getByRole("button", { name: /^更新全部/ })).toBeInTheDocument();
  });

  test("sorts library by real update time before local mtime fallback", async () => {
    const libraryPayload = {
      items: [
        {
          id: "1",
          title: "旧目录新漫画",
          path: "D:/downloads/old-folder",
          author: "作者甲",
          status: "连载中",
          description: "",
          cover_path: "",
          mtime: 100,
          last_update_ts: 300,
          last_update_text: "2024-01-03 00:00",
          latest_chapter: "第3话",
        },
        {
          id: "2",
          title: "新目录旧漫画",
          path: "D:/downloads/new-folder",
          author: "作者乙",
          status: "连载中",
          description: "",
          cover_path: "",
          mtime: 200,
          last_update_ts: 0,
          last_update_text: "",
          latest_chapter: "",
        },
      ],
      total: 2,
      source: "scan",
    };

    (libraryApi.fetchLibrary as any).mockResolvedValue(libraryPayload);
    (libraryApi.refreshLibrary as any).mockResolvedValue(libraryPayload);
    (libraryApi.repairLibraryMetadata as any).mockResolvedValue({
      ok: true,
      message: "已补全 0 个目录",
      scanned: 0,
      fixed: 0,
      skipped: 0,
    });
    (downloadsApi.addDownload as any).mockResolvedValue({ ok: true, message: "已加入下载队列" });
    (mangaApi.fetchMangaDetail as any).mockResolvedValue({
      id: "1",
      title: "旧目录新漫画",
      description: "",
      author: "作者甲",
      status: "连载中",
      cover_url: "",
    });

    render(
      <AppProviders>
        <LibraryPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("旧目录新漫画")).toBeInTheDocument();
      expect(screen.getByText("新目录旧漫画")).toBeInTheDocument();
    });

    const first = screen.getByText("旧目录新漫画");
    const second = screen.getByText("新目录旧漫画");
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test("单本更新遇到重复任务时不标记为已加入", async () => {
    const user = userEvent.setup();
    const libraryPayload = {
      items: [
        {
          id: "101",
          title: "重复任务漫画",
          path: "D:/downloads/duplicate-task",
          author: "作者甲",
          status: "连载中",
          description: "",
          cover_path: "cover.jpg",
          mtime: 100,
        },
      ],
      total: 1,
      source: "scan",
    };

    (libraryApi.fetchLibrary as any).mockResolvedValue(libraryPayload);
    (libraryApi.refreshLibrary as any).mockResolvedValue(libraryPayload);
    (libraryApi.repairLibraryMetadata as any).mockResolvedValue({
      ok: true,
      message: "已补全 0 个目录",
      scanned: 0,
      fixed: 0,
      skipped: 0,
    });
    (downloadsApi.addDownload as any).mockResolvedValue({
      ok: false,
      message: "任务已在队列中",
    });
    (mangaApi.fetchMangaDetail as any).mockResolvedValue({
      id: "101",
      title: "重复任务漫画",
      description: "",
      author: "作者甲",
      status: "连载中",
      cover_url: "",
    });

    render(
      <AppProviders>
        <LibraryPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("重复任务漫画")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "更新" }));

    await waitFor(() => {
      expect(downloadsApi.addDownload).toHaveBeenCalledWith(expect.objectContaining({ id: "101" }));
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "已加入" })).not.toBeInTheDocument();
    });
  });

  test("批量更新全部按统计结果展示新增、重复与失败数量", async () => {
    const user = userEvent.setup();
    const libraryItems = Array.from({ length: 25 }, (_, index) => ({
      id: String(index + 1),
      title: `测试漫画 ${index + 1}`,
      path: `D:/downloads/test-${index + 1}`,
      author: `作者 ${index + 1}`,
      status: "连载中",
      description: "",
      cover_path: `cover-${index + 1}.jpg`,
      mtime: index + 1,
    }));

    (libraryApi.fetchLibrary as any).mockResolvedValue({
      items: libraryItems,
      total: libraryItems.length,
      source: "scan",
    });
    (libraryApi.refreshLibrary as any).mockResolvedValue({
      items: libraryItems,
      total: libraryItems.length,
      source: "scan",
    });
    (libraryApi.repairLibraryMetadata as any).mockResolvedValue({
      ok: true,
      message: "已补全 0 个目录",
      scanned: 0,
      fixed: 0,
      skipped: 0,
    });
    (mangaApi.fetchMangaDetail as any).mockResolvedValue({
      id: "1",
      title: "测试漫画 1",
      description: "",
      author: "作者 1",
      status: "连载中",
      cover_url: "",
    });

    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");
    const firstBatchDeferred = Array.from({ length: 20 }, () => createDeferred<{ ok: boolean; message: string }>());

    (downloadsApi.addDownload as any).mockImplementation((_request: { id: string }) => {
      const numericId = Number(_request.id);
      if (numericId <= 20) {
        return firstBatchDeferred[numericId - 1].promise;
      }
      if (numericId === 21) {
        return Promise.resolve({ ok: true, message: "已加入下载队列" });
      }
      if (numericId === 22) {
        return Promise.resolve({ ok: false, message: "任务已在队列中" });
      }
      if (numericId === 23) {
        return Promise.reject(new Error("network error"));
      }
      return Promise.resolve({ ok: true, message: "已加入下载队列" });
    });

    render(
      <AppProviders>
        <LibraryPage />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("测试漫画 1")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /^更新全部/ }));

    await waitFor(() => {
      expect(downloadsApi.addDownload).toHaveBeenCalledTimes(20);
    });

    expect(screen.getByRole("button", { name: "刷新" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "补全" })).toBeDisabled();
    expect(screen.getByText("正在加入下载队列：0 / 25")).toBeInTheDocument();

    firstBatchDeferred[0].resolve({ ok: true, message: "已加入下载队列" });
    firstBatchDeferred[1].resolve({ ok: false, message: "任务已在队列中" });
    firstBatchDeferred[2].reject(new Error("network error"));
    for (let index = 3; index < firstBatchDeferred.length; index += 1) {
      firstBatchDeferred[index].resolve({ ok: true, message: "已加入下载队列" });
    }

    await waitFor(() => {
      expect(screen.getByText("正在加入下载队列：20 / 25")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(downloadsApi.addDownload).toHaveBeenCalledTimes(25);
    });

    await waitFor(() => {
      expect(screen.getByText("已处理 25 本：新增 23，本地已存在 1，失败 1")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "已加入" })).toHaveLength(23);
    });

    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ["downloads", "queue"] });
  });
});
