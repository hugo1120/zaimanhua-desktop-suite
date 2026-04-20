import { afterEach, describe, expect, test, vi } from "vitest";

import { useSessionStore } from "../../stores/session-store";
import { ApiError, apiFetch } from "./http";


describe("apiFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useSessionStore.getState().clear();
  });

  test("clears the local session store when backend returns 401", async () => {
    useSessionStore.getState().setSession({
      username: "hugo",
      loggedIn: true,
      rememberPassword: true,
      rememberedPassword: "secret",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "登录已失效，请重新登录" }), {
          status: 401,
          headers: {
            "Content-Type": "application/json",
          },
        }),
      ),
    );

    await expect(apiFetch("/api/recent-updates")).rejects.toMatchObject({
      status: 401,
      message: "登录已失效，请重新登录",
    });

    expect(useSessionStore.getState().loggedIn).toBe(false);
    expect(useSessionStore.getState().hydrated).toBe(true);
  });
});
