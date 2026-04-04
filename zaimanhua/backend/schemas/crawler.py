from __future__ import annotations

from pydantic import BaseModel, Field


class CrawlerStatusResponse(BaseModel):
    running: bool
    last_message: str = ""
    max_known_id: int = 0


class CrawlerStartRequest(BaseModel):
    start_id: int = Field(..., ge=1)
    end_id: int = Field(..., ge=1)
