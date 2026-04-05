from __future__ import annotations

from pathlib import Path


def resolve_frontend_file(frontend_dist_path: str | Path, request_path: str) -> Path | None:
    dist_path = Path(frontend_dist_path).resolve()
    normalized = str(request_path or "").strip().lstrip("/")

    if not normalized:
        candidate = dist_path / "index.html"
        return candidate if candidate.is_file() else None

    candidate = (dist_path / normalized).resolve()
    try:
        candidate.relative_to(dist_path)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    fallback = dist_path / "index.html"
    return fallback if fallback.is_file() else None
