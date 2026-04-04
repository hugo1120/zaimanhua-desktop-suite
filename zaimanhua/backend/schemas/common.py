from __future__ import annotations

from pydantic import BaseModel


class OperationResponse(BaseModel):
    ok: bool
    message: str
