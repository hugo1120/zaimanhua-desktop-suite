import os
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_env_path(env_name: str) -> Path | None:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return None
    return Path(raw_value).resolve()


def get_app_root() -> Path:
    return _resolve_env_path("ZAIMANHUA_ROOT") or get_project_root()


def get_config_path() -> Path:
    return _resolve_env_path("ZAIMANHUA_CONFIG_PATH") or (get_app_root() / "config.json")


def get_data_root() -> Path:
    return get_config_path().parent


def get_download_dir() -> Path:
    return _resolve_env_path("ZAIMANHUA_DOWNLOAD_DIR") or (get_data_root() / "downloads")


def get_manga_list_path() -> Path:
    return get_data_root() / "manga_list.txt"


def get_library_cache_path() -> Path:
    return get_data_root() / "library_cache.json"
