from __future__ import annotations

from pydantic import BaseModel


class MangaDetailResponse(BaseModel):
    id: str
    title: str
    description: str = ""
    author: str = ""
    status: str = ""
    cover_url: str = ""
