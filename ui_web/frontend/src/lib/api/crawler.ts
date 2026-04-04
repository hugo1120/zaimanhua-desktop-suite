import type { CrawlerStartRequest, CrawlerStatusResponse, OperationResponse } from "./contracts";
import { apiFetch } from "./http";

export function fetchCrawlerStatus() {
  return apiFetch<CrawlerStatusResponse>("/api/crawler/status");
}

export function startCrawler(request: CrawlerStartRequest) {
  return apiFetch<CrawlerStatusResponse>("/api/crawler/start", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function stopCrawler() {
  return apiFetch<OperationResponse>("/api/crawler/stop", {
    method: "POST",
  });
}
