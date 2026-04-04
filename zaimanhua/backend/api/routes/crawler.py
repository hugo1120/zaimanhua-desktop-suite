from __future__ import annotations

from fastapi import APIRouter, Depends

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.crawler import CrawlerStartRequest, CrawlerStatusResponse
from zaimanhua.backend.schemas.common import OperationResponse

router = APIRouter()


@router.get("/crawler/status", response_model=CrawlerStatusResponse)
def crawler_status(container: BackendContainer = Depends(get_container), user=Depends(get_current_user)) -> CrawlerStatusResponse:
    return container.crawler_service.get_status()


@router.post("/crawler/start", response_model=CrawlerStatusResponse)
def crawler_start(
    payload: CrawlerStartRequest,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> CrawlerStatusResponse:
    return container.crawler_service.start(payload.start_id, payload.end_id)


@router.post("/crawler/stop", response_model=OperationResponse)
def crawler_stop(container: BackendContainer = Depends(get_container), user=Depends(get_current_user)) -> OperationResponse:
    return container.crawler_service.stop()
