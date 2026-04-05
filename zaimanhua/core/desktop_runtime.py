from __future__ import annotations

import socket
import time
from typing import Any, Callable


def wait_for_tcp_port(
    host: str,
    port: int,
    *,
    timeout_seconds: float = 15.0,
    poll_interval: float = 0.05,
    connect_fn: Callable[[str, int], bool] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    interval = max(float(poll_interval), 0.01)
    deadline = time.monotonic() + max(float(timeout_seconds), interval)
    last_error: Exception | None = None

    if connect_fn is None:
        def _default_connect(target_host: str, target_port: int) -> bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(interval)
                return client.connect_ex((target_host, int(target_port))) == 0

        connect_fn = _default_connect

    while time.monotonic() < deadline:
        try:
            if connect_fn(host, int(port)):
                return True
        except OSError as exc:
            last_error = exc
        sleep_fn(interval)

    raise TimeoutError(f"Timed out waiting for tcp://{host}:{port}") from last_error


def wait_for_window_handle(
    window: Any,
    *,
    timeout_seconds: float = 10.0,
    poll_interval: float = 0.05,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    interval = max(float(poll_interval), 0.01)
    deadline = time.monotonic() + max(float(timeout_seconds), interval)
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            native = getattr(window, "native", None)
            if native is None:
                raise RuntimeError("window.native is not ready")
            handle = getattr(native, "Handle", None)
            if handle is None:
                raise RuntimeError("window handle is not ready")
            to_int64 = getattr(handle, "ToInt64", None)
            hwnd = int(to_int64() if callable(to_int64) else handle)
            if hwnd:
                return hwnd
        except Exception as exc:
            last_error = exc
        sleep_fn(interval)

    raise TimeoutError("Timed out waiting for native window handle") from last_error


def build_webview_start_kwargs(
    *,
    gui: str = "winforms",
    storage_path: str | None = None,
) -> dict[str, Any]:
    # 显式传 storage_path 会触发 pywebview 的 CoreWebView2Environment.CreateAsync
    # 路径，在当前应用场景下会稳定导致 WebView2 初始化失败；这里统一回退到
    # pywebview 默认存储策略。
    return {"gui": gui}


def activate_window(hwnd: int, *, user32: Any = None) -> None:
    if not hwnd:
        raise ValueError("hwnd is required")

    if user32 is None:
        import ctypes

        user32 = ctypes.windll.user32

    sw_restore = 9
    hwnd_topmost = -1
    hwnd_notopmost = -2
    swp_nomove_nosize = 0x0001 | 0x0002

    user32.ShowWindow(hwnd, sw_restore)
    user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_nomove_nosize)
    user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, swp_nomove_nosize)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)


def stabilize_window_display(
    window: Any,
    *,
    wait_for_handle_fn: Callable[..., int] = wait_for_window_handle,
    activate_fn: Callable[[int], None] = activate_window,
    log_fn: Callable[..., None] | None = None,
    handle_timeout_seconds: float = 10.0,
    shown_timeout_seconds: float = 5.0,
) -> int:
    def _log(event: str, **details: Any) -> None:
        if log_fn is not None:
            log_fn("desktop.window", event, **details)

    _log("stabilizer_start")

    before_show = getattr(getattr(window, "events", None), "before_show", None)
    if before_show is not None and hasattr(before_show, "wait"):
        if not before_show.wait(handle_timeout_seconds):
            _log("before_show_wait_timeout", timeout_seconds=handle_timeout_seconds)

    native = getattr(window, "native", None)
    if native is not None and hasattr(native, "show"):
        try:
            native.show()
            _log("show_invoked")
        except Exception as exc:
            _log("show_invoke_failed", error=str(exc), error_type=type(exc).__name__)

    hwnd = wait_for_handle_fn(window, timeout_seconds=handle_timeout_seconds)
    _log("handle_ready", hwnd=hwnd)

    shown = getattr(getattr(window, "events", None), "shown", None)
    if shown is not None and hasattr(shown, "wait"):
        if not shown.wait(shown_timeout_seconds):
            _log("shown_wait_timeout", hwnd=hwnd, timeout_seconds=shown_timeout_seconds)
            native = getattr(window, "native", None)
            if native is not None and hasattr(native, "show"):
                try:
                    native.show()
                    _log("show_reinvoked", hwnd=hwnd)
                except Exception as exc:
                    _log("show_reinvoke_failed", hwnd=hwnd, error=str(exc), error_type=type(exc).__name__)

    try:
        window.on_top = True
        _log("topmost_applied", hwnd=hwnd)
    except Exception as exc:
        _log("topmost_apply_failed", hwnd=hwnd, error=str(exc), error_type=type(exc).__name__)

    activate_fn(hwnd)
    _log("foreground_applied", hwnd=hwnd)

    try:
        window.on_top = False
        _log("topmost_released", hwnd=hwnd)
    except Exception as exc:
        _log("topmost_release_failed", hwnd=hwnd, error=str(exc), error_type=type(exc).__name__)

    return hwnd
