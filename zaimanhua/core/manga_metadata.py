from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def format_update_text(timestamp: Any) -> str:
    value = coerce_int(timestamp, 0)
    if value <= 0:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def extract_latest_chapter(data: Mapping[str, Any]) -> str:
    latest_name = str(data.get("last_update_chapter_name") or "").strip()
    if latest_name:
        return latest_name

    latest_id = str(data.get("last_update_chapter_id") or "").strip()
    chapters = data.get("chapters")
    if not latest_id or not isinstance(chapters, list):
        return ""

    for group in chapters:
        if not isinstance(group, dict):
            continue
        rows = group.get("data")
        if not isinstance(rows, list):
            continue
        for chapter in rows:
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("chapter_id") or chapter.get("id") or "").strip()
            if chapter_id != latest_id:
                continue
            return str(chapter.get("chapter_title") or chapter.get("title") or "").strip()
    return ""
