from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from zaimanhua.backend.api.dependencies import BackendContainer, get_container, get_current_user


router = APIRouter()


class OpenFolderRequest(BaseModel):
    path: str


@router.post("/library/open-folder")
def open_folder(request: OpenFolderRequest, container: BackendContainer = Depends(get_container), user=Depends(get_current_user)) -> dict:
    try:
        target_path = Path(request.path).resolve()
        base_dir = container.library_service._download_dir.resolve()
        # 验证目录是否在 downloads 内
        target_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问下载目录以外的路径")
    except Exception as e:
        raise HTTPException(status_code=400, detail="无效的路径")

    if not target_path.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")
        
    target = str(target_path)
    try:
        if sys.platform == "win32":
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return {"ok": True, "message": f"已打开 {target}"}
    except Exception:
        raise HTTPException(status_code=500, detail="打开文件夹失败")
