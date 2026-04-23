from zaimanhua.backend.app_services import search_service
from zaimanhua.backend.app_services.search_service import SearchService


class FakeApi:
    def __init__(self, rows):
        self._rows = list(rows)
        self.calls = []

    def search_dynamic(self, keyword):
        self.calls.append(keyword)
        return list(self._rows)


def test_search_backfills_author_from_local_index_for_remote_web_result(monkeypatch):
    monkeypatch.setattr(
        search_service,
        "_load_local_index",
        lambda: [
            {
                "id": "123",
                "title": "索引里的标题",
                "author": "索引作者",
                "source": "local",
                "status": "",
                "cover_url": "",
            }
        ],
    )
    service = SearchService(
        api=FakeApi(
            [
                {
                    "id": "123",
                    "title": "网页搜索结果",
                    "author": "",
                    "source": "web",
                    "status": "",
                    "cover_url": "",
                }
            ]
        )
    )

    response = service.search("只命中网页")

    assert len(response.items) == 1
    assert response.items[0].id == "123"
    assert response.items[0].title == "网页搜索结果"
    assert response.items[0].author == "索引作者"
    assert response.items[0].source == "web"


def test_search_reloads_local_index_when_source_file_changes(monkeypatch, tmp_path):
    index_path = tmp_path / "manga_list.txt"
    index_path.write_text("1|旧标题|旧作者\n", encoding="utf-8")
    monkeypatch.setattr(search_service, "_default_index_path", lambda: index_path)
    monkeypatch.setattr(search_service, "_LOCAL_INDEX_CACHE", None)
    if hasattr(search_service, "_LOCAL_INDEX_CACHE_KEY"):
        monkeypatch.setattr(search_service, "_LOCAL_INDEX_CACHE_KEY", None)

    class FakeApiWithoutRemoteResults:
        def search_dynamic(self, keyword):
            return []

    service = SearchService(api=FakeApiWithoutRemoteResults())

    first = service.search("旧")
    assert [item.title for item in first.items] == ["旧标题"]

    index_path.write_text("2|新标题|新作者\n", encoding="utf-8")

    second = service.search("新")

    assert [item.title for item in second.items] == ["新标题"]
