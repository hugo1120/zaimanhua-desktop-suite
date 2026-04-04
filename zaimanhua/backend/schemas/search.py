from __future__ import annotations

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: str
    title: str
    author: str = ""
    source: str = ""
    status: str = ""
    cover_url: str = ""
    description: str = ""


class SearchResponse(BaseModel):
    keyword: str
    items: list[SearchResultItem]
