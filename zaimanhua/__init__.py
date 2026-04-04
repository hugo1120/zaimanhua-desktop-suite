from __future__ import annotations

__all__ = ["App"]


def __getattr__(name: str):
    if name == "App":
        from zaimanhua.ui.app import App

        return App
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
