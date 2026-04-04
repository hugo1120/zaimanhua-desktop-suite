from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.search import SearchResponse

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=422, detail="q 不能为空白")
    return container.search_service.search(q)
