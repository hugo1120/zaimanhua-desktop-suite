from __future__ import annotations

import json
import logging
import threading
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from zaimanhua.backend.core.paths import get_config_path
from zaimanhua.backend.schemas.settings import SettingsResponse, SettingsUpdateRequest

logger = logging.getLogger(__name__)


def _coerce_limited_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < minimum or number > maximum:
        return default
    return number


def _normalize_theme_mode(value: Any, default: str = "dark") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"dark", "light"}:
        return normalized
    return default


class SettingsService:
    def __init__(self, config_path: str | None = None):
        default_config_path = get_config_path()
        self.config_path = str(config_path or default_config_path)
        self._lock = threading.RLock()

    def _read_config(self) -> dict[str, Any]:
        config_path = Path(self.config_path)
        if not config_path.exists():
            return {}
        try:
            with config_path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
                return data if isinstance(data, dict) else {}
        except JSONDecodeError as e:
            logger.error("JSON配置解析失败: %s - %s", config_path, e)
            return {}
        except Exception as e:
            logger.error("读取配置文件失败: %s - %s", config_path, e)
            return {}

    def _write_config(self, data: dict[str, Any]) -> None:
        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, ensure_ascii=False, indent=2)

    def read_raw_config(self) -> dict[str, Any]:
        with self._lock:
            return self._read_config()

    def write_raw_config(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._write_config(data)

    def _default_download_dir(self) -> str:
        return str(Path(self.config_path).parent / "downloads")

    def get_download_dir(self) -> str:
        with self._lock:
            data = self._read_config()
        custom = str(data.get("download_dir") or "").strip()
        if custom:
            return custom
        return self._default_download_dir()

    def get_theme_mode(self) -> str:
        with self._lock:
            data = self._read_config()
        return _normalize_theme_mode(data.get("theme_mode"))

    def set_theme_mode(self, theme_mode: str) -> str:
        normalized = _normalize_theme_mode(theme_mode)
        with self._lock:
            data = self._read_config()
            data["theme_mode"] = normalized
            self._write_config(data)
        return normalized

    def get_settings(self) -> SettingsResponse:
        with self._lock:
            data = self._read_config()
        username = str(data.get("username") or "")
        token = str(data.get("token") or "")
        max_books = _coerce_limited_int(data.get("max_books"), default=1, minimum=1, maximum=10)
        max_images = _coerce_limited_int(data.get("max_images"), default=5, minimum=1, maximum=32)
        custom_dir = str(data.get("download_dir") or "").strip()
        download_dir = custom_dir if custom_dir else self._default_download_dir()
        return SettingsResponse(
            username=username,
            has_token=bool(token),
            max_books=max_books,
            max_images=max_images,
            download_dir=download_dir,
        )

    def update_settings(self, request: SettingsUpdateRequest) -> SettingsResponse:
        with self._lock:
            data = self._read_config()
            data["max_books"] = request.max_books
            data["max_images"] = request.max_images
            if request.download_dir is not None:
                normalized = request.download_dir.strip()
                if normalized and normalized != self._default_download_dir():
                    # Validate the path is absolute and looks reasonable
                    dir_path = Path(normalized)
                    if not dir_path.is_absolute():
                        normalized = str((Path(self.config_path).parent / normalized).resolve())
                    data["download_dir"] = normalized
                else:
                    data.pop("download_dir", None)
            self._write_config(data)
        return self.get_settings()
