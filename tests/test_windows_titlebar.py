from zaimanhua.core.windows_titlebar import (
    apply_window_titlebar_theme,
    get_window_titlebar_palette,
    sync_window_titlebar_if_needed,
    resolve_color_scheme_is_dark,
    sync_window_titlebar_from_page,
)


def test_light_palette_uses_white_titlebar_and_black_text():
    palette = get_window_titlebar_palette(False)

    assert palette.style == "light"
    assert palette.header_color == "#ffffff"
    assert palette.border_color == "#ffffff"
    assert palette.title_color == "#000000"


def test_apply_window_titlebar_theme_updates_border_before_refresh():
    calls = []

    class FakePyWinStyles:
        @staticmethod
        def apply_style(hwnd, style):
            calls.append(("apply_style", hwnd, style))

        @staticmethod
        def change_header_color(hwnd, color):
            calls.append(("change_header_color", hwnd, color))

        @staticmethod
        def change_border_color(hwnd, color):
            calls.append(("change_border_color", hwnd, color))

        @staticmethod
        def change_title_color(hwnd, color):
            calls.append(("change_title_color", hwnd, color))

    class FakeUser32:
        @staticmethod
        def SetWindowPos(hwnd, insert_after, x, y, cx, cy, flags):
            calls.append(("SetWindowPos", hwnd, flags))

    apply_window_titlebar_theme(1024, False, pywinstyles=FakePyWinStyles(), user32=FakeUser32())

    assert calls == [
        ("apply_style", 1024, "light"),
        ("change_header_color", 1024, "#ffffff"),
        ("change_border_color", 1024, "#ffffff"),
        ("change_title_color", 1024, "#000000"),
        ("SetWindowPos", 1024, 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010),
    ]


def test_resolve_color_scheme_is_dark_handles_quotes_and_fallback():
    assert resolve_color_scheme_is_dark("dark", fallback_is_dark=False) is True
    assert resolve_color_scheme_is_dark('"dark"', fallback_is_dark=False) is True
    assert resolve_color_scheme_is_dark("'light'", fallback_is_dark=True) is False
    assert resolve_color_scheme_is_dark(None, fallback_is_dark=True) is True
    assert resolve_color_scheme_is_dark("unknown", fallback_is_dark=False) is False


def test_sync_window_titlebar_from_page_reads_dom_theme_and_applies_it():
    calls = []

    class FakeWindow:
        @staticmethod
        def evaluate_js(script):
            calls.append(("evaluate_js", script))
            return '"dark"'

    def fake_apply(hwnd, is_dark):
        calls.append(("apply_theme", hwnd, is_dark))

    is_dark = sync_window_titlebar_from_page(
        FakeWindow(),
        2048,
        fallback_is_dark=False,
        apply_theme=fake_apply,
    )

    assert is_dark is True
    assert calls == [
        ("evaluate_js", "document.documentElement.getAttribute('data-mantine-color-scheme')"),
        ("apply_theme", 2048, True),
    ]


def test_sync_window_titlebar_if_needed_only_applies_on_theme_change():
    calls = []

    class FakeWindow:
        @staticmethod
        def evaluate_js(script):
            calls.append(("evaluate_js", script))
            return '"light"'

    def fake_apply(hwnd, is_dark):
        calls.append(("apply_theme", hwnd, is_dark))

    current_is_dark = sync_window_titlebar_if_needed(
        FakeWindow(),
        4096,
        previous_is_dark=True,
        apply_theme=fake_apply,
    )

    assert current_is_dark is False
    assert calls == [
        ("evaluate_js", "document.documentElement.getAttribute('data-mantine-color-scheme')"),
        ("apply_theme", 4096, False),
    ]
