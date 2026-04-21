import asyncio
import logging
import os
import sys
import threading
import socket
import webview
import uvicorn
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from zaimanhua.core.runtime_warnings import configure_runtime_warnings
from zaimanhua.core.desktop_debug import (
    configure_desktop_debug,
    desktop_log,
    get_default_desktop_debug_path,
)
from zaimanhua.core.desktop_api import DesktopApi
from zaimanhua.core.desktop_runtime import stabilize_window_display, wait_for_tcp_port, wait_for_window_handle
from zaimanhua.core.desktop_runtime import build_webview_start_kwargs
from zaimanhua.core.frontend_bundle import resolve_frontend_file
from zaimanhua.core.windows_icon import apply_window_icon_from_file
from zaimanhua.core.windows_titlebar import (
    apply_window_titlebar_theme,
    sync_window_titlebar_if_needed,
    sync_window_titlebar_from_page,
)

configure_runtime_warnings()

# --- 路径与日志逻辑 ---
def get_app_root():
    if hasattr(sys, 'frozen'): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_bundle_dir():
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

APP_ROOT = get_app_root()
BUNDLE_DIR = get_bundle_dir()
os.environ.setdefault("ZAIMANHUA_ROOT", APP_ROOT)
os.environ.setdefault("ZAIMANHUA_DOWNLOAD_DIR", os.path.join(APP_ROOT, "downloads"))
os.environ.setdefault("ZAIMANHUA_CONFIG_PATH", os.path.join(APP_ROOT, "config.json"))
LOG_PATH = configure_desktop_debug(get_default_desktop_debug_path(APP_ROOT))


def configure_pywebview_logger(log_path: str | Path) -> None:
    logger = logging.getLogger("pywebview")
    logger.setLevel(logging.DEBUG)

    target = str(log_path)
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == target:
            return

    file_handler = logging.FileHandler(target, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("[pywebview] %(levelname)s %(message)s"))
    logger.addHandler(file_handler)


configure_pywebview_logger(LOG_PATH)

def log_debug(msg):
    desktop_log("desktop.message", "legacy", message=msg)

desktop_log(
    "desktop.lifecycle",
    "process_start",
    app_root=APP_ROOT,
    bundle_dir=BUNDLE_DIR,
    log_path=str(LOG_PATH),
)

for folder in ["downloads", "cache", "temp"]:
    os.makedirs(os.path.join(APP_ROOT, folder), exist_ok=True)
    desktop_log("desktop.fs", "ensure_dir", path=os.path.join(APP_ROOT, folder))

sys.path.append(BUNDLE_DIR)
from zaimanhua.backend.api.app import create_app
from zaimanhua.backend.app_services.settings_service import SettingsService

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def start_server(port, stop_event):
    frontend_dist_path = os.path.join(BUNDLE_DIR, "ui_web", "frontend", "dist")
    desktop_log(
        "desktop.server",
        "start_requested",
        port=port,
        frontend_dist_path=frontend_dist_path,
    )
    
    app = create_app()
    if os.path.exists(frontend_dist_path):
        desktop_log("desktop.server", "frontend_dist_found", path=frontend_dist_path)
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/"): return {"error": "Not Found"}
            resolved_path = resolve_frontend_file(frontend_dist_path, full_path)
            if resolved_path is None:
                return {"error": "Not Found"}
            return FileResponse(str(resolved_path))

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server_task = loop.create_task(server.serve())
    async def wait_for_stop():
        desktop_log("desktop.server", "started", port=port)
        while not stop_event.is_set(): await asyncio.sleep(0.5)
        server.should_exit = True
        await server_task
    loop.run_until_complete(wait_for_stop())
    loop.close()
    desktop_log("desktop.server", "stopped", port=port)

def main():
    port = get_free_port()
    stop_event = threading.Event()
    settings_service = SettingsService(config_path=os.environ["ZAIMANHUA_CONFIG_PATH"])
    initial_theme_mode = settings_service.get_theme_mode()
    initial_is_dark = initial_theme_mode == "dark"
    desktop_log("desktop.lifecycle", "main_enter", port=port)
    server_thread = threading.Thread(target=start_server, args=(port, stop_event), daemon=True)
    server_thread.start()
    try:
        wait_for_tcp_port("127.0.0.1", port, timeout_seconds=15.0)
        desktop_log("desktop.server", "ready", port=port)
    except Exception as e:
        stop_event.set()
        server_thread.join(timeout=2.0)
        desktop_log("desktop.server", "ready_wait_failed", port=port, error=str(e), error_type=type(e).__name__)
        raise
    
    api = DesktopApi(
        settings_service=settings_service,
        desktop_log_fn=desktop_log,
        wait_for_window_handle_fn=wait_for_window_handle,
        apply_window_titlebar_theme_fn=apply_window_titlebar_theme,
    )
    window = webview.create_window(
        "hugoの再漫画下载器", 
        f"http://127.0.0.1:{port}",
        js_api=api,
        width=1280, height=800, min_size=(1000, 700),
        focus=True,
        background_color="#0a0a0c" if initial_is_dark else "#ffffff",
    )
    desktop_log("desktop.window", "created", port=port, title="hugoの再漫画下载器")
    api._window = window

    def watch_titlebar_theme(hwnd, seed_is_dark: bool):
        failure_count = 0
        last_failure_signature = None
        is_dark = seed_is_dark
        loaded = window.events.loaded.wait(15)
        if not loaded:
            desktop_log(
                "desktop.titlebar",
                "initial_sync_wait_timeout",
                hwnd=hwnd,
                fallback_is_dark=seed_is_dark,
            )
        try:
            is_dark = sync_window_titlebar_from_page(
                window,
                hwnd,
                fallback_is_dark=is_dark,
            )
            desktop_log(
                "desktop.titlebar",
                "initial_synced",
                hwnd=hwnd,
                is_dark=is_dark,
            )
        except Exception as e:
            desktop_log(
                "desktop.titlebar",
                "initial_sync_failed",
                hwnd=hwnd,
                error=str(e),
                error_type=type(e).__name__,
            )
            is_dark = seed_is_dark

        while not stop_event.is_set():
            stop_event.wait(0.5)
            if stop_event.is_set():
                break
            try:
                next_is_dark = sync_window_titlebar_if_needed(
                    window,
                    hwnd,
                    previous_is_dark=is_dark,
                )
                if next_is_dark != is_dark:
                    desktop_log(
                        "desktop.titlebar",
                        "watcher_theme_changed",
                        hwnd=hwnd,
                        previous_is_dark=is_dark,
                        current_is_dark=next_is_dark,
                    )
                is_dark = next_is_dark
                failure_count = 0
                last_failure_signature = None
            except Exception as e:
                failure_count += 1
                failure_signature = f"{type(e).__name__}:{e}"
                if failure_signature != last_failure_signature or failure_count in {1, 5, 20, 50}:
                    desktop_log(
                        "desktop.titlebar",
                        "watcher_failed",
                        hwnd=hwnd,
                        error=str(e),
                        error_type=type(e).__name__,
                        failure_count=failure_count,
                    )
                last_failure_signature = failure_signature

    def on_shown():
        try:
            hwnd = stabilize_window_display(window, log_fn=desktop_log)
            desktop_log("desktop.window", "shown", hwnd=hwnd)

            apply_window_titlebar_theme(hwnd, initial_is_dark)
            desktop_log("desktop.titlebar", "seed_applied", hwnd=hwnd, is_dark=initial_is_dark)

            icon_candidates = [
                os.path.join(APP_ROOT, "app.ico"),
                os.path.join(APP_ROOT, "favicon.ico"),
                os.path.join(BUNDLE_DIR, "app.ico"),
                os.path.join(BUNDLE_DIR, "favicon.ico"),
            ]
            icon_path = next((path for path in icon_candidates if os.path.exists(path)), "")
            if os.path.exists(icon_path):
                icon_handle = apply_window_icon_from_file(hwnd, icon_path)
                desktop_log(
                    "desktop.window",
                    "icon_injected",
                    hwnd=hwnd,
                    icon_path=icon_path,
                    icon_handle=icon_handle,
                )

            threading.Thread(
                target=watch_titlebar_theme,
                args=(hwnd, initial_is_dark),
                daemon=True,
            ).start()
            
            desktop_log("desktop.window", "shown_polish_completed", hwnd=hwnd)
        except Exception as e:
            desktop_log("desktop.window", "shown_failed", error=str(e), error_type=type(e).__name__)

    start_kwargs = build_webview_start_kwargs(gui="winforms")
    desktop_log("desktop.webview", "start_requested", **start_kwargs)
    webview.start(on_shown, **start_kwargs)
    stop_event.set()
    server_thread.join(timeout=5.0)
    if server_thread.is_alive():
        desktop_log("desktop.server", "join_timeout", port=port)
    desktop_log("desktop.lifecycle", "webview_stopped")

if __name__ == "__main__":
    main()
