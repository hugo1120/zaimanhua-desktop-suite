import type { AddDownloadRequest, DownloadQueueResponse, OperationResponse } from "./contracts";
import { apiFetch } from "./http";

export function fetchDownloadQueue() {
  return apiFetch<DownloadQueueResponse>("/api/downloads/queue");
}

export function addDownload(request: AddDownloadRequest) {
  return apiFetch<OperationResponse>("/api/downloads", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function cancelDownload(taskId: string) {
  return apiFetch<OperationResponse>(`/api/downloads/${taskId}/cancel`, {
    method: "POST",
  });
}

export function stopAllDownloads() {
  return apiFetch<OperationResponse>("/api/downloads/stop-all", {
    method: "POST",
  });
}
