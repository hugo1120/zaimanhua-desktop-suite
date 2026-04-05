from __future__ import annotations

import time
from collections.abc import Callable
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
    def _build_item(raw: dict[str, Any]) -> RecentUpdateItem:
        return RecentUpdateItem(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            cover=str(raw.get("cover") or ""),
            author=str(raw.get("author") or ""),
            status=str(raw.get("status") or ""),
            latest=str(raw.get("latest") or ""),
            time=str(raw.get("time") or ""),
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
            rows = self._api.get_recent_updates(page_number) or []
            self._page_cache[page_number] = (
                now,
                [
                    self._build_item(row)
                    for row in rows
                    if isinstance(row, dict)
                ],
            )

        return RecentUpdatesResponse(page=page_number, items=self._page_cache[page_number][1])
