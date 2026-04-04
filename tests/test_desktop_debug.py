from pathlib import Path
import shutil

from zaimanhua.core.desktop_debug import (
    configure_desktop_debug,
    desktop_log,
    reset_desktop_debug_for_tests,
)


def _make_temp_dir(name: str) -> Path:
    temp_dir = Path(__file__).resolve().parents[1] / ".test_tmp" / name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def test_desktop_log_writes_structured_line_with_session_and_details():
    log_path = _make_temp_dir("desktop_debug_case1") / "desktop_debug.log"
    configure_desktop_debug(log_path)

    desktop_log(
        "frontend.theme",
        "set_theme_start",
        theme="light",
        source="pywebviewready",
    )

    content = log_path.read_text(encoding="utf-8").strip()

    assert "[component=frontend.theme]" in content
    assert "[event=set_theme_start]" in content
    assert '"theme":"light"' in content
    assert '"source":"pywebviewready"' in content
    assert "[session=" in content
    assert "[thread=" in content
    assert "[seq=" in content

    reset_desktop_debug_for_tests()
    shutil.rmtree(log_path.parent)


def test_desktop_log_appends_multiple_lines_in_order():
    log_path = _make_temp_dir("desktop_debug_case2") / "desktop_debug.log"
    configure_desktop_debug(log_path)

    desktop_log("desktop.lifecycle", "start", phase="boot")
    desktop_log("desktop.lifecycle", "shown", phase="ready")

    lines = log_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert "[seq=0001]" in lines[0]
    assert "[event=start]" in lines[0]
    assert "[seq=0002]" in lines[1]
    assert "[event=shown]" in lines[1]

    reset_desktop_debug_for_tests()
    shutil.rmtree(log_path.parent)


def test_configure_desktop_debug_treats_dotted_directory_name_as_directory():
    temp_dir = _make_temp_dir("desktop.v1")
    log_path = configure_desktop_debug(temp_dir)

    assert log_path.name == "desktop_debug.log"
    assert log_path.parent == temp_dir

    reset_desktop_debug_for_tests()
    shutil.rmtree(temp_dir)


def test_desktop_log_serializes_non_json_value_with_fallback():
    log_path = _make_temp_dir("desktop_debug_case3") / "desktop_debug.log"
    configure_desktop_debug(log_path)

    desktop_log("desktop.test", "path_payload", path=Path("C:/demo/file.txt"))

    content = log_path.read_text(encoding="utf-8").strip()

    assert '"path":"C:\\\\demo\\\\file.txt"' in content

    reset_desktop_debug_for_tests()
    shutil.rmtree(log_path.parent)
