from pathlib import Path

from zaimanhua.core.windows_icon import apply_window_icon_from_file


def test_apply_window_icon_from_file_uses_timeout_messages_when_available():
    calls = []

    class FakeUser32:
        @staticmethod
        def LoadImageW(instance, path, image_type, cx, cy, flags):
            calls.append(("LoadImageW", path, image_type, flags))
            return 9527

        @staticmethod
        def SendMessageTimeoutW(hwnd, message, icon_type, icon_handle, flags, timeout_ms, result):
            calls.append(
                ("SendMessageTimeoutW", hwnd, message, icon_type, icon_handle, flags, timeout_ms),
            )
            return 1

    apply_window_icon_from_file(
        2048,
        Path("D:/demo/favicon.ico"),
        user32=FakeUser32(),
    )

    assert calls == [
        ("LoadImageW", str(Path("D:/demo/favicon.ico")), 1, 0x00000010 | 0x00000040),
        ("SendMessageTimeoutW", 2048, 0x0080, 1, 9527, 0x0002, 200),
        ("SendMessageTimeoutW", 2048, 0x0080, 0, 9527, 0x0002, 200),
    ]
