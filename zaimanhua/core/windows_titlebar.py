from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any


_FRAME_CHANGED_FLAGS = 0x0020 | 0x0002 | 0x0001 | 0x0004 | 0x0010


@dataclass(frozen=True)
class WindowTitleBarPalette:
    style: str
    header_color: str
    border_color: str
    title_color: str


def get_window_titlebar_palette(is_dark: bool) -> WindowTitleBarPalette:
    if is_dark:
        return WindowTitleBarPalette(
            style="dark",
            header_color="#0a0a0c",
            border_color="#0a0a0c",
            title_color="#ffffff",
        )

    return WindowTitleBarPalette(
        style="light",
        header_color="#ffffff",
        border_color="#ffffff",
        title_color="#000000",
    )


def apply_window_titlebar_theme(
    hwnd: int,
    is_dark: bool,
    *,
    pywinstyles: Any | None = None,
    user32: Any | None = None,
) -> WindowTitleBarPalette:
    if pywinstyles is None:
        import pywinstyles as pywinstyles_module

        pywinstyles = pywinstyles_module

    if user32 is None:
        user32 = ctypes.windll.user32

    palette = get_window_titlebar_palette(is_dark)
    pywinstyles.apply_style(hwnd, palette.style)
    pywinstyles.change_header_color(hwnd, palette.header_color)
    pywinstyles.change_border_color(hwnd, palette.border_color)
    pywinstyles.change_title_color(hwnd, palette.title_color)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, _FRAME_CHANGED_FLAGS)
    return palette


def resolve_color_scheme_is_dark(
    color_scheme: str | None,
    *,
    fallback_is_dark: bool,
) -> bool:
    if isinstance(color_scheme, str):
        normalized = color_scheme.strip().strip('"').strip("'").lower()
        if normalized == "dark":
            return True
        if normalized == "light":
            return False

    return fallback_is_dark


def read_window_color_scheme_is_dark(
    window: Any,
    *,
    fallback_is_dark: bool,
) -> bool:
    color_scheme = None

    try:
        color_scheme = window.evaluate_js(
            "document.documentElement.getAttribute('data-mantine-color-scheme')"
        )
    except Exception:
        color_scheme = None

    return resolve_color_scheme_is_dark(
        color_scheme,
        fallback_is_dark=fallback_is_dark,
    )


def sync_window_titlebar_from_page(
    window: Any,
    hwnd: int,
    *,
    fallback_is_dark: bool,
    apply_theme: Any = apply_window_titlebar_theme,
) -> bool:
    is_dark = read_window_color_scheme_is_dark(
        window,
        fallback_is_dark=fallback_is_dark,
    )
    apply_theme(hwnd, is_dark)
    return is_dark


def sync_window_titlebar_if_needed(
    window: Any,
    hwnd: int,
    *,
    previous_is_dark: bool,
    apply_theme: Any = apply_window_titlebar_theme,
) -> bool:
    current_is_dark = read_window_color_scheme_is_dark(
        window,
        fallback_is_dark=previous_is_dark,
    )

    if current_is_dark != previous_is_dark:
        apply_theme(hwnd, current_is_dark)

    return current_is_dark
