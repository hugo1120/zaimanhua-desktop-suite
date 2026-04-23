from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user
from zaimanhua.backend.schemas.settings import SettingsResponse, SettingsUpdateRequest

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
def get_settings(container: BackendContainer = Depends(get_container), user=Depends(get_current_user)) -> SettingsResponse:
    return container.settings_service.get_settings()


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    request: SettingsUpdateRequest,
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> SettingsResponse:
    settings = container.settings_service.update_settings(request)
    if hasattr(container.download_service, "apply_settings"):
        container.download_service.apply_settings(settings)
    # Update library service download dir if changed
    new_dir = Path(settings.download_dir)
    if hasattr(container.library_service, "_download_dir"):
        container.library_service._download_dir = new_dir
    if hasattr(container.download_service, "set_download_dir"):
        container.download_service.set_download_dir(str(new_dir))
    return settings
