import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

from zaimanhua.backend.app_services import crawler_service as service_mod
from zaimanhua.backend.events.bus import EventBus
from zaimanhua.services import crawler as crawler_mod


def _make_temp_dir(name: str) -> Path:
    temp_dir = Path(__file__).resolve().parents[1] / ".test_tmp" / name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")


def test_crawler_service_keeps_thread_error_message(monkeypatch):
    class FailingCrawler:
        def __init__(self, callback=None, stop_event=None):
            self.callback = callback
            self.stop_event = stop_event

        def run(self, start_id, end_id):
            raise RuntimeError("boom")

    temp_dir = _make_temp_dir("crawler_service_thread_error")
    index_file = temp_dir / "manga_list.txt"
    index_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        service_mod,
        "_create_crawler",
        lambda callback, stop_event: FailingCrawler(callback=callback, stop_event=stop_event),
    )

    service = service_mod.CrawlerService(event_bus=EventBus(), manga_list_file=str(index_file))
    service.start(1, 2)

    _wait_until(lambda: not service.get_status().running)

    assert service.get_status().last_message == "爬虫错误: boom"
    shutil.rmtree(temp_dir)


def test_crawler_service_reports_missing_progress_when_crawler_returns_silently(monkeypatch):
    class SilentCrawler:
        def __init__(self, callback=None, stop_event=None):
            self.callback = callback
            self.stop_event = stop_event

        def run(self, start_id, end_id):
            return

    temp_dir = _make_temp_dir("crawler_service_silent_finish")
    index_file = temp_dir / "manga_list.txt"
    index_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        service_mod,
        "_create_crawler",
        lambda callback, stop_event: SilentCrawler(callback=callback, stop_event=stop_event),
    )

    service = service_mod.CrawlerService(event_bus=EventBus(), manga_list_file=str(index_file))
    service.start(1, 2)

    _wait_until(lambda: not service.get_status().running)

    assert service.get_status().last_message == "索引任务已结束，但未收到任何进度回调"
    shutil.rmtree(temp_dir)


def test_manga_crawler_disables_environment_proxy_settings():
    crawler = crawler_mod.MangaCrawler()

    assert crawler.session.trust_env is False


def test_importing_crawler_module_does_not_pull_gui_runtime():
    repo_root = Path(__file__).resolve().parents[1]
    script = """
import sys
sys.modules.pop('zaimanhua.services.crawler', None)
sys.modules.pop('zaimanhua.core.runtime', None)
import zaimanhua.services.crawler
print('zaimanhua.core.runtime' in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_manga_crawler_reports_failure_summary_when_all_requests_fail(monkeypatch):
    temp_dir = _make_temp_dir("crawler_all_requests_fail")
    index_file = temp_dir / "manga_list.txt"
    index_file.write_text("", encoding="utf-8")
    messages: list[str] = []

    monkeypatch.setattr(crawler_mod, "MANGA_LIST_FILE", str(index_file))
    monkeypatch.setattr(crawler_mod, "CRAWLER_MAX_WORKERS", 1)

    crawler = crawler_mod.MangaCrawler(callback=messages.append)

    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(crawler.session, "get", raise_connection_error)

    crawler.run(1, 2)

    assert any("索引更新失败" in message and "offline" in message for message in messages)
    shutil.rmtree(temp_dir)


def test_manga_crawler_allows_null_authors_without_counting_as_failure(monkeypatch):
    temp_dir = _make_temp_dir("crawler_null_authors")
    index_file = temp_dir / "manga_list.txt"
    index_file.write_text("", encoding="utf-8")
    messages: list[str] = []

    monkeypatch.setattr(crawler_mod, "MANGA_LIST_FILE", str(index_file))
    monkeypatch.setattr(crawler_mod, "CRAWLER_MAX_WORKERS", 1)

    crawler = crawler_mod.MangaCrawler(callback=messages.append)

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "errno": 0,
                "data": {
                    "data": {
                        "title": "测试漫画",
                        "authors": None,
                    }
                },
            }

    monkeypatch.setattr(crawler.session, "get", lambda *args, **kwargs: DummyResponse())

    crawler.run(1, 1)

    assert crawler.request_error_count == 0
    assert any("保存成功" in message for message in messages)
    assert "测试漫画" in index_file.read_text(encoding="utf-8")
    shutil.rmtree(temp_dir)
