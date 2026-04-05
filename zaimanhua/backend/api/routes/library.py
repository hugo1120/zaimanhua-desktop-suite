from __future__ import annotations

from fastapi import APIRouter, Depends

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.library import (
    LibraryRepairResponse,
    LibraryResponse,
    LibrarySmartUpdateResponse,
)

router = APIRouter(tags=["library"])


@router.get("/library", response_model=LibraryResponse)
def list_library(
    keyword: str | None = None,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> LibraryResponse:
    return container.library_service.list_library(keyword=keyword)


@router.post("/library/refresh", response_model=LibraryResponse)
def refresh_library(
    keyword: str | None = None,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> LibraryResponse:
    return container.library_service.refresh_library(keyword=keyword)


@router.post("/library/repair", response_model=LibraryRepairResponse)
def repair_library(
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> LibraryRepairResponse:
    return container.library_service.repair_metadata()


@router.post("/library/smart-update", response_model=LibrarySmartUpdateResponse)
def smart_update_library(
    max_pages: int = 5,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> LibrarySmartUpdateResponse:
    return container.library_service.build_smart_update_candidates(max_pages=max_pages)
