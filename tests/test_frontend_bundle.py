import shutil
from contextlib import contextmanager
from pathlib import Path

from zaimanhua.core.frontend_bundle import resolve_frontend_file


@contextmanager
def _temp_dir(name: str):
    temp_dir = Path(__file__).resolve().parents[1] / ".test_tmp" / name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_resolve_frontend_file_serves_root_static_asset():
    with _temp_dir("frontend_bundle_root_asset") as temp_dir:
        dist = temp_dir / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        (dist / "theme-bootstrap.js").write_text("console.log('ok')", encoding="utf-8")

        resolved = resolve_frontend_file(dist, "theme-bootstrap.js")

        assert resolved == dist / "theme-bootstrap.js"


def test_resolve_frontend_file_falls_back_to_index_for_frontend_route():
    with _temp_dir("frontend_bundle_route_fallback") as temp_dir:
        dist = temp_dir / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")

        resolved = resolve_frontend_file(dist, "login")

        assert resolved == dist / "index.html"


def test_resolve_frontend_file_blocks_parent_traversal():
    with _temp_dir("frontend_bundle_path_traversal") as temp_dir:
        dist = temp_dir / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")

        resolved = resolve_frontend_file(dist, "../desktop_debug.log")

        assert resolved is None
