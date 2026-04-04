from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_password: bool = False


class SessionResponse(BaseModel):
    username: str = ""
    logged_in: bool = False
    remember_password: bool = False
    remembered_password: str = ""
