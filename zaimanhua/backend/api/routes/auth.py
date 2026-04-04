from __future__ import annotations

from fastapi import APIRouter, Depends

from zaimanhua.backend.api.dependencies import BackendContainer, get_container
from zaimanhua.backend.schemas.auth import LoginRequest, SessionResponse
from zaimanhua.backend.schemas.common import OperationResponse

router = APIRouter()


@router.get("/auth/session", response_model=SessionResponse)
def get_session(container: BackendContainer = Depends(get_container)) -> SessionResponse:
    return container.auth_service.get_session()


@router.post("/auth/login", response_model=SessionResponse)
def login(
    request: LoginRequest,
    container: BackendContainer = Depends(get_container),
) -> SessionResponse:
    return container.auth_service.login(
        username=request.username,
        password=request.password,
        remember_password=request.remember_password,
    )


@router.post("/auth/logout", response_model=OperationResponse)
def logout(container: BackendContainer = Depends(get_container)) -> OperationResponse:
    return container.auth_service.logout()
