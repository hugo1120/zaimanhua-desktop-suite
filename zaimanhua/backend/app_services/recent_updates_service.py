from __future__ import annotations

from typing import Any

from zaimanhua.backend.schemas.recent_updates import RecentUpdateItem, RecentUpdatesResponse


class RecentUpdatesService:
    def __init__(self, api: Any):
        self._api = api
        self._page_cache: dict[int, list[RecentUpdateItem]] = {}

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

        if refresh and page_number in self._page_cache:
            del self._page_cache[page_number]

        if page_number not in self._page_cache:
            rows = self._api.get_recent_updates(page_number) or []
            self._page_cache[page_number] = [
                self._build_item(row)
                for row in rows
                if isinstance(row, dict)
            ]

        return RecentUpdatesResponse(page=page_number, items=self._page_cache[page_number])
