export interface StopAllSummaryPayload {
  waiting_canceled?: number;
  active_stopping?: number;
}

export const DOWNLOAD_QUEUE_REFRESH_DELAY_MS = 150;

export function isStopAllSummaryPayload(payload: unknown): payload is StopAllSummaryPayload {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  return "waiting_canceled" in payload || "active_stopping" in payload;
}

export function formatStopAllSummaryMessage(payload: StopAllSummaryPayload) {
  const waitingCanceled = Math.max(0, Number(payload.waiting_canceled ?? 0));
  const activeStopping = Math.max(0, Number(payload.active_stopping ?? 0));

  if (waitingCanceled === 0 && activeStopping === 0) {
    return "当前没有可停止的下载任务";
  }
  if (waitingCanceled > 0 && activeStopping > 0) {
    return `已取消 ${waitingCanceled} 个排队任务，并向 ${activeStopping} 个活跃任务发出停止请求`;
  }
  if (waitingCanceled > 0) {
    return `已取消 ${waitingCanceled} 个排队任务`;
  }
  return `已向 ${activeStopping} 个活跃任务发出停止请求`;
}

export function createQueueRefreshScheduler(
  callback: () => void,
  delayMs = DOWNLOAD_QUEUE_REFRESH_DELAY_MS,
) {
  let timer: number | null = null;

  return {
    schedule() {
      if (timer !== null) {
        return;
      }

      timer = window.setTimeout(() => {
        timer = null;
        callback();
      }, delayMs);
    },
    cancel() {
      if (timer === null) {
        return;
      }

      window.clearTimeout(timer);
      timer = null;
    },
  };
}
