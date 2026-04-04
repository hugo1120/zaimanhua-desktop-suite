import type { SettingsResponse, SettingsUpdateRequest } from "./contracts";
import { apiFetch } from "./http";

export function fetchSettings() {
  return apiFetch<SettingsResponse>("/api/settings");
}

export function updateSettings(request: SettingsUpdateRequest) {
  return apiFetch<SettingsResponse>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(request),
  });
}
