from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from zaimanhua.backend.schemas.recent_updates import RecentUpdateItem, RecentUpdatesResponse

DEFAULT_RECENT_UPDATES_CACHE_TTL_SECONDS = 60.0


class RecentUpdatesService:
    def __init__(
        self,
        api: Any,
        *,
        time_fn: Callable[[], float] | None = None,
        cache_ttl_seconds: float = DEFAULT_RECENT_UPDATES_CACHE_TTL_SECONDS,
    ):
        self._api = api
        self._time_fn = time_fn or time.time
        try:
            normalized_ttl = float(cache_ttl_seconds)
        except (TypeError, ValueError):
            normalized_ttl = DEFAULT_RECENT_UPDATES_CACHE_TTL_SECONDS
        self._cache_ttl_seconds = max(normalized_ttl, 0.0)
        self._page_cache: dict[int, tuple[float, list[RecentUpdateItem]]] = {}

    @staticmethod
    def _normalize_author(raw: dict[str, Any]) -> str:
        author = raw.get("author")
        if isinstance(author, str):
            return author

        authors = raw.get("authors")
        if isinstance(authors, str):
            return authors
        if isinstance(authors, list):
            names: list[str] = []
            for item in authors:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict):
                    value = item.get("tag_name") or item.get("name")
                    if isinstance(value, str) and value.strip():
                        names.append(value.strip())
            return ",".join(names)
        return ""

    @staticmethod
    def _normalize_status(raw: dict[str, Any]) -> str:
        status = raw.get("status")
        if isinstance(status, str):
            return status
        if isinstance(status, list):
            labels: list[str] = []
            for item in status:
                if isinstance(item, str) and item.strip():
                    labels.append(item.strip())
                elif isinstance(item, dict):
                    value = item.get("tag_name") or item.get("name")
                    if isinstance(value, str) and value.strip():
                        labels.append(value.strip())
            return ",".join(labels)
        return ""

    @staticmethod
    def _normalize_time(raw: dict[str, Any]) -> str:
        explicit_time = raw.get("time")
        if isinstance(explicit_time, str) and explicit_time.strip():
            return explicit_time

        raw_ts = raw.get("last_updatetime") or 0
        try:
            ts = int(raw_ts)
        except (TypeError, ValueError):
            ts = 0
        if ts <= 0:
            return ""
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return ""

    @classmethod
    def _build_item(cls, raw: dict[str, Any]) -> RecentUpdateItem:
        manga_id = raw.get("id") or raw.get("comic_id") or ""
        return RecentUpdateItem(
            id=str(manga_id),
            title=str(raw.get("title") or raw.get("name") or ""),
            cover=str(raw.get("cover") or ""),
            author=cls._normalize_author(raw),
            status=cls._normalize_status(raw),
            latest=str(raw.get("latest") or raw.get("last_update_chapter_name") or ""),
            time=cls._normalize_time(raw),
        )

    def list_page(self, page: int, refresh: bool = False) -> RecentUpdatesResponse:
        try:
            page_number = int(page)
        except (TypeError, ValueError):
            page_number = 1
        if page_number < 1:
            page_number = 1

        if refresh:
            self._page_cache.clear()

        cached_entry = self._page_cache.get(page_number)
        now = float(self._time_fn())
        cache_expired = True
        if cached_entry is not None:
            cached_at, _ = cached_entry
            cache_expired = (now - cached_at) >= self._cache_ttl_seconds

        if cached_entry is None or cache_expired:
            rows = self._api.get_recent_updates_raw(page_number) or []
            self._page_cache[page_number] = (
                now,
                [
                    self._build_item(row)
                    for row in rows
                    if isinstance(row, dict)
                ],
            )

        return RecentUpdatesResponse(page=page_number, items=self._page_cache[page_number][1])
