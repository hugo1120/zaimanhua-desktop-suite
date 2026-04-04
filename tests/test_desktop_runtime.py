from zaimanhua.core.desktop_runtime import wait_for_tcp_port, wait_for_window_handle


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
