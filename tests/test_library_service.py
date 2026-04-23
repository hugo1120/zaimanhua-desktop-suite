import json
import shutil
from contextlib import contextmanager
from pathlib import Path

from zaimanhua.backend.app_services.library_service import LibraryService


class FakeApi:
    def __init__(self, pages=None, error_on_page=None):
        self._pages = dict(pages or {})
        self._error_on_page = error_on_page
        self.calls = []

    def get_recent_updates_raw(self, page):
        self.calls.append(page)
        if self._error_on_page == page:
            raise RuntimeError("recent updates boom")
        return list(self._pages.get(page, []))


@contextmanager
def _temp_dir(name):
    temp_dir = Path(__file__).resolve().parents[1] / ".test_tmp" / name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _build_service(base_dir, local_items, api):
    download_dir = base_dir / "downloads"
    cache_path = base_dir / "library_cache.json"
    download_dir.mkdir(parents=True, exist_ok=True)

    items = {}
    ordered_names = []
    for index, item in enumerate(local_items, start=1):
        folder = str(item.get("folder_name") or f"book_{index}")
        ordered_names.append(folder)
        folder_path = download_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        info_payload = item.get("info_json")
        info_path = folder_path / "info.json"
        if isinstance(info_payload, dict):
            info_path.write_text(json.dumps(info_payload, ensure_ascii=False), encoding="utf-8")
        stored = {
            "title": item.get("title", folder),
            "id": item.get("id", "???"),
            "last_update_ts": int(item.get("last_update_ts", 0)),
            "author": item.get("author", ""),
            "latest_chapter": item.get("latest_chapter", ""),
        }
        if "cover_name" in item:
            stored["cover_name"] = item.get("cover_name", "")
        items[folder] = {
            "dir_mtime_ns": int(item.get("dir_mtime_ns", 0)),
            "info_mtime_ns": int(item.get("info_mtime_ns", 0)),
            "data": stored,
        }

    payload = {
        "version": 2,
        "root_mtime_ns": 0,
        "ordered_names": ordered_names,
        "items": items,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return LibraryService(
        download_dir=str(download_dir),
        cache_path=str(cache_path),
        api=api,
    )


def test_smart_update_candidates_selects_when_remote_is_newer():
    with _temp_dir("library_smart_update_newer") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 200, "title": "远端更新作品"},
                    {"id": "999", "last_updatetime": 300, "title": "不在本地"},
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[{"id": "100", "title": "本地作品", "last_update_ts": 100}],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.scanned_pages == 1
        assert response.recent_total == 2
        assert response.matched_total == 1
        assert response.candidate_total == 1
        assert response.missing_id_total == 0
        assert [item.id for item in response.items] == ["100"]


def test_smart_update_candidates_skips_when_local_already_latest():
    with _temp_dir("library_smart_update_latest") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 120, "title": "未更新"},
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[{"id": "100", "title": "本地作品", "last_update_ts": 120}],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.matched_total == 1
        assert response.candidate_total == 0
        assert response.items == []


def test_smart_update_candidates_skips_invalid_local_id_and_counts_it():
    with _temp_dir("library_smart_update_missing_id") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "300", "last_updatetime": 80, "title": "缺失ID"},
                    {"id": "200", "last_updatetime": 50, "title": "可更新作品"},
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[
                {"id": "???", "title": "缺失ID", "last_update_ts": 10},
                {"id": "200", "title": "正常作品", "last_update_ts": 0},
            ],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.missing_id_total == 1
        assert response.candidate_total == 1
        assert [item.id for item in response.items] == ["200"]
        assert all(item.id != "300" for item in response.items)


def test_smart_update_candidates_deduplicates_duplicate_ids_across_pages():
    with _temp_dir("library_smart_update_dedupe") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 20, "title": "第一页较旧"},
                ],
                2: [
                    {"id": "100", "last_updatetime": 40, "title": "第二页较新重复"},
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[{"id": "100", "title": "本地作品", "last_update_ts": 30}],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=2)

        assert response.ok is True
        assert response.scanned_pages == 2
        assert response.recent_total == 2
        assert response.matched_total == 1
        assert response.candidate_total == 1
        assert [item.id for item in response.items] == ["100"]
        assert api.calls == [1, 2]


def test_smart_update_candidates_returns_explicit_failure_when_recent_updates_fails(monkeypatch):
    with _temp_dir("library_smart_update_api_error") as temp_dir:
        api = FakeApi(error_on_page=1)
        service = _build_service(
            temp_dir,
            local_items=[{"id": "100", "title": "本地作品", "last_update_ts": 10}],
            api=api,
        )

        def _fail_if_scan_fallback():
            raise AssertionError("不应在最近更新失败时回退为全量扫描")

        monkeypatch.setattr(service, "_scan_library", _fail_if_scan_fallback)

        response = service.build_smart_update_candidates(max_pages=2)

        assert response.ok is False
        assert "最近更新" in response.message
        assert response.items == []
        assert response.candidate_total == 0


def test_smart_update_candidates_returns_failure_when_cache_unavailable():
    with _temp_dir("library_smart_update_empty_cache") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 200, "title": "远端更新作品"},
                ]
            }
        )
        service = _build_service(temp_dir, local_items=[], api=api)

        response = service.build_smart_update_candidates(max_pages=2)

        assert response.ok is False
        assert "刷新书库" in response.message
        assert response.scanned_pages == 0
        assert response.recent_total == 0
        assert response.items == []
        assert api.calls == []


def test_smart_update_candidates_returns_missing_id_guidance_when_cache_entries_have_no_valid_id():
    with _temp_dir("library_smart_update_all_missing_id") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 200, "title": "远端更新作品"},
                ]
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[
                {"id": "???", "title": "缺失ID-1", "last_update_ts": 10},
                {"id": "0", "title": "缺失ID-2", "last_update_ts": 20},
            ],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=2)

        assert response.ok is False
        assert response.missing_id_total == 2
        assert "补全" in response.message
        assert "刷新书库" not in response.message
        assert response.scanned_pages == 0
        assert response.recent_total == 0
        assert response.items == []
        assert api.calls == []


def test_smart_update_candidates_uses_remote_title_and_chapter_for_newer_candidate():
    with _temp_dir("library_smart_update_metadata_consistency") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {
                        "id": "100",
                        "last_updatetime": 300,
                        "title": "远端新标题",
                        "last_update_chapter_name": "第120话",
                    },
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[
                {"id": "100", "title": "本地旧标题", "last_update_ts": 200, "latest_chapter": "第80话"},
            ],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.candidate_total == 1
        assert response.items[0].last_update_ts == 300
        assert response.items[0].title == "远端新标题"
        assert response.items[0].latest_chapter == "第120话"


def test_smart_update_candidates_corrects_stale_cache_from_newer_info_json():
    with _temp_dir("library_smart_update_corrects_stale_cache") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {
                        "id": "100",
                        "last_updatetime": 250,
                        "title": "远端较旧标题",
                        "last_update_chapter_name": "第100话",
                    },
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[
                {
                    "id": "100",
                    "title": "缓存旧标题",
                    "last_update_ts": 100,
                    "latest_chapter": "第80话",
                    "info_mtime_ns": 0,
                    "info_json": {
                        "id": "100",
                        "title": "本地已更新标题",
                        "last_update_ts": 300,
                        "last_update_text": "3分钟前",
                        "latest_chapter": "第120话",
                    },
                }
            ],
            api=api,
        )

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.matched_total == 1
        assert response.candidate_total == 0
        assert response.items == []

        payload = json.loads(service._cache_path.read_text(encoding="utf-8"))
        cached = payload["items"]["book_1"]
        assert cached["data"]["last_update_ts"] == 300
        assert cached["data"]["title"] == "本地已更新标题"
        assert cached["data"]["latest_chapter"] == "第120话"
        assert cached["info_mtime_ns"] > 0


def test_smart_update_candidates_never_discovers_cover_from_cache_path(monkeypatch):
    with _temp_dir("library_smart_update_no_cover_discovery") as temp_dir:
        api = FakeApi(
            pages={
                1: [
                    {"id": "100", "last_updatetime": 200, "title": "远端更新作品"},
                ],
            }
        )
        service = _build_service(
            temp_dir,
            local_items=[{"id": "100", "title": "本地作品", "last_update_ts": 100}],
            api=api,
        )

        def _fail_if_discover_cover(_folder_path):
            raise AssertionError("智能更新路径不应探测封面文件")

        monkeypatch.setattr(service, "_discover_cover_path", _fail_if_discover_cover)

        response = service.build_smart_update_candidates(max_pages=1)

        assert response.ok is True
        assert response.candidate_total == 1
        assert [item.id for item in response.items] == ["100"]


def test_library_service_backfills_author_from_manga_list_file():
    with _temp_dir("library_author_backfill_from_index") as temp_dir:
        download_dir = temp_dir / "downloads"
        cache_path = temp_dir / "library_cache.json"
        manga_list_path = temp_dir / "manga_list.txt"
        folder = download_dir / "book_1"
        folder.mkdir(parents=True, exist_ok=True)
        manga_list_path.write_text("100|索引标题|索引作者\n", encoding="utf-8")
        (folder / "info.json").write_text(
            json.dumps({"id": "100", "title": "本地标题", "author": ""}, ensure_ascii=False),
            encoding="utf-8",
        )

        service = LibraryService(
            download_dir=str(download_dir),
            cache_path=str(cache_path),
            manga_list_file=str(manga_list_path),
            api=FakeApi(),
        )

        response = service.refresh_library()

        assert response.total == 1
        assert response.items[0].author == "索引作者"
