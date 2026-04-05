import type {
  LibraryRepairResponse,
  LibraryResponse,
  LibrarySmartUpdateResponse,
  OperationResponse,
} from "./contracts";
import { apiFetch } from "./http";

export function fetchLibrary(keyword = "") {
  const query = new URLSearchParams();
  if (keyword.trim()) {
    query.set("keyword", keyword.trim());
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<LibraryResponse>(`/api/library${suffix}`);
}

export function refreshLibrary(keyword = "") {
  const query = new URLSearchParams();
  if (keyword.trim()) {
    query.set("keyword", keyword.trim());
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<LibraryResponse>(`/api/library/refresh${suffix}`, {
    method: "POST",
  });
}

export function smartUpdateLibrary() {
  return apiFetch<LibrarySmartUpdateResponse>("/api/library/smart-update", {
    method: "POST",
  });
}

export function openLibraryFolder(path: string) {
  return apiFetch<OperationResponse>("/api/library/open-folder", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function repairLibraryMetadata() {
  return apiFetch<LibraryRepairResponse>("/api/library/repair", {
    method: "POST",
  });
}
