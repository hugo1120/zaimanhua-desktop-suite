from __future__ import annotations

from typing import Any

from zaimanhua.backend.events.bus import EventBus
from zaimanhua.backend.schemas.common import OperationResponse
from zaimanhua.backend.schemas.downloads import AddDownloadRequest, DownloadQueueResponse, DownloadTaskItem


_EVENT_NAME_MAP = {
    "task_added": "download.task_added",
    "progress": "download.task_updated",
    "task_finish": "download.task_finished",
    "task_error": "download.task_failed",
    "task_canceled": "download.task_canceled",
    "queue_changed": "queue.changed",
    "stop_all": "download.stop_all",
}


def _build_stop_all_message(summary: dict[str, int]) -> str:
    waiting_canceled = int(summary.get("waiting_canceled", 0) or 0)
    active_stopping = int(summary.get("active_stopping", 0) or 0)

    if waiting_canceled == 0 and active_stopping == 0:
        return "当前没有可停止的下载任务"
    if waiting_canceled > 0 and active_stopping > 0:
        return f"已取消 {waiting_canceled} 个排队任务，并向 {active_stopping} 个活跃任务发出停止请求"
    if waiting_canceled > 0:
        return f"已取消 {waiting_canceled} 个排队任务"
    return f"已向 {active_stopping} 个活跃任务发出停止请求"


def _create_download_manager(api: Any, callback, download_dir: str | None = None):
    from zaimanhua.services.downloads import DownloadManager

    return DownloadManager(api, callback, download_dir=download_dir)


class DownloadService:
    def __init__(self, api: Any, settings_service: Any, event_bus: EventBus):
        self._api = api
        self._settings_service = settings_service
        self._event_bus = event_bus
        download_dir = getattr(settings_service, "get_download_dir", lambda: None)()
        self._manager = _create_download_manager(api, self._on_manager_event, download_dir=download_dir)
        settings = self._settings_service.get_settings()
        self.apply_settings(settings)

    @staticmethod
    def _to_task_item(task: Any) -> DownloadTaskItem:
        return DownloadTaskItem(
            id=str(getattr(task, "id", "") or ""),
            title=str(getattr(task, "title", "") or ""),
            cover=str(getattr(task, "cover", "") or ""),
            status=str(getattr(task, "status", "") or ""),
            progress=float(getattr(task, "progress", 0.0) or 0.0),
            message=str(getattr(task, "message", "") or ""),
            total_chapters=int(getattr(task, "total_chapters", 0) or 0),
            done_chapters=int(getattr(task, "done_chapters", 0) or 0),
            failed_chapters=int(getattr(task, "failed_chapters", 0) or 0),
        )

    def _serialize_event_payload(self, payload: Any) -> Any:
        if payload is None:
            return None
        if hasattr(payload, "id"):
            return self._to_task_item(payload).model_dump()
        return payload

    def _on_manager_event(self, event_name: str, payload: Any) -> None:
        normalized_name = _EVENT_NAME_MAP.get(str(event_name), str(event_name))
        self._event_bus.publish(
            {
                "type": normalized_name,
                "payload": self._serialize_event_payload(payload),
            }
        )

    def get_queue(self) -> DownloadQueueResponse:
        active: list[DownloadTaskItem] = []
        waiting: list[DownloadTaskItem] = []
        for task in self._manager.get_all_tasks():
            item = self._to_task_item(task)
            if item.status == "waiting":
                waiting.append(item)
            else:
                active.append(item)
        return DownloadQueueResponse(active=active, waiting=waiting)

    def add_task(self, request: AddDownloadRequest) -> OperationResponse:
        ok = bool(self._manager.add_task(str(request.id), request.title, cover=request.cover or ""))
        if ok:
            return OperationResponse(ok=True, message="已加入下载队列")
        return OperationResponse(ok=False, message="任务已在队列中")

    def cancel_task(self, task_id: str) -> OperationResponse:
        task = self._manager.get_task(str(task_id))
        if task is None:
            return OperationResponse(ok=False, message="任务不存在")
        ok = bool(self._manager.cancel_task(task))
        if ok:
            return OperationResponse(ok=True, message="已取消任务")
        return OperationResponse(ok=False, message="取消任务失败")

    def stop_all(self) -> OperationResponse:
        summary = self._manager.stop_all_tasks() or {"waiting_canceled": 0, "active_stopping": 0}
        return OperationResponse(ok=True, message=_build_stop_all_message(summary))

    def apply_settings(self, settings: Any) -> None:
        self._manager.set_concurrency(int(settings.max_books), int(settings.max_images))

    def set_download_dir(self, download_dir: str) -> None:
        if hasattr(self._manager, "set_download_dir"):
            self._manager.set_download_dir(download_dir)

    def close(self) -> None:
        if hasattr(self._manager, "close"):
            self._manager.close()
