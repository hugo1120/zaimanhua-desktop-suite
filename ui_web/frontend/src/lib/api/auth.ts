import type { LoginRequest, OperationResponse, SessionResponse } from "./contracts";
import { emitDesktopLog } from "../desktop-debug";
import { apiFetch } from "./http";

export async function fetchSession() {
  emitDesktopLog("frontend.auth", "fetch_session_request");
  try {
    const response = await apiFetch<SessionResponse>("/api/auth/session");
    emitDesktopLog("frontend.auth", "fetch_session_response", {
      username: response.username,
      loggedIn: response.logged_in,
    });
    return response;
  } catch (error) {
    emitDesktopLog("frontend.auth", "fetch_session_error", {
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

export async function login(request: LoginRequest) {
  emitDesktopLog("frontend.auth", "login_request", {
    username: request.username,
  });
  try {
    const response = await apiFetch<SessionResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(request),
    });
    emitDesktopLog("frontend.auth", "login_response", {
      username: response.username,
      loggedIn: response.logged_in,
    });
    return response;
  } catch (error) {
    emitDesktopLog("frontend.auth", "login_error", {
      username: request.username,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

export async function logout() {
  emitDesktopLog("frontend.auth", "logout_request");
  try {
    const response = await apiFetch<OperationResponse>("/api/auth/logout", {
      method: "POST",
    });
    emitDesktopLog("frontend.auth", "logout_response", {
      ok: response.ok,
      message: response.message,
    });
    return response;
  } catch (error) {
    emitDesktopLog("frontend.auth", "logout_error", {
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}
