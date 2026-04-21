from __future__ import annotations

import warnings

import urllib3


def configure_runtime_warnings() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
