from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request, WebSocket, Depends, HTTPException

from zaimanhua.backend.app_services.auth_service import AuthService
from zaimanhua.backend.app_services.crawler_service import CrawlerService
from zaimanhua.backend.app_services.download_service import DownloadService
from zaimanhua.backend.app_services.library_service import LibraryService
from zaimanhua.backend.app_services.recent_updates_service import RecentUpdatesService
from zaimanhua.backend.app_services.search_service import SearchService
from zaimanhua.backend.app_services.settings_service import SettingsService
from zaimanhua.backend.events.bus import EventBus
from zaimanhua.services.api import ZaimanhuaAPI


class BackendContainer:
    def __init__(self, config_path: str | None = None, api_client: Any | None = None):
        self.event_bus = EventBus()
        self.settings_service = SettingsService(config_path=config_path)
        self.api = api_client or ZaimanhuaAPI()
        # Aliases for tests compatibility
        self.api_client = self.api
        
        config_dir = Path(self.settings_service.config_path).parent
        download_dir = self.settings_service.get_download_dir()

        self.auth_service = AuthService(api=self.api, settings_service=self.settings_service)
        self.search_service = SearchService(api=self.api)
        self.recent_updates_service = RecentUpdatesService(api=self.api)
        self.download_service = DownloadService(
            api=self.api,
            settings_service=self.settings_service,
            event_bus=self.event_bus,
        )
        self.crawler_service = CrawlerService(
            event_bus=self.event_bus,
            manga_list_file=str(config_dir / "manga_list.txt")
        )
        self.library_service = LibraryService(
            download_dir=download_dir,
            cache_path=str(config_dir / "library_cache.json"),
            manga_list_file=str(config_dir / "manga_list.txt"),
            api=self.api
        )

    def close(self) -> None:
        self.crawler_service.close()
        self.download_service.close()
        self.event_bus.close()


def get_container(request: Request) -> BackendContainer:
    return request.app.state.container


def get_ws_container(websocket: WebSocket) -> BackendContainer:
    return websocket.app.state.container


def get_current_user(container: BackendContainer = Depends(get_container)):
    session = container.auth_service.get_session()
    if not session.logged_in:
        raise HTTPException(status_code=401, detail="请先登录")
    return session
