from __future__ import annotations

import json
import os
import re

from zaimanhua.core import runtime

GEOMETRY_RE = re.compile(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)")


def parse_geometry_string(geometry_value):
    if not geometry_value:
        return None
    match = GEOMETRY_RE.match(str(geometry_value))
    if not match:
        return None
    return tuple(int(match.group(index)) for index in range(1, 5))


def read_config_file():
    if os.path.exists(runtime.CONFIG_FILE):
        try:
            with open(runtime.CONFIG_FILE, 'r', encoding='utf-8') as file_obj:
                return json.load(file_obj)
        except Exception:
            return {}
    return {}


def write_config_file(data):
    with open(runtime.CONFIG_FILE, 'w', encoding='utf-8') as file_obj:
        json.dump(data, file_obj, ensure_ascii=False)


def sanitize_window_geometry(widget, width, height, x=None, y=None, min_width=320, min_height=240):
    try:
        widget.update_idletasks()
    except Exception:
        pass
    screen_width = max(int(widget.winfo_screenwidth()), min_width)
    screen_height = max(int(widget.winfo_screenheight()), min_height)
    width = max(min_width, min(int(width or min_width), max(min_width, screen_width - 80)))
    height = max(min_height, min(int(height or min_height), max(min_height, screen_height - 120)))
    if x is None or y is None:
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
    else:
        x = int(x)
        y = int(y)
        if x >= screen_width - 40 or y >= screen_height - 40 or x + 40 <= 0 or y + 40 <= 0:
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
        else:
            x = min(max(x, 0), max(0, screen_width - width))
            y = min(max(y, 0), max(0, screen_height - height - 40))
    return width, height, x, y


def center_geometry_to_parent(widget, parent, width, height, min_width=320, min_height=240):
    width, height, _, _ = sanitize_window_geometry(widget, width, height, None, None, min_width, min_height)
    if parent and parent.winfo_exists():
        try:
            parent.update_idletasks()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_width = max(parent.winfo_width(), width)
            parent_height = max(parent.winfo_height(), height)
            return sanitize_window_geometry(widget, width, height, parent_x + max(0, (parent_width - width) // 2), parent_y + max(0, (parent_height - height) // 2), min_width, min_height)
        except Exception:
            pass
    return sanitize_window_geometry(widget, width, height, None, None, min_width, min_height)


def apply_window_geometry(widget, width, height, x, y):
    widget.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")


def extract_widget_geometry(widget):
    geometry_value = parse_geometry_string(widget.geometry())
    if geometry_value:
        return geometry_value
    return (max(widget.winfo_width(), widget.winfo_reqwidth()), max(widget.winfo_height(), widget.winfo_reqheight()), widget.winfo_x(), widget.winfo_y())


def save_widget_geometry(widget, key_prefix):
    try:
        if hasattr(widget, 'state') and widget.state() != 'normal':
            return
    except Exception:
        pass
    try:
        width, height, x, y = extract_widget_geometry(widget)
        data = read_config_file()
        data[f'{key_prefix}_width'] = width
        data[f'{key_prefix}_height'] = height
        data[f'{key_prefix}_x'] = x
        data[f'{key_prefix}_y'] = y
        if key_prefix == 'window':
            data['win_geometry'] = f'{width}x{height}+{x}+{y}'
        write_config_file(data)
    except Exception as exc:
        print(f'保存窗口布局失败({key_prefix}): {exc}')


def clamp_splitter_position(total_width, sash_x, min_left=0, min_right=0):
    total_width = max(int(total_width or 0), 1)
    min_left = max(int(min_left or 0), 0)
    min_right = max(int(min_right or 0), 0)
    min_x = min(min_left, max(total_width - min_right, 0))
    max_x = max(total_width - min_right, 0)
    try:
        sash_x = int(sash_x)
    except (TypeError, ValueError):
        sash_x = min_x
    return min(max(sash_x, min_x), max_x)


def resolve_splitter_position(total_width, stored_x=None, stored_ratio=None, min_left=0, min_right=0, default_ratio=0.5):
    total_width = max(int(total_width or 0), 1)
    target_x = None
    if stored_ratio is not None:
        try:
            ratio = float(stored_ratio)
        except (TypeError, ValueError):
            ratio = None
        if ratio is not None and 0.0 < ratio < 1.0:
            target_x = int(total_width * ratio)
    if target_x is None and stored_x is not None:
        try:
            target_x = int(stored_x)
        except (TypeError, ValueError):
            target_x = None
    if target_x is None:
        target_x = int(total_width * float(default_ratio))
    return clamp_splitter_position(total_width, target_x, min_left, min_right)


def save_splitter_position(key_prefix, sash_x, total_width):
    try:
        sash_x = int(sash_x)
        total_width = max(int(total_width or 0), 1)
    except (TypeError, ValueError):
        return
    data = read_config_file()
    data[f'{key_prefix}_sash_x'] = sash_x
    data[f'{key_prefix}_sash_ratio'] = round(sash_x / total_width, 6)
    write_config_file(data)


def post_init_center_dialog(window, master, min_width=300, min_height=200):
    try:
        window.update_idletasks()
        width = max(window.winfo_width(), window.winfo_reqwidth(), min_width)
        height = max(window.winfo_height(), window.winfo_reqheight(), min_height)
        width, height, x, y = center_geometry_to_parent(window, master, width, height, min_width, min_height)
        apply_window_geometry(window, width, height, x, y)
        if master and master.winfo_exists():
            window.transient(master)
        window.lift()
    except Exception:
        pass
