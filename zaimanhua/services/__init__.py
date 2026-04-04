from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["DownloadManager", "DownloadTask", "MangaCrawler", "ZaimanhuaAPI"]


def __getattr__(name: str) -> Any:
    if name == "ZaimanhuaAPI":
        return getattr(import_module("zaimanhua.services.api"), name)
    if name == "MangaCrawler":
        return getattr(import_module("zaimanhua.services.crawler"), name)
    if name in {"DownloadManager", "DownloadTask"}:
        return getattr(import_module("zaimanhua.services.downloads"), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
