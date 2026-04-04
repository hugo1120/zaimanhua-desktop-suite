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
