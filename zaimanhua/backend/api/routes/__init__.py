from .auth import router as auth_router
from .recent_updates import router as recent_updates_router
from .search import router as search_router
from .settings import router as settings_router

__all__ = ["auth_router", "settings_router", "search_router", "recent_updates_router"]
