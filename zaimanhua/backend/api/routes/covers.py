from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user

router = APIRouter()

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@router.get("/covers")
def serve_cover(
    path: str = Query(..., description="Relative path within downloads directory"),
    container: BackendContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> FileResponse:
    download_dir = getattr(container.library_service, "_download_dir", None)
    if not download_dir:
        raise HTTPException(status_code=500, detail="Download directory not configured")
    base = Path(download_dir).resolve()
    target = (base / path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Cover not found")
    media_type = _MEDIA_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(target, media_type=media_type)
