from __future__ import annotations

from collections.abc import Callable
from typing import Any


class DesktopApi:
    def __init__(
        self,
        *,
        settings_service: Any | None = None,
        desktop_log_fn: Callable[..., None],
        wait_for_window_handle_fn: Callable[..., int],
        apply_window_titlebar_theme_fn: Callable[[int, bool], None],
    ) -> None:
        self._settings_service = settings_service
        self._desktop_log_fn = desktop_log_fn
        self._wait_for_window_handle_fn = wait_for_window_handle_fn
        self._apply_window_titlebar_theme_fn = apply_window_titlebar_theme_fn
        self._window: Any | None = None

    def set_theme(self, is_dark: bool):
        self._desktop_log_fn("desktop.api", "set_theme_called", is_dark=is_dark)
        if self._settings_service is not None:
            theme_mode = self._settings_service.set_theme_mode("dark" if is_dark else "light")
            self._desktop_log_fn("desktop.api", "theme_mode_persisted", theme_mode=theme_mode)

        window = self._window
        if window and getattr(window, "native", None):
            try:
                hwnd = self._wait_for_window_handle_fn(window, timeout_seconds=2.0)
                self._desktop_log_fn("desktop.api", "set_theme_target", hwnd=hwnd, is_dark=is_dark)
                self._apply_window_titlebar_theme_fn(hwnd, is_dark)
                self._desktop_log_fn("desktop.api", "set_theme_applied", hwnd=hwnd, is_dark=is_dark)
            except Exception as exc:
                self._desktop_log_fn(
                    "desktop.api",
                    "set_theme_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

    def log_debug(self, component: str, event: str, payload=None):
        if isinstance(payload, dict):
            self._desktop_log_fn(component, event, **payload)
        else:
            self._desktop_log_fn(component, event, payload=payload)
