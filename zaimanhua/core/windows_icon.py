from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any


IMAGE_ICON = 1
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
SMTO_ABORTIFHUNG = 0x0002


def _send_seticon_message(user32: Any, hwnd: int, icon_type: int, icon_handle: int) -> None:
    send_message_timeout = getattr(user32, "SendMessageTimeoutW", None)
    if callable(send_message_timeout):
        result = send_message_timeout(
            hwnd,
            WM_SETICON,
            icon_type,
            icon_handle,
            SMTO_ABORTIFHUNG,
            200,
            0,
        )
        if not result:
            raise OSError(f"SendMessageTimeoutW failed for hwnd={hwnd}, icon_type={icon_type}")
        return

    user32.SendMessageW(hwnd, WM_SETICON, icon_type, icon_handle)


def apply_window_icon_from_file(
    hwnd: int,
    icon_path: str | Path,
    *,
    user32: Any | None = None,
) -> int:
    if user32 is None:
        user32 = ctypes.windll.user32

    icon_handle = user32.LoadImageW(
        0,
        str(icon_path),
        IMAGE_ICON,
        0,
        0,
        LR_LOADFROMFILE | LR_DEFAULTSIZE,
    )
    if not icon_handle:
        raise OSError(f"LoadImageW failed for icon: {icon_path}")

    _send_seticon_message(user32, hwnd, ICON_BIG, icon_handle)
    _send_seticon_message(user32, hwnd, ICON_SMALL, icon_handle)
    return int(icon_handle)
