import { useEffect } from "react";
import { Navigate, Outlet, createBrowserRouter, useLocation } from "react-router-dom";

import { emitDesktopLog } from "../lib/desktop-debug";
import { WebShell } from "../layouts/web-shell";
import { DownloadsPage } from "../pages/downloads/downloads-page";
import { LibraryPage } from "../pages/library/library-page";
import { LoginPage } from "../pages/login/login-page";
import { SearchPage } from "../pages/search/search-page";
import { SettingsPage } from "../pages/settings/settings-page";
import { useSessionStore } from "../stores/session-store";

function RequireSession() {
  const location = useLocation();
  const hydrated = useSessionStore((state) => state.hydrated);
  const loggedIn = useSessionStore((state) => state.loggedIn);

  useEffect(() => {
    emitDesktopLog("frontend.router", "require_session_state", {
      hydrated,
      loggedIn,
      pathname: location.pathname,
    });
  }, [hydrated, loggedIn, location.pathname]);

  if (!hydrated) {
    return <div className="app-loading">正在恢复会话…</div>;
  }

  if (!loggedIn) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}

function LoginGate() {
  const location = useLocation();
  const hydrated = useSessionStore((state) => state.hydrated);
  const loggedIn = useSessionStore((state) => state.loggedIn);

  useEffect(() => {
    emitDesktopLog("frontend.router", "login_gate_state", {
      hydrated,
      loggedIn,
      pathname: location.pathname,
    });
  }, [hydrated, loggedIn, location.pathname]);

  if (!hydrated) {
    return <div className="app-loading">正在恢复会话…</div>;
  }

  if (loggedIn) {
    return <Navigate to="/search" replace />;
  }

  return <LoginPage />;
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginGate />,
  },
  {
    path: "/",
    element: <RequireSession />,
    children: [
      {
        element: <WebShell />,
        children: [
          { index: true, element: <Navigate to="/search" replace /> },
          {
            path: "search",
            element: <SearchPage />,
          },
          {
            path: "recent-updates",
            element: <Navigate to="/search" replace />,
          },
          {
            path: "downloads",
            element: <DownloadsPage />,
          },
          {
            path: "library",
            element: <LibraryPage />,
          },
          {
            path: "settings",
            element: <SettingsPage />,
          },
        ],
      },
    ],
  },
]);
