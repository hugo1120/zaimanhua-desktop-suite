from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zaimanhua.backend.api.dependencies import BackendContainer
from zaimanhua.backend.api.routes.auth import router as auth_router
from zaimanhua.backend.api.routes.covers import router as covers_router
from zaimanhua.backend.api.routes.crawler import router as crawler_router
from zaimanhua.backend.api.routes.downloads import router as downloads_router
from zaimanhua.backend.api.routes.library import router as library_router
from zaimanhua.backend.api.routes.library_actions import router as library_actions_router
from zaimanhua.backend.api.routes.manga import router as manga_router
from zaimanhua.backend.api.routes.recent_updates import router as recent_updates_router
from zaimanhua.backend.api.routes.search import router as search_router
from zaimanhua.backend.api.routes.settings import router as settings_router
from zaimanhua.backend.api.websocket import router as websocket_router


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    try:
        yield
    finally:
        container = getattr(app.state, "container", None)
        if container is not None and hasattr(container, "close"):
            container.close()


def create_app(config_path: str | None = None, api_client: Any | None = None) -> FastAPI:
    app = FastAPI(title="Zaimanhua Web Backend", lifespan=_app_lifespan)
    # Allow localhost origins on typical dev port range
    cors_origins = []
    for port in range(5173, 5183):
        cors_origins.append(f"http://localhost:{port}")
        cors_origins.append(f"http://127.0.0.1:{port}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.container = BackendContainer(config_path=config_path, api_client=api_client)
    app.include_router(settings_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(manga_router, prefix="/api")
    app.include_router(library_router, prefix="/api")
    app.include_router(library_actions_router, prefix="/api")
    app.include_router(recent_updates_router, prefix="/api")
    app.include_router(downloads_router, prefix="/api")
    app.include_router(crawler_router, prefix="/api")
    app.include_router(websocket_router)
    app.include_router(covers_router, prefix="/api")
    return app
