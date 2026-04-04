from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import tempfile
import threading
import time
import zipfile
from typing import Callable

from zaimanhua.core.manga_metadata import coerce_int, extract_latest_chapter, format_update_text
from zaimanhua.services.api import ZaimanhuaAPI


def _resolve_script_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SCRIPT_DIR = _resolve_script_dir()
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")


def _resolve_queue_file(download_dir: str | None = None) -> str:
    base_download_dir = os.path.abspath(download_dir or DOWNLOAD_DIR)
    return os.path.join(os.path.dirname(base_download_dir), "queue.json")


class DownloadTask:

    def __init__(self, manga_id, title=None, cover="", generation=0):
        self.id = str(manga_id)
        self.title = title
        self.cover = cover
        self.generation = generation
        self.status = 'waiting'
        self.progress = 0.0
        self.message = '排队中...'
        self.total_chapters = 0
        self.done_chapters = 0
        self.failed_chapters = 0
        self.stop_event = threading.Event()


class DownloadCanceledError(Exception):
    pass


class DownloadFailedError(Exception):
    pass


class DownloadManager:

    def __init__(self, api: ZaimanhuaAPI, ui_callback: Callable, download_dir: str | None = None):
        self.api = api
        self.ui_callback = ui_callback
        self.download_dir = os.path.abspath(download_dir or DOWNLOAD_DIR)
        self.max_books = 1
        self.max_images = 5
        self.waiting_list = []
        self.waiting_ids = set()
        self.active_tasks = []
        self.active_ids = set()
        self.state_lock = threading.Lock()
        self.stop_flag = threading.Event()
        self._scheduler_stop_event = threading.Event()
        self._close_lock = threading.Lock()
        self._executors_closed = False
        self._active_book_futures = set()
        self._book_executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        self._image_executor = concurrent.futures.ThreadPoolExecutor(max_workers=24)
        self.current_generation = 0
        self.is_closed = False
        self._queue_file = _resolve_queue_file(self.download_dir)
        self._load_queue()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def _save_queue(self):
        try:
            with self.state_lock:
                all_tasks = self.active_tasks + self.waiting_list
                data = []
                for t in all_tasks:
                    data.append({
                        "id": t.id,
                        "title": t.title,
                        "cover": getattr(t, "cover", ""),
                    })
            os.makedirs(os.path.dirname(self._queue_file), exist_ok=True)
            with open(self._queue_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存队列失败: {e}")

    def _load_queue(self):
        if not os.path.exists(self._queue_file):
            return
        try:
            with open(self._queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for item in data:
                manga_id = item.get("id")
                title = item.get("title")
                cover = item.get("cover", "")
                if manga_id:
                    task = DownloadTask(manga_id, title, cover=cover, generation=self.current_generation)
                    self.waiting_list.append(task)
                    self.waiting_ids.add(task.id)
        except Exception as e:
            print(f"加载队列失败: {e}")

    def set_concurrency(self, books, images):
        self.max_books = int(books)
        self.max_images = int(images)
        print(f'并发设置更新: 书籍={self.max_books}, 图片={self.max_images}')

    def stop_all_tasks(self):
        self.stop_flag.set()
        with self.state_lock:
            self.current_generation += 1
            waiting_tasks = list(self.waiting_list)
            active_tasks = list(self.active_tasks)
            self.waiting_list.clear()
            self.waiting_ids.clear()
        summary = {
            "waiting_canceled": len(waiting_tasks),
            "active_stopping": len(active_tasks),
        }
        self._save_queue()
        for task in waiting_tasks:
            task.stop_event.set()
            task.status = 'canceled'
            task.message = '已取消'
            self.ui_callback('task_canceled', task)
        for task in active_tasks:
            task.stop_event.set()
            task.status = 'stopping'
            task.message = '正在停止...'
            self.ui_callback('progress', task)
        self.ui_callback('queue_changed', None)
        self.ui_callback('stop_all', summary)
        return summary

    def add_task(self, manga_id, title=None, cover=""):
        if self.is_closed:
            return False
        if self.stop_flag.is_set():
            self.stop_flag.clear()
        with self.state_lock:
            task = DownloadTask(manga_id, title, cover=cover, generation=self.current_generation)
            if task.id in self.waiting_ids or task.id in self.active_ids:
                return False
            self.waiting_list.append(task)
            self.waiting_ids.add(task.id)
        self._save_queue()
        self.ui_callback('task_added', task)
        self.ui_callback('queue_changed', None)
        return True

    def cancel_task(self, task):
        task.stop_event.set()
        waiting_canceled = False
        active_stopping = False
        with self.state_lock:
            if task in self.waiting_list:
                self.waiting_list.remove(task)
                self.waiting_ids.discard(task.id)
                task.status = 'canceled'
                task.message = '已取消'
                waiting_canceled = True
            elif task.id in self.active_ids:
                task.status = 'stopping'
                task.message = '正在停止...'
                active_stopping = True
            else:
                return False
        if waiting_canceled:
            self._save_queue()
            self.ui_callback('queue_changed', None)
            self.ui_callback('task_canceled', task)
            return True
        if active_stopping:
            self.ui_callback('progress', task)
            return True
        return False

    def get_waiting_tasks(self):
        with self.state_lock:
            return list(self.waiting_list)

    def get_all_tasks(self):
        with self.state_lock:
            return list(self.active_tasks) + list(self.waiting_list)

    def get_task(self, task_id):
        target_id = str(task_id)
        with self.state_lock:
            for task in self.active_tasks:
                if task.id == target_id:
                    return task
            for task in self.waiting_list:
                if task.id == target_id:
                    return task
        return None

    def get_queue_size(self):
        with self.state_lock:
            return len(self.waiting_list)

    def get_active_size(self):
        with self.state_lock:
            return len(self.active_ids)

    def _finish_active_task(self, task):
        with self.state_lock:
            self.active_ids.discard(task.id)
            if task in self.active_tasks:
                self.active_tasks.remove(task)

    def _raise_if_stopped(self, task):
        if self.stop_flag.is_set() or task.stop_event.is_set():
            raise DownloadCanceledError('任务已取消')

    def _on_book_future_done(self, future: concurrent.futures.Future):
        with self.state_lock:
            self._active_book_futures.discard(future)

    def _scheduler_loop(self):
        futures = []
        try:
            while not self._scheduler_stop_event.is_set():
                futures = [f for f in futures if not f.done()]
                if self.get_active_size() < self.max_books and (not self.stop_flag.is_set()):
                    task = None
                    with self.state_lock:
                        if self.waiting_list:
                            task = self.waiting_list.pop(0)
                            self.waiting_ids.discard(task.id)
                    if task:
                        if self.stop_flag.is_set():
                            task.status = 'canceled'
                            task.message = '已取消'
                            continue
                        with self.state_lock:
                            self.active_tasks.append(task)
                            self.active_ids.add(task.id)
                        future = self._book_executor.submit(self._process_book, task, self.max_images)
                        with self.state_lock:
                            self._active_book_futures.add(future)
                        future.add_done_callback(self._on_book_future_done)
                        futures.append(future)
                        self.ui_callback('queue_changed', None)
                    else:
                        time.sleep(0.2)
                else:
                    time.sleep(0.3)
        finally:
            self._shutdown_executors()

    def _shutdown_executors(self):
        with self._close_lock:
            if self._executors_closed:
                return
            self._executors_closed = True
            executors = (self._book_executor, self._image_executor)
        for executor in executors:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def _process_book(self, task: DownloadTask, img_concurrency: int):
        task.status = 'downloading'
        task.message = '获取信息...'
        self.ui_callback('progress', task)
        try:
            self._raise_if_stopped(task)
            detail = self.api.get_manga_detail(task.id)
            if not detail or detail.get('errno') != 0:
                raise Exception('API Fail')
            self._raise_if_stopped(task)
            data = detail['data']['data']
            real_title = data.get('title', task.title or '未知漫画')
            task.title = real_title
            safe_name = self.api._sanitize(real_title)
            manga_dir = os.path.join(self.download_dir, safe_name)
            os.makedirs(manga_dir, exist_ok=True)
            info_path = os.path.join(manga_dir, 'info.json')
            status_label = self.api.get_status_label(data.get('status', []))
            existing_data = {}
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception:
                    pass
            raw_author = data.get('authors', [])
            author_text = ''
            if isinstance(raw_author, list):
                author_text = ','.join([str(a.get('tag_name', '')) for a in raw_author if isinstance(a, dict)])
            elif isinstance(raw_author, str):
                author_text = raw_author
            original_info = dict(existing_data)
            last_update_ts = coerce_int(data.get('last_updatetime'), coerce_int(existing_data.get('last_update_ts'), 0))
            latest_chapter = extract_latest_chapter(data) or str(existing_data.get('latest_chapter', '') or '')
            existing_data.update(
                {
                    'id': str(task.id),
                    'title': real_title,
                    'author': author_text,
                    'status': status_label,
                    'description': str(data.get('description', '') or ''),
                    'last_update_ts': last_update_ts,
                    'last_update_text': format_update_text(last_update_ts),
                    'latest_chapter': latest_chapter,
                }
            )
            cover_url = data.get('cover')
            if cover_url:
                cover_name = f'{task.id}_{safe_name}_cover.jpg'
                self.api.download_cover(cover_url, manga_dir, cover_name)
                # 关键修复：存储相对路径，确保前端能通过 /api/covers 加载
                task.cover = f"{safe_name}/{cover_name}"
                self.ui_callback('progress', task)
            existing_data.pop('cover_path', None)
            if existing_data != original_info:
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
            chapters = []
            for group in data.get('chapters', []):
                g_title = group.get('title', '')
                for ch in group.get('data', []):
                    chapter_title = ch.get('chapter_title', '')
                    full_title = chapter_title if g_title == '连载' else f'{g_title}-{chapter_title}'
                    chapters.append({'title': full_title, 'id': ch.get('chapter_id')})
            task.total_chapters = len(chapters)
            if task.total_chapters == 0:
                raise Exception('无章节')
            task.done_chapters = 0
            task.failed_chapters = 0
            chapter_failures = []
            for ch in chapters:
                self._raise_if_stopped(task)
                chapter_title = self.api._sanitize(ch['title'])
                cbz_path = os.path.join(manga_dir, f'{safe_name}_{chapter_title}.cbz')
                task.message = f'下载: {chapter_title}'
                self.ui_callback('progress', task)
                if os.path.exists(cbz_path):
                    task.done_chapters += 1
                else:
                    try:
                        self._download_chapter_images(task, task.id, ch['id'], cbz_path, img_concurrency)
                    except DownloadFailedError as exc:
                        task.failed_chapters += 1
                        chapter_failures.append(f'{chapter_title}: {exc}')
                        task.message = f'失败: {chapter_title}'
                    finally:
                        task.done_chapters += 1
                task.progress = task.done_chapters / task.total_chapters
                self.ui_callback('progress', task)
            if task.failed_chapters >= task.total_chapters and chapter_failures:
                raise DownloadFailedError(f'全部章节下载失败，首个失败原因：{chapter_failures[0]}')
            task.status = 'finished'
            if task.failed_chapters:
                task.message = f'⚠️ 完成，失败 {task.failed_chapters} 话'
            else:
                task.message = '✅ 完成'
            self.ui_callback('task_finish', task)
        except DownloadCanceledError:
            task.status = 'canceled'
            task.message = '已取消'
            self.ui_callback('task_canceled', task)
        except Exception as e:
            task.status = 'error'
            task.message = f'❌ {str(e)}'
            self.ui_callback('task_error', task)
        finally:
            self._finish_active_task(task)
            self.ui_callback('queue_changed', None)

    def close(self, join_timeout: float = 1.0):
        if self.is_closed:
            return
        self.is_closed = True
        self._scheduler_stop_event.set()
        self.stop_flag.set()
        safe_timeout = max(0.01, float(join_timeout))
        with self.state_lock:
            waiting_tasks = list(self.waiting_list)
            active_tasks = list(self.active_tasks)
            self.waiting_list.clear()
            self.waiting_ids.clear()
        for task in waiting_tasks:
            task.stop_event.set()
            task.status = 'canceled'
            task.message = '已取消'
        for task in active_tasks:
            task.stop_event.set()
            task.status = 'stopping'
            task.message = '正在停止...'
        try:
            self._scheduler_thread.join(timeout=safe_timeout)
        except Exception:
            pass
        with self.state_lock:
            active_book_futures = list(self._active_book_futures)
        if active_book_futures:
            try:
                concurrent.futures.wait(active_book_futures, timeout=safe_timeout)
            except Exception:
                pass
        self._shutdown_executors()

    def _download_chapter_images(self, task: DownloadTask, mid, cid, cbz_path, concurrency):
        self._raise_if_stopped(task)
        c_res = self.api.get_chapter_images(mid, cid)
        if not c_res or c_res.get('errno') != 0:
            errmsg = ''
            if isinstance(c_res, dict):
                errmsg = c_res.get('errmsg', '')
            raise DownloadFailedError(errmsg or f'章节接口返回异常: {cid}')
        self._raise_if_stopped(task)
        chapter_data = c_res.get('data', {}).get('data', {})
        urls = chapter_data.get('page_url') or chapter_data.get('page_url_hd') or []
        if not urls:
            raise DownloadFailedError('章节图片列表为空')
        with tempfile.TemporaryDirectory() as tmp:
            img_paths = [None] * len(urls)
            failed_indexes = []
            future_to_idx = {}
            max_pending = max(1, min(concurrency, self.max_images))
            next_idx = 0
            while next_idx < len(urls) or future_to_idx:
                self._raise_if_stopped(task)
                while next_idx < len(urls) and len(future_to_idx) < max_pending:
                    self._raise_if_stopped(task)
                    future = self._image_executor.submit(self.api.download_image_content, urls[next_idx])
                    future_to_idx[future] = next_idx
                    next_idx += 1
                done, _ = concurrent.futures.wait(future_to_idx, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    idx = future_to_idx.pop(future)
                    self._raise_if_stopped(task)
                    try:
                        data = future.result()
                        if data:
                            ext = self.api._get_image_extension(data, urls[idx])
                            path = os.path.join(tmp, f'{idx + 1:03d}{ext}')
                            with open(path, 'wb') as f:
                                f.write(data)
                            img_paths[idx] = path
                        else:
                            failed_indexes.append(idx + 1)
                    except Exception:
                        failed_indexes.append(idx + 1)
            self._raise_if_stopped(task)
            if failed_indexes:
                failed_indexes = sorted(set(failed_indexes))
                preview = ', '.join(str(index) for index in failed_indexes[:5])
                suffix = '...' if len(failed_indexes) > 5 else ''
                raise DownloadFailedError(f'图片下载不完整，缺少 {len(failed_indexes)} 张（页码: {preview}{suffix}）')
            valid_paths = [path for path in img_paths if path]
            if not valid_paths:
                raise DownloadFailedError('未下载到任何图片')
            with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for path in valid_paths:
                    self._raise_if_stopped(task)
                    zf.write(path, os.path.basename(path))
