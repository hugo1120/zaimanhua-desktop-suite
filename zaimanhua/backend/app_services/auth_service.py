from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from zaimanhua.backend.schemas.auth import SessionResponse
from zaimanhua.backend.schemas.common import OperationResponse


class AuthService:
    def __init__(self, api: Any, settings_service: Any):
        self._api = api
        self._settings_service = settings_service

    def _get_api_token(self) -> str:
        return str(getattr(self._api, "token", "") or "")

    def _set_api_token(self, token: str) -> None:
        setattr(self._api, "token", str(token or ""))

    def get_session(self) -> SessionResponse:
        data = self._settings_service.read_raw_config()
        username = str(data.get("username") or "")
        token = str(data.get("token") or "")
        remembered_password = str(data.get("remembered_password") or "")
        self._set_api_token(token)
        return SessionResponse(
            username=username,
            logged_in=bool(token),
            remember_password=bool(remembered_password),
            remembered_password=remembered_password,
        )

    def login(self, username: str, password: str, remember_password: bool = False) -> SessionResponse:
        self._set_api_token("")
        ok = bool(self._api.login(username, password))
        token = self._get_api_token()
        if not ok or not token:
            raise HTTPException(status_code=401, detail="登录失败")
        data = self._settings_service.read_raw_config()
        data["username"] = username
        data["token"] = token
        if remember_password:
            data["remembered_password"] = password
        else:
            data.pop("remembered_password", None)
        self._settings_service.write_raw_config(data)
        return self.get_session()

    def logout(self) -> OperationResponse:
        data = self._settings_service.read_raw_config()
        data["token"] = ""
        self._settings_service.write_raw_config(data)
        self._set_api_token("")
        return OperationResponse(ok=True, message="已退出登录")
