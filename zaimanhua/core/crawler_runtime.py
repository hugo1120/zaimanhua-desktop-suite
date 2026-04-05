from __future__ import annotations

import os
import sys


if getattr(sys, "frozen", False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", SCRIPT_DIR)
else:
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    BUNDLE_DIR = SCRIPT_DIR

MANGA_LIST_FILE = os.path.join(SCRIPT_DIR, "manga_list.txt")
MANGA_LIST_FILE_BUNDLE = os.path.join(BUNDLE_DIR, "manga_list.txt")
CRAWLER_MAX_WORKERS = 20
CRAWLER_SAVE_INTERVAL = 100
