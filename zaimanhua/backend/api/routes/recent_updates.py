from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.recent_updates import RecentUpdatesResponse
from zaimanhua.services.api import ApiAuthenticationError, ApiRequestError

router = APIRouter()


@router.get("/recent-updates", response_model=RecentUpdatesResponse)
def list_recent_updates(
    page: int = Query(1, ge=1),
    refresh: bool = Query(False),
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> RecentUpdatesResponse:
    try:
        return container.recent_updates_service.list_page(page, refresh=refresh)
    except ApiAuthenticationError as exc:
        container.auth_service.logout()
        raise HTTPException(status_code=401, detail=str(exc) or "登录已失效，请重新登录") from exc
    except ApiRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc) or "最近更新加载失败，请稍后重试") from exc
