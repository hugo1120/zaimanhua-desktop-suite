import type { SearchResponse } from "./contracts";
import { apiFetch } from "./http";

export function searchManga(keyword: string) {
  const query = new URLSearchParams({ q: keyword });
  return apiFetch<SearchResponse>(`/api/search?${query.toString()}`);
}
