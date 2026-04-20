from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from zaimanhua.backend.api.routes.recent_updates import list_recent_updates
from zaimanhua.services.api import ApiAuthenticationError, ApiRequestError


class FakeRecentUpdatesService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def list_page(self, page, refresh=False):
        self.calls.append((page, refresh))
        if self.error is not None:
            raise self.error
        raise AssertionError("当前用例应显式提供 error")


class FakeAuthService:
    def __init__(self):
        self.logout_calls = 0

    def logout(self):
        self.logout_calls += 1


def test_recent_updates_route_clears_session_and_returns_401_when_remote_auth_expires():
    auth_service = FakeAuthService()
    container = SimpleNamespace(
        recent_updates_service=FakeRecentUpdatesService(
            error=ApiAuthenticationError("登录已失效，请重新登录"),
        ),
        auth_service=auth_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        list_recent_updates(container=container, user=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "登录已失效，请重新登录"
    assert auth_service.logout_calls == 1


def test_recent_updates_route_returns_502_without_clearing_session_on_generic_failure():
    auth_service = FakeAuthService()
    container = SimpleNamespace(
        recent_updates_service=FakeRecentUpdatesService(
            error=ApiRequestError("最近更新加载失败，请稍后重试"),
        ),
        auth_service=auth_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        list_recent_updates(container=container, user=object())

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "最近更新加载失败，请稍后重试"
    assert auth_service.logout_calls == 0
