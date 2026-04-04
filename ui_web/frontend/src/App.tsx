import { useEffect, useRef } from "react";
import { RouterProvider } from "react-router-dom";
import { useComputedColorScheme } from "@mantine/core";

import { AppProviders } from "./app/providers";
import { router } from "./app/router";
import { fetchSession } from "./lib/api/auth";
import { emitDesktopLog } from "./lib/desktop-debug";
import { useSessionStore } from "./stores/session-store";

function ThemeSync() {
  const computedColorScheme = useComputedColorScheme("dark", { getInitialValueInEffect: false });
  const lastSent = useRef<string | null>(null);
  const inFlight = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    let attempts = 0;
    const maxAttempts = 15;

    emitDesktopLog("frontend.theme", "effect_mount", {
      computedColorScheme,
    });

    const sync = () => {
      // @ts-ignore
      const api = window.pywebview?.api;
      if (!api || !api.set_theme) {
        return false;
      }

      if (lastSent.current === computedColorScheme) {
        return true;
      }

      if (inFlight.current === computedColorScheme) {
        return false;
      }

      inFlight.current = computedColorScheme;
      emitDesktopLog("frontend.theme", "set_theme_start", {
        computedColorScheme,
        attempt: attempts,
      });
      try {
        void Promise.resolve(api.set_theme(computedColorScheme === "dark"))
          .then(() => {
            if (!active) {
              return;
            }
            lastSent.current = computedColorScheme;
            emitDesktopLog("frontend.theme", "set_theme_success", {
              computedColorScheme,
            });
          })
          .catch((error: unknown) => {
            emitDesktopLog("frontend.theme", "set_theme_failed", {
              computedColorScheme,
              error: error instanceof Error ? error.message : String(error),
            });
          })
          .finally(() => {
            if (inFlight.current === computedColorScheme) {
              inFlight.current = null;
            }
          });
      } catch (error) {
        inFlight.current = null;
        emitDesktopLog("frontend.theme", "set_theme_failed", {
          computedColorScheme,
          error: error instanceof Error ? error.message : String(error),
        });
      }

      return false;
    };

    const interval = setInterval(() => {
      attempts += 1;
      if (sync() || attempts >= maxAttempts) {
        clearInterval(interval);
      }
    }, 1000);

    const handlePywebviewReady = () => {
      attempts = 0;
      emitDesktopLog("frontend.theme", "pywebviewready", {
        computedColorScheme,
      });
      sync();
    };

    window.addEventListener("pywebviewready", handlePywebviewReady);
    sync();

    return () => {
      active = false;
      inFlight.current = null;
      emitDesktopLog("frontend.theme", "effect_cleanup", {
        computedColorScheme,
      });
      window.removeEventListener("pywebviewready", handlePywebviewReady);
      clearInterval(interval);
    };
  }, [computedColorScheme]);

  return null;
}


function SessionBootstrap() {
  const setSession = useSessionStore((state) => state.setSession);
  const markHydrated = useSessionStore((state) => state.markHydrated);

  useEffect(() => {
    let active = true;
    emitDesktopLog("frontend.session", "bootstrap_start");

    void fetchSession()
      .then((session) => {
        if (!active) {
          return;
        }
        emitDesktopLog("frontend.session", "bootstrap_success", {
          username: session.username,
          loggedIn: session.logged_in,
          rememberPassword: session.remember_password,
        });
        setSession({
          username: session.username,
          loggedIn: session.logged_in,
          rememberPassword: session.remember_password,
          rememberedPassword: session.remembered_password,
        });
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        emitDesktopLog("frontend.session", "bootstrap_failed", {
          error: error instanceof Error ? error.message : String(error),
        });
        markHydrated();
      });

    return () => {
      active = false;
      emitDesktopLog("frontend.session", "bootstrap_cleanup");
    };
  }, [markHydrated, setSession]);

  return <RouterProvider router={router} />;
}

export default function App() {
  return (
    <AppProviders>
      <ThemeSync />
      <SessionBootstrap />
    </AppProviders>
  );
}
