import type { MangaDetail } from "./contracts";
import { apiFetch } from "./http";

export function fetchMangaDetail(id: string) {
  return apiFetch<MangaDetail>(`/api/manga/${encodeURIComponent(id)}`);
}
