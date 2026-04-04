from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Mapping

from zaimanhua.core.manga_metadata import coerce_int, extract_latest_chapter, format_update_text
from zaimanhua.backend.schemas.library import LibraryItem, LibraryRepairResponse, LibraryResponse

LIBRARY_CACHE_VERSION = 2
COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

logger = logging.getLogger(__name__)


def _safe_mtime_ns(path: Path | str) -> int:
    try:
        return int(Path(path).stat().st_mtime_ns)
    except OSError:
        return 0


def _safe_mtime(path: Path | str) -> int:
    try:
        return int(Path(path).stat().st_mtime)
    except OSError:
        return 0


def _load_local_index_rows(manga_list_file: str | Path | None) -> list[dict[str, str]]:
    path = Path(manga_list_file) if manga_list_file else None
    if not path or not path.exists():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        rows.append(
            {
                "id": parts[0],
                "title": parts[1],
                "author": parts[2] if len(parts) > 2 else "",
            }
        )
    return rows


def _extract_author_text(raw_author: Any) -> str:
    if isinstance(raw_author, list):
        return ",".join(str(item.get("tag_name", "")) for item in raw_author if isinstance(item, dict))
    if isinstance(raw_author, str):
        return raw_author
    return ""


def _build_cache_record(item: dict[str, Any], dir_mtime_ns: int, info_mtime_ns: int) -> dict[str, Any]:
    stored_item = dict(item)
    stored_item.pop("path", None)
    cover_path = str(stored_item.pop("cover_path", "") or "")
    if cover_path:
        cover_name = os.path.basename(cover_path)
        if cover_name:
            stored_item["cover_name"] = cover_name
    return {
        "dir_mtime_ns": int(dir_mtime_ns or 0),
        "info_mtime_ns": int(info_mtime_ns or 0),
        "data": stored_item,
    }


def _empty_payload() -> dict[str, Any]:
    return {
        "version": LIBRARY_CACHE_VERSION,
        "root_mtime_ns": 0,
        "ordered_names": [],
        "items": {},
    }


class LibraryService:
    def __init__(
        self,
        download_dir: str | Path | None = None,
        cache_path: str | Path | None = None,
        manga_index: Mapping[str, Mapping[str, str]] | None = None,
        manga_list_file: str | Path | None = None,
        api: Any | None = None,
    ):
        root = Path(__file__).resolve().parents[3]
        self._download_dir = Path(download_dir or root / "downloads")
        self._cache_path = Path(cache_path or root / "library_cache.json")
        self._manga_index = dict(manga_index or {})
        self._manga_list_file = Path(manga_list_file or root / "manga_list.txt")
        self._api = api

    def list_library(self, keyword: str | None = None) -> LibraryResponse:
        payload = self._read_cache_payload()
        items = self._restore_from_cache(payload)
        if items:
            return self._build_response(items, keyword, "cache")
        return self._build_response(self._scan_library(), keyword, "scan")

    def refresh_library(self, keyword: str | None = None) -> LibraryResponse:
        scanned = self._scan_library()
        source = "scan"
        return self._build_response(scanned, keyword, source)

    def _read_cache_payload(self) -> dict[str, Any]:
        cache_path = self._cache_path
        if not cache_path.exists():
            return _empty_payload()
        try:
            content = cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception:
            logger.warning("书库缓存读取失败: %s", cache_path, exc_info=True)
            return _empty_payload()
        if not isinstance(data, dict):
            return _empty_payload()
        items = data.get("items")
        if not isinstance(items, dict):
            items = {}
        ordered_names = data.get("ordered_names")
        if not isinstance(ordered_names, list):
            ordered_names = [name for name in items.keys()]
        ordered_names = [str(name) for name in ordered_names if str(name) in items]
        return {
            "version": coerce_int(data.get("version", LIBRARY_CACHE_VERSION), LIBRARY_CACHE_VERSION),
            "root_mtime_ns": coerce_int(data.get("root_mtime_ns", 0), 0),
            "ordered_names": ordered_names,
            "items": items,
        }

    def _write_cache_payload(self, payload: dict[str, Any]) -> None:
        cache_path = self._cache_path
        temp_path = cache_path.with_name(f"{cache_path.name}.tmp")
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with temp_path.open("w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj, ensure_ascii=False, indent=2)
            os.replace(temp_path, cache_path)
        except Exception:
            logger.warning("书库缓存写入失败: %s", cache_path, exc_info=True)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _restore_from_cache(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        items_map = payload.get("items") or {}
        ordered_names = payload.get("ordered_names") or sorted(items_map.keys())
        restored = []
        for folder_name in ordered_names:
            folder_path = self._download_dir / folder_name
            entry = items_map.get(folder_name)
            restored.append(self._build_item_from_cache(folder_name, folder_path, entry))
        return restored

    def _scan_library(self) -> list[dict[str, Any]]:
        download_dir = self._download_dir
        if not download_dir.exists():
            return []

        # 获取现有缓存，用于增量校验
        existing_payload = self._read_cache_payload()
        existing_items = existing_payload.get("items") or {}
        current_root_mtime = _safe_mtime_ns(download_dir)

        try:
            # 机械盘优化：使用 os.scandir 获取元数据，减少系统调用
            with os.scandir(str(download_dir)) as it:
                entries = [entry for entry in it if entry.is_dir()]
        except OSError:
            logger.warning("书库目录读取失败: %s", download_dir, exc_info=True)
            return []

        # 按名称排序以保持 UI 一致
        entries.sort(key=lambda entry: entry.name)
        
        scanned: list[dict[str, Any]] = []
        cache_items: dict[str, dict[str, Any]] = {}
        ordered_names: list[str] = []

        for entry in entries:
            folder_name = entry.name
            try:
                # 从 scandir entry 中提取 mtime，避免额外的 stat 调用
                dir_mtime_ns = int(entry.stat().st_mtime_ns)
            except OSError:
                continue

            folder_path = Path(entry.path)
            info_mtime_ns = _safe_mtime_ns(folder_path / "info.json")

            # 尝试从缓存中恢复
            cached_record = existing_items.get(folder_name)
            item = None
            
            # 优先比较目录和 info.json 的 mtime；任一变化都需要重建该项。
            if isinstance(cached_record, dict):
                if (
                    cached_record.get("dir_mtime_ns") == dir_mtime_ns
                    and cached_record.get("info_mtime_ns") == info_mtime_ns
                ):
                    try:
                        item = self._build_item_from_cache(folder_name, folder_path, cached_record)
                    except Exception:
                        pass

            if item is None:
                # 只有在目录或 info.json 发生变化时，才执行昂贵的“深层扫描”
                try:
                    item = self._build_item_from_path(folder_name, folder_path)
                    # 记录新缓存
                    cache_items[folder_name] = _build_cache_record(item, dir_mtime_ns, info_mtime_ns)
                except Exception:
                    logger.warning("书库扫描失败: %s", entry.path, exc_info=True)
                    continue
            else:
                # 直接复用缓存记录，保持高性能
                cache_items[folder_name] = cached_record

            if isinstance(item, dict):
                scanned.append(item)
                ordered_names.append(folder_name)

        payload = {
            "version": LIBRARY_CACHE_VERSION,
            "root_mtime_ns": current_root_mtime,
            "ordered_names": ordered_names,
            "items": cache_items,
        }
        self._write_cache_payload(payload)
        return scanned

    def _build_item_from_path(self, folder_name: str, folder_path: Path) -> dict[str, Any]:
        item = {
            "title": folder_name,
            "id": "???",
            "path": str(folder_path),
            "author": "",
            "status": "未知状态",
            "description": "",
            "cover_path": "",
            "mtime": int(_safe_mtime(folder_path)),
            "last_update_ts": 0,
            "last_update_text": "",
            "latest_chapter": "",
        }
        info_path = folder_path / "info.json"
        if info_path.exists():
            try:
                data = json.loads(info_path.read_text(encoding="utf-8"))
                if "author" in data:
                    data["author"] = self._clean_author_field(data["author"])
                cover_path = self._normalize_cover_path(folder_path, data.get("cover_path"))
                if cover_path:
                    data["cover_path"] = str(cover_path)
                elif "cover_path" in data:
                    data.pop("cover_path", None)
                item.update(data)
            except json.JSONDecodeError as e:
                logger.error("解析 info.json 失败: %s - %s", info_path, e)
            except Exception as e:
                logger.error("读取 info.json 失败: %s - %s", info_path, e)
        return self._fill_author_from_index(item)

    def _build_item_from_cache(self, folder_name: str, folder_path: Path, cache_entry: dict[str, Any] | None) -> dict[str, Any]:
        data = dict((cache_entry or {}).get("data") or {})
        data.setdefault("title", folder_name)
        data["path"] = str(folder_path)
        cover_name = data.pop("cover_name", "")
        if cover_name:
            data["cover_path"] = str(folder_path / cover_name)
        else:
            cover_path = self._discover_cover_path(folder_path)
            data["cover_path"] = str(cover_path) if cover_path else ""
        data.setdefault("status", "未知状态")
        data.setdefault("author", "")
        data.setdefault("id", "???")
        data.setdefault("description", "")
        data.setdefault("mtime", int((cache_entry or {}).get("dir_mtime_ns", 0) // 1_000_000_000))
        data.setdefault("last_update_ts", 0)
        data.setdefault("last_update_text", "")
        data.setdefault("latest_chapter", "")
        return self._fill_author_from_index(data)

    def _clean_author_field(self, val: Any) -> str:
        if not val:
            return ""
        val = str(val)
        if "[{'tag_id'" in val:
            try:
                names = re.findall("'tag_name': '([^']+)'", val)
                return ",".join(names)
            except Exception:
                return val
        return val

    def _normalize_cover_path(self, folder_path: Path, cover_path_str: Any) -> Path | str:
        if not cover_path_str:
            return self._discover_cover_path(folder_path)
        path = Path(cover_path_str)
        if path.exists():
            return path
        candidate = folder_path / path.name
        if candidate.exists():
            return candidate
        return self._discover_cover_path(folder_path)

    def _discover_cover_path(self, folder_path: Path) -> Path | str:
        try:
            entries = sorted(folder_path.iterdir(), key=lambda e: e.name)
        except OSError:
            return ""
        candidates = []
        for entry in entries:
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in COVER_EXTENSIONS:
                continue
            if "cover" in entry.name.lower():
                return entry
            candidates.append(entry)
        return candidates[0] if candidates else ""

    def _fill_author_from_index(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("author"):
            return item
        cached = self._manga_index.get(str(item.get("id") or ""))
        if cached:
            item["author"] = cached.get("author", "")
        return item

    def _build_response(self, items: list[dict[str, Any]], keyword: str | None, source: str) -> LibraryResponse:
        cleaned_keyword = (keyword or "").strip().lower()
        if not cleaned_keyword:
            filtered = items
        else:
            filtered = []
            for item in items:
                title = str(item.get("title") or "").lower()
                item_id = str(item.get("id") or "").lower()
                author = str(item.get("author") or "").lower()
                if cleaned_keyword in title or cleaned_keyword in item_id or cleaned_keyword in author:
                    filtered.append(item)

        libs = [
            LibraryItem(
                id=str(item.get("id") or "???"),
                title=str(item.get("title") or ""),
                author=str(item.get("author") or ""),
                status=str(item.get("status") or "未知状态"),
                description=str(item.get("description") or ""),
                path=str(item.get("path") or ""),
                cover_path=str(item.get("cover_path") or ""),
                mtime=int(item.get("mtime") or 0),
                last_update_ts=int(item.get("last_update_ts") or 0),
                last_update_text=str(item.get("last_update_text") or ""),
                latest_chapter=str(item.get("latest_chapter") or ""),
            )
            for item in filtered
            if isinstance(item, dict)
        ]
        return LibraryResponse(items=libs, total=len(libs), source=source)

    def repair_metadata(self) -> LibraryRepairResponse:
        if self._api is None:
            return LibraryRepairResponse(ok=False, message="未配置漫画 API 客户端")

        if not self._download_dir.exists():
            return LibraryRepairResponse(ok=True, message="downloads 目录不存在", scanned=0, fixed=0, skipped=0)

        local_rows = _load_local_index_rows(self._manga_list_file)
        local_by_title = {row["title"]: row for row in local_rows if row.get("title")}
        scanned = 0
        fixed = 0
        skipped = 0

        for entry in sorted(self._download_dir.iterdir(), key=lambda item: item.name):
            if not entry.is_dir():
                continue
            scanned += 1
            if self._repair_single_folder(entry, local_by_title):
                fixed += 1
            else:
                skipped += 1

        self._scan_library()
        return LibraryRepairResponse(
            ok=True,
            message=f"已补全 {fixed} 个目录",
            scanned=scanned,
            fixed=fixed,
            skipped=skipped,
        )

    def _repair_single_folder(self, folder: Path, local_by_title: Mapping[str, Mapping[str, str]]) -> bool:
        info_path = folder / "info.json"
        existing: dict[str, Any] = {}
        if info_path.exists():
            try:
                existing = json.loads(info_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        manga_id = str(existing.get("id") or "").strip()
        title = str(existing.get("title") or folder.name).strip() or folder.name
        if not manga_id:
            local_match = local_by_title.get(folder.name)
            if local_match:
                manga_id = str(local_match.get("id") or "").strip()
                existing.setdefault("author", str(local_match.get("author") or ""))
            if not manga_id:
                results = self._api.search_dynamic(folder.name) or []
                exact_match = next(
                    (item for item in results if str(item.get("title") or "").strip() == folder.name),
                    None,
                )
                if exact_match:
                    manga_id = str(exact_match.get("id") or "").strip()
                    title = str(exact_match.get("title") or title).strip() or title

        if not manga_id:
            return False

        detail = self._api.get_manga_detail(manga_id) or {}
        if detail.get("errno") != 0:
            return False
        data = detail.get("data", {}).get("data", {})
        if not isinstance(data, dict):
            return False

        safe_title = self._api._sanitize(title)
        cover_url = str(data.get("cover") or "")
        cover_name = ""
        if cover_url:
            cover_name = f"{manga_id}_{safe_title}_cover.jpg"
            self._api.download_cover(cover_url, str(folder), cover_name)

        last_update_ts = coerce_int(data.get("last_updatetime"), coerce_int(existing.get("last_update_ts"), 0))
        latest_chapter = extract_latest_chapter(data) or str(existing.get("latest_chapter") or "")

        merged = dict(existing)
        merged.update(
            {
                "id": manga_id,
                "title": str(data.get("title") or title),
                "author": _extract_author_text(data.get("authors")) or str(merged.get("author") or ""),
                "status": str(self._api.get_status_label(data.get("status", [])) or "未知状态"),
                "description": str(data.get("description") or ""),
                "last_update_ts": last_update_ts,
                "last_update_text": format_update_text(last_update_ts),
                "latest_chapter": latest_chapter,
            }
        )
        merged.pop("cover_path", None)

        info_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
