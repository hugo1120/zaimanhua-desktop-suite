import { describe, expect, test } from "vitest";

import { resolveApiUrl, resolveBackendOrigin, resolveWebSocketUrl } from "./backend-origin";

describe("backend origin helpers", () => {
  test("keeps relative API paths in browser dev mode without explicit backend origin", () => {
    expect(
      resolveApiUrl("/api/search", {
        protocol: "https:",
        origin: "https://app.local",
      }),
    ).toBe("/api/search");
  });

  test("falls back to local backend origin for file protocol", () => {
    expect(
      resolveBackendOrigin({
        protocol: "file:",
        origin: "null",
      }),
    ).toBe("http://127.0.0.1:8001");
  });

  test("builds absolute API url when backend origin is configured", () => {
    expect(
      resolveApiUrl(
        "/api/search",
        {
          protocol: "https:",
          origin: "https://app.local",
        },
        "http://127.0.0.1:9000/",
      ),
    ).toBe("http://127.0.0.1:9000/api/search");
  });

  test("builds websocket url from configured backend origin", () => {
    expect(
      resolveWebSocketUrl(
        "/ws/events",
        {
          protocol: "https:",
          origin: "https://app.local",
        },
        "http://127.0.0.1:9000/",
      ),
    ).toBe("ws://127.0.0.1:9000/ws/events");
  });
});
