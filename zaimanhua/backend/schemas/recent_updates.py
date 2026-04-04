from __future__ import annotations

from pydantic import BaseModel


class RecentUpdateItem(BaseModel):
    id: str
    title: str
    cover: str = ""
    author: str = ""
    status: str = ""
    latest: str = ""
    time: str = ""


class RecentUpdatesResponse(BaseModel):
    page: int
    items: list[RecentUpdateItem]
