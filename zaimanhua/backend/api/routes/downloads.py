from __future__ import annotations

from fastapi import APIRouter, Depends

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.common import OperationResponse
from zaimanhua.backend.schemas.downloads import AddDownloadRequest, DownloadQueueResponse

router = APIRouter()


@router.get("/downloads/queue", response_model=DownloadQueueResponse)
def get_download_queue(
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> DownloadQueueResponse:
    return container.download_service.get_queue()


@router.post("/downloads", response_model=OperationResponse)
def add_download_task(
    request: AddDownloadRequest,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> OperationResponse:
    return container.download_service.add_task(request)


@router.post("/downloads/{task_id}/cancel", response_model=OperationResponse)
def cancel_download_task(
    task_id: str,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> OperationResponse:
    return container.download_service.cancel_task(task_id)


@router.post("/downloads/stop-all", response_model=OperationResponse)
def stop_all_download_tasks(
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> OperationResponse:
    return container.download_service.stop_all()
