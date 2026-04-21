import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";

import { AppProviders } from "../../app/providers";
import { queryClient } from "../../app/query-client";
import type { BackendEvent, DownloadQueueResponse, DownloadTaskItem, OperationResponse } from "../../lib/api/contracts";
import * as downloadsApi from "../../lib/api/downloads";
import * as eventsApi from "../../lib/ws/events";
import { useDownloadsStore } from "../../stores/downloads-store";
import { DownloadsPage } from "./downloads-page";

vi.mock("../../lib/api/downloads", () => ({
  fetchDownloadQueue: vi.fn(),
  cancelDownload: vi.fn(),
  stopAllDownloads: vi.fn(),
}));

vi.mock("../../lib/ws/events", () => ({
  connectEvents: vi.fn(),
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

function createTask(overrides: Partial<DownloadTaskItem> = {}): DownloadTaskItem {
  return {
    id: overrides.id ?? "task-1",
    title: overrides.title ?? "测试漫画",
    cover: overrides.cover ?? "",
    status: overrides.status ?? "downloading",
    progress: overrides.progress ?? 0.5,
    message: overrides.message ?? "下载中",
    total_chapters: overrides.total_chapters ?? 10,
    done_chapters: overrides.done_chapters ?? 5,
    failed_chapters: overrides.failed_chapters ?? 0,
  };
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

function renderPage() {
  return render(
    <AppProviders>
      <DownloadsPage />
    </AppProviders>,
  );
}

describe("DownloadsPage", () => {
  let emitEvent: ((event: BackendEvent) => void) | undefined;
  let emitReconnect: (() => void) | undefined;

  beforeEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
    queryClient.clear();
    useDownloadsStore.setState((state) => ({
      ...state,
      active: [],
      waiting: [],
    }));

    emitEvent = undefined;
    emitReconnect = undefined;

    (eventsApi.connectEvents as any).mockImplementation((onEvent: (event: BackendEvent) => void, options?: { onReconnect?(): void }) => {
      emitEvent = onEvent;
      emitReconnect = options?.onReconnect;
      return { close: () => undefined };
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("页面初始能渲染 active 和 waiting 队列", async () => {
    const queuePayload: DownloadQueueResponse = {
      active: [createTask({ id: "active-1", title: "活跃任务" })],
      waiting: [createTask({ id: "waiting-1", title: "排队任务", status: "waiting", message: "等待中" })],
    };

    (downloadsApi.fetchDownloadQueue as any).mockResolvedValue(queuePayload);
    (downloadsApi.stopAllDownloads as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);
    (downloadsApi.cancelDownload as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("活跃中 (1)")).toBeInTheDocument();
      expect(screen.getByText("等待队列 (1)")).toBeInTheDocument();
    });

    expect(screen.getByText("活跃任务")).toBeInTheDocument();
    expect(screen.getByText("排队任务")).toBeInTheDocument();
  });

  test("点击停止全部后按钮立即 disabled，并在成功后显示反馈文案", async () => {
    const user = userEvent.setup();
    const stopAllDeferred = createDeferred<OperationResponse>();

    (downloadsApi.fetchDownloadQueue as any).mockResolvedValue({
      active: [createTask({ id: "active-1", title: "活跃任务" })],
      waiting: [createTask({ id: "waiting-1", title: "排队任务", status: "waiting", message: "等待中" })],
    } satisfies DownloadQueueResponse);
    (downloadsApi.stopAllDownloads as any).mockImplementation(() => stopAllDeferred.promise);
    (downloadsApi.cancelDownload as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);

    renderPage();

    const stopAllButton = await screen.findByRole("button", { name: "停止全部" });
    await waitFor(() => {
      expect(stopAllButton).toBeEnabled();
    });

    await user.click(stopAllButton);

    expect(stopAllButton).toBeDisabled();

    stopAllDeferred.resolve({
      ok: true,
      message: "已取消 1 个排队任务，并向 1 个活跃任务发出停止请求",
    });

    await waitFor(() => {
      expect(screen.getByText("已取消 1 个排队任务，并向 1 个活跃任务发出停止请求")).toBeInTheDocument();
    });
  });

  test("queue.changed 与 download.stop_all 会合并成一次补拉", async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    (downloadsApi.fetchDownloadQueue as any).mockResolvedValue({
      active: [createTask({ id: "active-1" })],
      waiting: [],
    } satisfies DownloadQueueResponse);
    (downloadsApi.stopAllDownloads as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);
    (downloadsApi.cancelDownload as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);

    renderPage();

    await waitFor(() => {
      expect(downloadsApi.fetchDownloadQueue).toHaveBeenCalledTimes(1);
    });

    emitEvent?.({ type: "queue.changed", payload: null });
    emitEvent?.({ type: "download.stop_all", payload: { waiting_canceled: 1, active_stopping: 1 } });

    expect(invalidateQueriesSpy).not.toHaveBeenCalled();

    await sleep(180);
    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledTimes(1);
    });
  });

  test("download.stop_all 的 summary payload 能转成页面 feedback", async () => {
    (downloadsApi.fetchDownloadQueue as any).mockResolvedValue({
      active: [createTask({ id: "active-1" })],
      waiting: [],
    } satisfies DownloadQueueResponse);
    (downloadsApi.stopAllDownloads as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);
    (downloadsApi.cancelDownload as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);

    renderPage();

    await waitFor(() => {
      expect(downloadsApi.fetchDownloadQueue).toHaveBeenCalledTimes(1);
    });

    emitEvent?.({
      type: "download.stop_all",
      payload: { waiting_canceled: 1, active_stopping: 1 },
    });

    await waitFor(() => {
      expect(screen.getByText("已取消 1 个排队任务，并向 1 个活跃任务发出停止请求")).toBeInTheDocument();
    });
  });

  test("重连后会走 150ms 合并补拉", async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    (downloadsApi.fetchDownloadQueue as any).mockResolvedValue({
      active: [createTask({ id: "active-1" })],
      waiting: [],
    } satisfies DownloadQueueResponse);
    (downloadsApi.stopAllDownloads as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);
    (downloadsApi.cancelDownload as any).mockResolvedValue({ ok: true, message: "noop" } satisfies OperationResponse);

    renderPage();

    await waitFor(() => {
      expect(downloadsApi.fetchDownloadQueue).toHaveBeenCalledTimes(1);
    });

    emitReconnect?.();

    expect(invalidateQueriesSpy).not.toHaveBeenCalled();

    await sleep(170);
    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledTimes(1);
    });
  });
});
