from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.recent_updates import RecentUpdatesResponse

router = APIRouter()


@router.get("/recent-updates", response_model=RecentUpdatesResponse)
def list_recent_updates(
    page: int = Query(1, ge=1),
    refresh: bool = Query(False),
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> RecentUpdatesResponse:
    return container.recent_updates_service.list_page(page, refresh=refresh)
