const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8001";

function readConfiguredBackendOrigin() {
  if (typeof __ZAIMANHUA_BACKEND_ORIGIN__ === "string" && __ZAIMANHUA_BACKEND_ORIGIN__.trim()) {
    return __ZAIMANHUA_BACKEND_ORIGIN__;
  }

  return undefined;
}

export function resolveBackendOrigin(
  location: Pick<Location, "protocol" | "origin"> = window.location,
  configuredOrigin = readConfiguredBackendOrigin(),
) {
  const envOrigin = configuredOrigin?.trim();
  if (envOrigin) {
    return envOrigin.replace(/\/+$/, "");
  }

  if (location.protocol === "http:" || location.protocol === "https:") {
    return location.origin.replace(/\/+$/, "");
  }

  return DEFAULT_BACKEND_ORIGIN;
}

export function resolveApiUrl(
  input: string,
  location: Pick<Location, "protocol" | "origin"> = window.location,
  configuredOrigin = readConfiguredBackendOrigin(),
) {
  if (!input.startsWith("/")) {
    return input;
  }

  if (!configuredOrigin?.trim() && (location.protocol === "http:" || location.protocol === "https:")) {
    return input;
  }

  return new URL(input, `${resolveBackendOrigin(location, configuredOrigin)}/`).toString();
}

export function resolveWebSocketUrl(
  path = "/ws/events",
  location: Pick<Location, "protocol" | "origin"> = window.location,
  configuredOrigin = readConfiguredBackendOrigin(),
) {
  const url = new URL(path, `${resolveBackendOrigin(location, configuredOrigin)}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
