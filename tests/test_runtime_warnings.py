import warnings

import urllib3

from zaimanhua.core.runtime_warnings import configure_runtime_warnings


def test_configure_runtime_warnings_disables_expected_warning_categories(monkeypatch):
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        urllib3,
        "disable_warnings",
        lambda category: calls.append(("urllib3", category)),
    )
    monkeypatch.setattr(
        warnings,
        "filterwarnings",
        lambda action, category=None, **kwargs: calls.append(("warnings", action, category)),
    )

    configure_runtime_warnings()

    assert calls == [
        ("urllib3", urllib3.exceptions.InsecureRequestWarning),
        ("warnings", "ignore", DeprecationWarning),
    ]
