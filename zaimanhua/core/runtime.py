from __future__ import annotations

import concurrent.futures
import os
import threading
import tkinter as tk
import warnings

import customtkinter as ctk
from PIL import Image, ImageTk
from zaimanhua.core.runtime_warnings import configure_runtime_warnings
from zaimanhua.core.crawler_runtime import (
    BUNDLE_DIR,
    CRAWLER_MAX_WORKERS,
    CRAWLER_SAVE_INTERVAL,
    MANGA_LIST_FILE,
    MANGA_LIST_FILE_BUNDLE,
    SCRIPT_DIR,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
configure_runtime_warnings()

CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
LIBRARY_CACHE_FILE = os.path.join(SCRIPT_DIR, "library_cache.json")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")
COMPLETED_DIR = os.path.join(SCRIPT_DIR, "已完结")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
RECENT_UPDATES_CACHE_FILE = os.path.join(CACHE_DIR, "recent_updates_page1.json")
RECENT_COVER_CACHE_DIR = os.path.join(CACHE_DIR, "recent_covers")
ICON_FILE_NAME = "favicon.ico"
IMAGE_LOADER = concurrent.futures.ThreadPoolExecutor(max_workers=8)
RECENT_IMAGE_LOADER = concurrent.futures.ThreadPoolExecutor(max_workers=6)
IMAGE_DOWNLOAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=24)
SEARCH_DETAIL_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
COVER_CACHE = {}
COVER_CACHE_LOCK = threading.Lock()
MANGA_INDEX = {}
MANGA_INDEX_LOADED = False
WINDOW_ICON_PHOTO = None

THEME = {
    "primary": "#6366F1",
    "primary_hover": "#4F46E5",
    "success": "#10B981",
    "success_hover": "#059669",
    "warning": "#F59E0B",
    "warning_hover": "#D97706",
    "danger": "#EF4444",
    "danger_hover": "#DC2626",
    "purple": "#8B5CF6",
    "purple_hover": "#7C3AED",
    "orange": "#F97316",
    "teal": "#14B8A6",
    "card_bg": ("gray92", "gray18"),
    "card_hover": ("gray88", "gray22"),
    "toolbar_bg": ("white", "gray20"),
}


def resolve_icon_path():
    icon_path = os.path.join(SCRIPT_DIR, ICON_FILE_NAME)
    if os.path.exists(icon_path):
        return icon_path
    bundle_icon_path = os.path.join(BUNDLE_DIR, ICON_FILE_NAME)
    if os.path.exists(bundle_icon_path):
        return bundle_icon_path
    return ""


def apply_window_icon(window):
    icon_path = resolve_icon_path()
    if not icon_path:
        return

    def _apply_icon_now():
        global WINDOW_ICON_PHOTO
        if not window.winfo_exists():
            return
        if getattr(window, "_icon_applied_path", None) == icon_path:
            return
        try:
            window.iconbitmap(default=icon_path)
        except Exception:
            pass
        try:
            window.iconbitmap(icon_path)
        except Exception:
            pass
        try:
            if WINDOW_ICON_PHOTO is None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    icon_image = Image.open(icon_path)
                WINDOW_ICON_PHOTO = ImageTk.PhotoImage(icon_image)
            is_root_window = getattr(window, "_w", "") == "."
            window.iconphoto(is_root_window, WINDOW_ICON_PHOTO)
        except Exception:
            pass
        window._icon_applied_path = icon_path

    try:
        _apply_icon_now()
    except Exception:
        pass
    try:
        window.after_idle(_apply_icon_now)
    except Exception:
        pass
    for delay_ms in (100, 300):
        try:
            window.after(delay_ms, _apply_icon_now)
        except Exception:
            pass
    if not getattr(window, "_icon_map_binding_added", False):
        try:
            window.bind("<Map>", lambda _event: getattr(window, "_icon_applied_path", None) != icon_path and window.after(0, _apply_icon_now), add="+")
            window._icon_map_binding_added = True
        except Exception:
            pass

def load_manga_index():
    """启动时一次性加载 manga_list.txt 到内存（约 3.7MB -> 字典查询 O(1)）"""
    global MANGA_INDEX, MANGA_INDEX_LOADED
    if MANGA_INDEX_LOADED:
        return
    list_path = MANGA_LIST_FILE
    if not os.path.exists(list_path) and MANGA_LIST_FILE_BUNDLE != list_path:
        list_path = MANGA_LIST_FILE_BUNDLE
    if not os.path.exists(list_path):
        MANGA_INDEX_LOADED = True
        return
    try:
        with open(list_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '|' not in line:
                    continue
                parts = [p.strip() for p in line.split('|')]
                mid = parts[0]
                title = parts[1] if len(parts) > 1 else ''
                author = parts[2] if len(parts) > 2 else ''
                MANGA_INDEX[mid] = {'title': title, 'author': author}
        MANGA_INDEX_LOADED = True
        print(f'[性能] 已加载 {len(MANGA_INDEX)} 条漫画索引到内存')
    except Exception as e:
        print(f'[性能] 加载索引失败: {e}')
