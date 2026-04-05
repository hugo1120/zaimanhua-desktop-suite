from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from zaimanhua.backend.core.paths import get_project_root
from zaimanhua.backend.events.bus import EventBus
from zaimanhua.backend.schemas.crawler import CrawlerStatusResponse
from zaimanhua.backend.schemas.common import OperationResponse
from zaimanhua.core.desktop_debug import desktop_log


def _create_crawler(callback: Any, stop_event: threading.Event) -> Any:
    from zaimanhua.services.crawler import MangaCrawler

    return MangaCrawler(callback=callback, stop_event=stop_event)


class CrawlerService:
    def __init__(self, event_bus: EventBus, manga_list_file: str | None = None):
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_message = ""
        project_root = get_project_root()
        self._manga_list_file = Path(manga_list_file or project_root / "manga_list.txt")

    def _read_max_known_id(self) -> int:
        max_id = 0
        if not self._manga_list_file.exists():
            return 0
        try:
            with self._manga_list_file.open("r", encoding="utf-8") as file_obj:
                for line in file_obj:
                    prefix = line.split("|", 1)[0].strip()
                    if prefix.isdigit():
                        max_id = max(max_id, int(prefix))
        except OSError:
            return 0
        return max_id

    def _build_status(self, running: bool | None = None) -> CrawlerStatusResponse:
        return CrawlerStatusResponse(
            running=(bool(self._thread and self._thread.is_alive()) if running is None else running),
            last_message=self._last_message,
            max_known_id=self._read_max_known_id(),
        )

    def _publish_status(self, status: CrawlerStatusResponse | None = None) -> None:
        payload = (status or self._build_status()).model_dump()
        self._event_bus.publish({"type": "crawler.progress", "payload": payload})

    def get_status(self) -> CrawlerStatusResponse:
        with self._lock:
            return self._build_status()

    def start(self, start_id: int, end_id: int) -> CrawlerStatusResponse:
        if start_id > end_id:
            raise HTTPException(status_code=422, detail="起始 ID 不能大于结束 ID")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise HTTPException(status_code=409, detail="索引更新正在进行中")
            self._stop_event = threading.Event()
            self._last_message = f"启动 {start_id}-{end_id}"
            desktop_log("backend.crawler", "start_requested", start_id=start_id, end_id=end_id)
            crawler = _create_crawler(self._on_progress, self._stop_event)
            self._thread = threading.Thread(
                target=self._run_crawler, args=(crawler, start_id, end_id), daemon=True
            )
            self._thread.start()
            status = self._build_status(running=True)
        self._publish_status(status)
        return status

    def _on_progress(self, value: str | None) -> None:
        with self._lock:
            self._last_message = str(value or "")
        desktop_log("backend.crawler", "progress", message=self._last_message)
        self._publish_status()

    def _run_crawler(self, crawler: Any, start_id: int, end_id: int) -> None:
        startup_message = f"启动 {start_id}-{end_id}"
        try:
            crawler.run(start_id, end_id)
        except BaseException as exc:
            with self._lock:
                self._last_message = f"爬虫错误: {exc}"
            desktop_log(
                "backend.crawler",
                "run_failed",
                start_id=start_id,
                end_id=end_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        finally:
            with self._lock:
                if self._last_message == startup_message:
                    self._last_message = "索引任务已结束，但未收到任何进度回调"
                self._thread = None
                final_message = self._last_message
            desktop_log(
                "backend.crawler",
                "run_finished",
                start_id=start_id,
                end_id=end_id,
                message=final_message,
            )
            self._publish_status(self._build_status(running=False))

    def stop(self) -> OperationResponse:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return OperationResponse(ok=False, message="索引更新未在运行")
            self._stop_event.set()
            self._last_message = "已发送停止信号"
            status = self._build_status(running=True)
        self._publish_status(status)
        return OperationResponse(ok=True, message="已发送停止信号")

    def close(self) -> None:
        self.stop()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
