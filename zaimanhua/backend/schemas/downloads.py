from __future__ import annotations

from pydantic import BaseModel


class DownloadTaskItem(BaseModel):
    id: str
    title: str
    cover: str = ""
    status: str

    progress: float = 0.0
    message: str = ""
    total_chapters: int = 0
    done_chapters: int = 0
    failed_chapters: int = 0


class DownloadQueueResponse(BaseModel):
    active: list[DownloadTaskItem]
    waiting: list[DownloadTaskItem]


class AddDownloadRequest(BaseModel):
    id: str
    title: str | None = None
    cover: str | None = None
