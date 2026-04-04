from __future__ import annotations

import importlib

__all__ = ["runtime"]


def __getattr__(name: str):
    if name == "runtime":
        module = importlib.import_module(".runtime", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
