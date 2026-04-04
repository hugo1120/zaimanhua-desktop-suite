from __future__ import annotations

import concurrent.futures
import hashlib
import io
import os
import threading

import customtkinter as ctk
import requests
from PIL import Image, ImageTk
from requests.adapters import HTTPAdapter

from zaimanhua.core import runtime

COVER_CACHE = runtime.COVER_CACHE
COVER_CACHE_LOCK = runtime.COVER_CACHE_LOCK
IMAGE_LOADER = runtime.IMAGE_LOADER
REMOTE_IMAGE_SESSION = requests.Session()
REMOTE_IMAGE_SESSION.trust_env = False
REMOTE_IMAGE_SESSION.mount('http://', HTTPAdapter(pool_connections=16, pool_maxsize=16))
REMOTE_IMAGE_SESSION.mount('https://', HTTPAdapter(pool_connections=16, pool_maxsize=16))
REMOTE_IMAGE_CACHE = {}
REMOTE_IMAGE_CACHE_LOCK = threading.Lock()
REMOTE_IMAGE_INFLIGHT = {}
REMOTE_IMAGE_INFLIGHT_LOCK = threading.Lock()
REMOTE_IMAGE_CACHE_MAX = 256

def _get_cached_cover(cache_key):
    with COVER_CACHE_LOCK:
        return COVER_CACHE.get(cache_key)


def _store_cached_cover(cache_key, image):
    with COVER_CACHE_LOCK:
        COVER_CACHE[cache_key] = image


def _remote_image_cache_key(url, size):
    return f'{size[0]}x{size[1]}:{url}'


def _remote_image_disk_path(url, size, disk_cache_dir):
    if not disk_cache_dir:
        return ''
    file_name = hashlib.md5(_remote_image_cache_key(url, size).encode('utf-8')).hexdigest() + '.png'
    return os.path.join(disk_cache_dir, file_name)


def _load_remote_image_from_disk(url, size, disk_cache_dir):
    cache_path = _remote_image_disk_path(url, size, disk_cache_dir)
    if not cache_path or (not os.path.exists(cache_path)):
        return None
    try:
        image = Image.open(cache_path)
        image.load()
        return image
    except Exception:
        return None


def _store_remote_image_to_disk(url, size, image, disk_cache_dir):
    cache_path = _remote_image_disk_path(url, size, disk_cache_dir)
    if not cache_path:
        return
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        image.save(cache_path, format='PNG')
    except Exception:
        pass


def _get_cached_remote_image(cache_key):
    with REMOTE_IMAGE_CACHE_LOCK:
        image = REMOTE_IMAGE_CACHE.get(cache_key)
        if image is None:
            return None
        REMOTE_IMAGE_CACHE.pop(cache_key, None)
        REMOTE_IMAGE_CACHE[cache_key] = image
        return image.copy()


def _store_cached_remote_image(cache_key, image):
    with REMOTE_IMAGE_CACHE_LOCK:
        REMOTE_IMAGE_CACHE.pop(cache_key, None)
        REMOTE_IMAGE_CACHE[cache_key] = image.copy()
        while len(REMOTE_IMAGE_CACHE) > REMOTE_IMAGE_CACHE_MAX:
            oldest_key = next(iter(REMOTE_IMAGE_CACHE))
            REMOTE_IMAGE_CACHE.pop(oldest_key, None)


def has_cached_remote_image(url, size):
    if not url:
        return False
    return _get_cached_remote_image(_remote_image_cache_key(url, size)) is not None


def has_disk_cached_remote_image(url, size, disk_cache_dir):
    if not url or not disk_cache_dir:
        return False
    return os.path.exists(_remote_image_disk_path(url, size, disk_cache_dir))


def get_remote_image_future(url, size, headers=None, timeout=5, disk_cache_dir=None, executor=None):
    if not url:
        future = concurrent.futures.Future()
        future.set_result(None)
        return future
    cache_key = _remote_image_cache_key(url, size)
    cached = _get_cached_remote_image(cache_key)
    if cached is not None:
        future = concurrent.futures.Future()
        future.set_result(cached)
        return future
    disk_cached = _load_remote_image_from_disk(url, size, disk_cache_dir)
    if disk_cached is not None:
        _store_cached_remote_image(cache_key, disk_cached)
        future = concurrent.futures.Future()
        future.set_result(disk_cached)
        return future
    with REMOTE_IMAGE_INFLIGHT_LOCK:
        future = REMOTE_IMAGE_INFLIGHT.get(cache_key)
        if future is not None:
            return future

        def _fetch():
            req_headers = headers or {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://manhua.zaimanhua.com/',
            }
            try:
                res = REMOTE_IMAGE_SESSION.get(url, headers=req_headers, timeout=timeout, verify=False)
                if res.status_code == 200:
                    image = Image.open(io.BytesIO(res.content))
                    image.load()
                    image.thumbnail(size, Image.Resampling.LANCZOS)
                    _store_cached_remote_image(cache_key, image)
                    _store_remote_image_to_disk(url, size, image, disk_cache_dir)
                    return image
            except Exception:
                return None
            return None

        image_executor = executor or IMAGE_LOADER
        future = image_executor.submit(_fetch)
        REMOTE_IMAGE_INFLIGHT[cache_key] = future

        def _cleanup(done_future):
            with REMOTE_IMAGE_INFLIGHT_LOCK:
                current = REMOTE_IMAGE_INFLIGHT.get(cache_key)
                if current is done_future:
                    REMOTE_IMAGE_INFLIGHT.pop(cache_key, None)

        future.add_done_callback(_cleanup)
        return future


def prefetch_remote_images(urls, size, headers=None, timeout=5, timeout_ms=None, disk_cache_dir=None, executor=None):
    future_map = {}
    for url in urls or []:
        if not url or url in future_map:
            continue
        future_map[url] = get_remote_image_future(url, size, headers=headers, timeout=timeout, disk_cache_dir=disk_cache_dir, executor=executor)
    if not future_map:
        return {}
    timeout_seconds = None
    if timeout_ms is not None:
        timeout_seconds = max(0.05, timeout_ms / 1000)
    done, pending = concurrent.futures.wait(list(future_map.values()), timeout=timeout_seconds)
    done_set = set(done)
    prefetched = {}
    for url, future in future_map.items():
        if future not in done_set:
            continue
        try:
            image = future.result()
        except Exception:
            image = None
        if image is not None:
            prefetched[url] = image
    for future in pending:
        future.cancel()
    return prefetched


def _apply_cached_cover(widget, label_widget, cache_key):
    cached = _get_cached_cover(cache_key)
    if cached and widget.winfo_exists():
        widget._cover_image = cached
        label_widget.configure(image=cached, text='')
        return True
    return False


def load_remote_cover_async(widget, label_widget, url, size, headers=None, timeout=5, cache_prefix='remote', on_ready=None, disk_cache_dir=None, executor=None):
    if not url:
        if on_ready:
            on_ready()
        return
    cache_key = f'{cache_prefix}:{size[0]}x{size[1]}:{url}'
    widget._expected_remote_cover_key = cache_key
    if _apply_cached_cover(widget, label_widget, cache_key):
        if on_ready:
            on_ready()
        return
    future = get_remote_image_future(url, size, headers=headers, timeout=timeout, disk_cache_dir=disk_cache_dir, executor=executor)

    def _done(done_future):
        try:
            img = done_future.result()
            if not widget.winfo_exists():
                if on_ready:
                    on_ready()
                return

            def _apply():
                if not widget.winfo_exists():
                    if on_ready:
                        on_ready()
                    return
                if getattr(widget, '_expected_remote_cover_key', None) != cache_key:
                    if on_ready:
                        on_ready()
                    return
                if img:
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    _store_cached_cover(cache_key, ctk_img)
                    _apply_cached_cover(widget, label_widget, cache_key)
                if on_ready:
                    on_ready()
            widget.after(0, _apply)
        except Exception:
            if on_ready and widget.winfo_exists():
                widget.after(0, on_ready)
    future.add_done_callback(_done)


def load_remote_cover_tk_async(widget, label_widget, url, size, headers=None, timeout=5, cache_prefix='remote-tk', on_ready=None, disk_cache_dir=None, executor=None):
    if not url:
        if on_ready:
            on_ready()
        return
    cache_key = f'{cache_prefix}:{size[0]}x{size[1]}:{url}'
    widget._expected_remote_cover_key = cache_key
    if _apply_cached_cover(widget, label_widget, cache_key):
        if on_ready:
            on_ready()
        return
    future = get_remote_image_future(url, size, headers=headers, timeout=timeout, disk_cache_dir=disk_cache_dir, executor=executor)

    def _done(done_future):
        try:
            img = done_future.result()
            if not widget.winfo_exists():
                if on_ready:
                    on_ready()
                return

            def _apply():
                if not widget.winfo_exists():
                    if on_ready:
                        on_ready()
                    return
                if getattr(widget, '_expected_remote_cover_key', None) != cache_key:
                    if on_ready:
                        on_ready()
                    return
                if img:
                    tk_img = ImageTk.PhotoImage(img)
                    _store_cached_cover(cache_key, tk_img)
                    _apply_cached_cover(widget, label_widget, cache_key)
                if on_ready:
                    on_ready()
            widget.after(0, _apply)
        except Exception:
            if on_ready and widget.winfo_exists():
                widget.after(0, on_ready)
    future.add_done_callback(_done)


def load_local_cover_async(widget, label_widget, path, size):
    if not path or not os.path.exists(path):
        return
    cache_key = f'local:{size[0]}x{size[1]}:{path}'
    if _apply_cached_cover(widget, label_widget, cache_key):
        return

    def _read():
        try:
            img = Image.open(path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
        except Exception:
            return None

    def _done(future):
        try:
            img = future.result()
            if not img or not widget.winfo_exists():
                return

            def _apply():
                if not widget.winfo_exists():
                    return
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                _store_cached_cover(cache_key, ctk_img)
                _apply_cached_cover(widget, label_widget, cache_key)
            widget.after(0, _apply)
        except Exception:
            pass
    IMAGE_LOADER.submit(_read).add_done_callback(_done)
