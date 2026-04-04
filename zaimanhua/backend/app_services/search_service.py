from __future__ import annotations

from pathlib import Path
from typing import Any

from zaimanhua.backend.core.paths import get_manga_list_path
from zaimanhua.backend.schemas.search import SearchResponse, SearchResultItem


_LOCAL_INDEX_CACHE: list[dict[str, str]] | None = None


def _default_index_path() -> Path:
    return get_manga_list_path()


def _load_local_index() -> list[dict[str, str]]:
    global _LOCAL_INDEX_CACHE
    if _LOCAL_INDEX_CACHE is not None:
        return _LOCAL_INDEX_CACHE

    index_path = _default_index_path()
    rows: list[dict[str, str]] = []
    if not index_path.exists():
        _LOCAL_INDEX_CACHE = rows
        return rows

    for line in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) < 2:
            continue
        manga_id = str(parts[0] or "").strip()
        title = str(parts[1] or "").strip()
        author = str(parts[2] or "").strip() if len(parts) > 2 else ""
        if not manga_id or not title:
            continue
        rows.append(
            {
                "id": manga_id,
                "title": title,
                "author": author,
                "source": "local",
                "status": "",
                "cover_url": "",
            }
        )

    _LOCAL_INDEX_CACHE = rows
    return rows


class SearchService:
    def __init__(self, api: Any):
        self._api = api

    @staticmethod
    def _build_item(raw: dict[str, Any], default_source: str = "") -> SearchResultItem:
        return SearchResultItem(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            author=str(raw.get("author") or ""),
            source=str(raw.get("source") or default_source or ""),
            status=str(raw.get("status") or ""),
            cover_url=str(raw.get("cover_url") or raw.get("cover") or ""),
            description=str(raw.get("description") or ""),
        )

    def search(self, keyword: str) -> SearchResponse:
        normalized_keyword = str(keyword or "").strip()
        key = normalized_keyword.casefold()

        local_items: list[SearchResultItem] = []
        for row in _load_local_index():
            title = str(row.get("title") or "")
            author = str(row.get("author") or "")
            if key and key not in title.casefold() and key not in author.casefold():
                continue
            local_items.append(self._build_item(row, default_source="local"))

        merged_items: list[SearchResultItem] = []
        merged_by_id: dict[str, SearchResultItem] = {}
        for item in local_items:
            if not item.id:
                continue
            merged_items.append(item)
            merged_by_id[item.id] = item

        remote_rows = self._api.search_dynamic(normalized_keyword) or []
        for row in remote_rows:
            item = self._build_item(row, default_source="remote")
            if not item.id:
                continue
            existing = merged_by_id.get(item.id)
            if existing is not None:
                if not existing.cover_url and item.cover_url:
                    existing.cover_url = item.cover_url
                if not existing.description and item.description:
                    existing.description = item.description
                if not existing.status and item.status:
                    existing.status = item.status
                if item.source and item.source not in existing.source.split("+"):
                    existing.source = f"{existing.source}+{item.source}" if existing.source else item.source
                continue
            merged_items.append(item)
            merged_by_id[item.id] = item

        return SearchResponse(keyword=normalized_keyword, items=merged_items)
