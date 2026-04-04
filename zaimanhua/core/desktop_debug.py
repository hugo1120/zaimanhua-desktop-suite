from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


_lock = threading.RLock()
_session_id = uuid4().hex[:8]
_sequence = 0
_log_path: Path | None = None


def get_default_desktop_debug_path(app_root: str | Path) -> Path:
    return Path(app_root) / "desktop_debug.log"


def configure_desktop_debug(path_or_root: str | Path) -> Path:
    global _log_path, _sequence

    with _lock:
        path = Path(path_or_root)
        if path.name.lower().endswith(".log"):
            _log_path = path
        else:
            _log_path = path / "desktop_debug.log"
        _log_path.parent.mkdir(parents=True, exist_ok=True)
        _sequence = 0
        return _log_path


def _resolve_log_path() -> Path:
    if _log_path is None:
        fallback_root = os.getenv("TEMP") or os.getcwd()
        return configure_desktop_debug(Path(fallback_root) / "zaimanhua-desktop-suite")
    return _log_path


def _next_sequence() -> int:
    global _sequence
    _sequence += 1
    return _sequence


def _sanitize_segment(value: Any) -> str:
    return str(value).replace("\r", "\\r").replace("\n", "\\n").replace("]", ")")


def desktop_log(component: str, event: str, **details: Any) -> None:
    with _lock:
        try:
            log_path = _resolve_log_path()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            sequence = _next_sequence()
            thread_name = _sanitize_segment(threading.current_thread().name)
            payload = json.dumps(
                details,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            line = (
                f"[{timestamp}]"
                f"[session={_session_id}]"
                f"[seq={sequence:04d}]"
                f"[thread={thread_name}]"
                f"[component={_sanitize_segment(component)}]"
                f"[event={_sanitize_segment(event)}] {payload}"
            )
            with log_path.open("a", encoding="utf-8") as file_obj:
                file_obj.write(f"{line}\n")
        except Exception:
            return


def reset_desktop_debug_for_tests() -> None:
    global _log_path, _sequence
    with _lock:
        _log_path = None
        _sequence = 0
