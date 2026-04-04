import type { RecentUpdatesResponse } from "./contracts";
import { apiFetch } from "./http";

export function fetchRecentUpdates(page: number, refresh?: boolean) {
  const query = new URLSearchParams({ page: String(page) });
  if (refresh) {
    query.append("refresh", "true");
  }
  return apiFetch<RecentUpdatesResponse>(`/api/recent-updates?${query.toString()}`);
}
