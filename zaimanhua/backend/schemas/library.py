from __future__ import annotations

from pydantic import BaseModel


class LibraryItem(BaseModel):
    id: str
    title: str
    author: str = ""
    status: str = ""
    description: str = ""
    path: str
    cover_path: str = ""
    mtime: int = 0
    last_update_ts: int = 0
    last_update_text: str = ""
    latest_chapter: str = ""


class LibraryResponse(BaseModel):
    items: list[LibraryItem]
    total: int
    source: str


class LibraryRepairResponse(BaseModel):
    ok: bool
    message: str
    scanned: int = 0
    fixed: int = 0
    skipped: int = 0
