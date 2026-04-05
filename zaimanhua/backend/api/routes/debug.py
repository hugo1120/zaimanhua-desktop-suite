from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from zaimanhua.core.desktop_debug import desktop_log
from zaimanhua.backend.schemas.common import OperationResponse

router = APIRouter(tags=["debug"])


class FrontendDebugRequest(BaseModel):
    message: str = ""
    source: str = "frontend"
    details: dict[str, str] = {}


@router.post("/debug/frontend-error", response_model=OperationResponse)
def frontend_error(payload: FrontendDebugRequest) -> OperationResponse:
    desktop_log(
        "frontend.bootstrap",
        "client_error",
        source=payload.source,
        message=payload.message,
        details=payload.details,
    )
    return OperationResponse(ok=True, message="logged")
