from zaimanhua.core.desktop_runtime import (
    activate_window,
    build_webview_start_kwargs,
    stabilize_window_display,
    wait_for_tcp_port,
    wait_for_window_handle,
)


def test_wait_for_tcp_port_retries_until_connection_succeeds():
    attempts = []

    def fake_connect(host: str, port: int) -> bool:
        attempts.append((host, port))
        return len(attempts) >= 3

    sleep_calls = []

    result = wait_for_tcp_port(
        "127.0.0.1",
        9527,
        timeout_seconds=1.0,
        poll_interval=0.01,
        connect_fn=fake_connect,
        sleep_fn=sleep_calls.append,
    )

    assert result is True
    assert attempts == [
        ("127.0.0.1", 9527),
        ("127.0.0.1", 9527),
        ("127.0.0.1", 9527),
    ]
    assert sleep_calls == [0.01, 0.01]


def test_wait_for_window_handle_retries_until_handle_is_ready():
    class FakeHandle:
        def ToInt64(self):
            return 4242

    class FakeNative:
        def __init__(self):
            self.calls = 0

        @property
        def Handle(self):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("handle not ready")
            return FakeHandle()

    class FakeWindow:
        def __init__(self):
            self.native = FakeNative()

    sleep_calls = []

    hwnd = wait_for_window_handle(
        FakeWindow(),
        timeout_seconds=1.0,
        poll_interval=0.01,
        sleep_fn=sleep_calls.append,
    )

    assert hwnd == 4242
    assert sleep_calls == [0.01, 0.01]


def test_activate_window_restores_and_brings_window_to_front():
    class FakeUser32:
        def __init__(self):
            self.calls = []

        def ShowWindow(self, hwnd, code):
            self.calls.append(("ShowWindow", hwnd, code))
            return 1

        def SetWindowPos(self, hwnd, insert_after, x, y, cx, cy, flags):
            self.calls.append(("SetWindowPos", hwnd, insert_after, flags))
            return 1

        def BringWindowToTop(self, hwnd):
            self.calls.append(("BringWindowToTop", hwnd))
            return 1

        def SetForegroundWindow(self, hwnd):
            self.calls.append(("SetForegroundWindow", hwnd))
            return 1

    user32 = FakeUser32()

    activate_window(4242, user32=user32)

    assert user32.calls == [
        ("ShowWindow", 4242, 9),
        ("SetWindowPos", 4242, -1, 3),
        ("SetWindowPos", 4242, -2, 3),
        ("BringWindowToTop", 4242),
        ("SetForegroundWindow", 4242),
    ]


def test_stabilize_window_display_invokes_show_topmost_and_activate():
    class FakeSignal:
        def __init__(self, value: bool):
            self.value = value
            self.calls = []

        def wait(self, timeout: float):
            self.calls.append(timeout)
            return self.value

    class FakeNative:
        def __init__(self):
            self.calls = []

        def show(self):
            self.calls.append("show")

    class FakeWindow:
        def __init__(self):
            self.native = FakeNative()
            self.events = type(
                "Events",
                (),
                {
                    "before_show": FakeSignal(True),
                    "shown": FakeSignal(False),
                },
            )()
            self._on_top = False

        @property
        def on_top(self):
            return self._on_top

        @on_top.setter
        def on_top(self, value):
            self._on_top = value

    window = FakeWindow()
    logs = []
    activations = []

    hwnd = stabilize_window_display(
        window,
        wait_for_handle_fn=lambda *_args, **_kwargs: 4242,
        activate_fn=lambda handle: activations.append(handle),
        log_fn=lambda component, event, **details: logs.append((component, event, details)),
    )

    assert hwnd == 4242
    assert window.native.calls == ["show", "show"]
    assert activations == [4242]
    assert window.events.before_show.calls == [10.0]
    assert window.events.shown.calls == [5.0]
    assert logs == [
        ("desktop.window", "stabilizer_start", {}),
        ("desktop.window", "show_invoked", {}),
        ("desktop.window", "handle_ready", {"hwnd": 4242}),
        ("desktop.window", "shown_wait_timeout", {"hwnd": 4242, "timeout_seconds": 5.0}),
        ("desktop.window", "show_reinvoked", {"hwnd": 4242}),
        ("desktop.window", "topmost_applied", {"hwnd": 4242}),
        ("desktop.window", "foreground_applied", {"hwnd": 4242}),
        ("desktop.window", "topmost_released", {"hwnd": 4242}),
    ]


def test_build_webview_start_kwargs_keeps_pywebview_default_storage_behavior():
    kwargs = build_webview_start_kwargs(
        gui="winforms",
        storage_path="D:/github/zaimanhua-desktop-suite/cache/pywebview",
    )

    assert kwargs == {"gui": "winforms"}
