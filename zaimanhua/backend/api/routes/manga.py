from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.manga import MangaDetailResponse

router = APIRouter()


@router.get("/manga/{manga_id}", response_model=MangaDetailResponse)
def get_manga_detail(
    manga_id: str,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> MangaDetailResponse:
    detail = container.api_client.get_manga_detail(str(manga_id)) or {}
    if detail.get("errno") != 0:
        raise HTTPException(status_code=404, detail="漫画详情不存在")

    data = detail.get("data", {}).get("data", {})
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="漫画详情不存在")

    authors = data.get("authors", [])
    if isinstance(authors, list):
        author = ",".join(str(item.get("tag_name", "")) for item in authors if isinstance(item, dict))
    else:
        author = str(authors or "")

    status = ""
    if hasattr(container.api_client, "get_status_label"):
        status = str(container.api_client.get_status_label(data.get("status", [])) or "")

    return MangaDetailResponse(
        id=str(manga_id),
        title=str(data.get("title") or ""),
        description=str(data.get("description") or ""),
        author=author,
        status=status,
        cover_url=str(data.get("cover") or ""),
    )
