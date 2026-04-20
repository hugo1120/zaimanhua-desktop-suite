import pytest

from zaimanhua.backend.app_services.recent_updates_service import RecentUpdatesService
from zaimanhua.services.api import ApiAuthenticationError


class FakeApi:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_recent_updates_raw(self, page):
        self.calls.append(page)
        return list(self.pages.get(page, []))


def test_refresh_clears_all_cached_pages():
    now = [100.0]
    api = FakeApi(
        {
            1: [{"id": "1", "title": "第一页旧数据", "status": "连载中", "time": "旧"}],
            2: [{"id": "2", "title": "第二页旧数据", "status": "连载中", "time": "旧"}],
        }
    )
    service = RecentUpdatesService(api=api, time_fn=lambda: now[0], cache_ttl_seconds=60)

    first_page = service.list_page(1)
    second_page = service.list_page(2)
    assert first_page.items[0].id == "1"
    assert second_page.items[0].id == "2"

    api.pages = {
        1: [{"id": "10", "title": "第一页新数据", "status": "已完结", "time": "新"}],
        2: [{"id": "20", "title": "第二页新数据", "status": "已完结", "time": "新"}],
    }

    refreshed_first_page = service.list_page(1, refresh=True)
    refreshed_second_page = service.list_page(2)

    assert refreshed_first_page.items[0].id == "10"
    assert refreshed_second_page.items[0].id == "20"
    assert api.calls == [1, 2, 1, 2]


def test_cache_expires_after_ttl():
    now = [100.0]
    api = FakeApi(
        {
            1: [{"id": "1", "title": "第一页旧数据", "status": "连载中", "time": "旧"}],
        }
    )
    service = RecentUpdatesService(api=api, time_fn=lambda: now[0], cache_ttl_seconds=30)

    initial_page = service.list_page(1)
    assert initial_page.items[0].id == "1"

    api.pages = {
        1: [{"id": "10", "title": "第一页新数据", "status": "已完结", "time": "新"}],
    }

    now[0] = 131.0
    refreshed_page = service.list_page(1)

    assert refreshed_page.items[0].id == "10"
    assert api.calls == [1, 1]


def test_list_page_builds_items_from_raw_api_rows():
    api = FakeApi(
        {
            1: [
                {
                    "comic_id": 10,
                    "title": "原始最近更新",
                    "cover": "https://example.com/cover.jpg",
                    "authors": "作者A",
                    "status": "连载中",
                    "last_update_chapter_name": "第10话",
                    "last_updatetime": 1713500000,
                }
            ]
        }
    )
    service = RecentUpdatesService(api=api)

    response = service.list_page(1)

    assert response.page == 1
    assert api.calls == [1]
    assert len(response.items) == 1
    assert response.items[0].id == "10"
    assert response.items[0].title == "原始最近更新"
    assert response.items[0].author == "作者A"
    assert response.items[0].latest == "第10话"
    assert response.items[0].time != ""


def test_list_page_propagates_authentication_error_from_raw_api():
    class AuthExpiredApi:
        def get_recent_updates_raw(self, page):
            raise ApiAuthenticationError("登录已失效，请重新登录")

    service = RecentUpdatesService(api=AuthExpiredApi())

    with pytest.raises(ApiAuthenticationError, match="登录已失效"):
        service.list_page(1)
