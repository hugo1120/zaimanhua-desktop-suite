import inspect

from zaimanhua.core.desktop_api import DesktopApi


def _collect_exposed_function_names(obj):
    exposed_objects = []
    names = []

    def _walk(target, base_name=""):
        if target in exposed_objects:
            return
        exposed_objects.append(target)

        for name in dir(target):
            if name.startswith("_"):
                continue

            full_name = f"{base_name}.{name}" if base_name else name
            attr = getattr(target, name)
            if inspect.ismethod(attr):
                names.append(full_name)
            elif inspect.isclass(attr) or (
                isinstance(attr, object) and not callable(attr) and hasattr(attr, "__module__")
            ):
                _walk(attr, full_name)

    _walk(obj)
    return names


def test_desktop_api_only_exposes_explicit_methods():
    api = DesktopApi(
        settings_service=object(),
        desktop_log_fn=lambda *_args, **_kwargs: None,
        wait_for_window_handle_fn=lambda *_args, **_kwargs: 1,
        apply_window_titlebar_theme_fn=lambda *_args, **_kwargs: None,
    )
    api._window = object()

    assert sorted(_collect_exposed_function_names(api)) == ["log_debug", "set_theme"]


def test_desktop_api_set_theme_uses_private_dependencies():
    calls = []

    class FakeSettingsService:
        def set_theme_mode(self, theme_mode: str):
            calls.append(("persist", theme_mode))
            return theme_mode

    class FakeWindow:
        def __init__(self):
            self.native = object()

    api = DesktopApi(
        settings_service=FakeSettingsService(),
        desktop_log_fn=lambda component, event, **details: calls.append((component, event, details)),
        wait_for_window_handle_fn=lambda window, timeout_seconds=2.0: 4242,
        apply_window_titlebar_theme_fn=lambda hwnd, is_dark: calls.append(("apply", hwnd, is_dark)),
    )
    api._window = FakeWindow()

    api.set_theme(True)

    assert ("persist", "dark") in calls
    assert ("apply", 4242, True) in calls
