from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    username: str = ""
    has_token: bool = False
    max_books: int = 1
    max_images: int = 5
    download_dir: str = ""


class SettingsUpdateRequest(BaseModel):
    max_books: int = Field(..., ge=1, le=10)
    max_images: int = Field(..., ge=1, le=32)
    download_dir: str | None = None
