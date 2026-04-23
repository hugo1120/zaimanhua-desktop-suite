from __future__ import annotations

import concurrent.futures
import os
import threading
import time
from pathlib import Path

import requests

from zaimanhua.core.crawler_runtime import CRAWLER_MAX_WORKERS, CRAWLER_SAVE_INTERVAL, MANGA_LIST_FILE
from zaimanhua.services.api import CustomSSLAdapter

class MangaCrawler:
    """内嵌的漫画索引爬虫，用于更新 manga_list.txt"""

    def __init__(self, callback=None, stop_event=None, manga_list_file: str | None = None):
        self.base_url = 'https://v4api.zaimanhua.com/app/v1'
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount('https://', CustomSSLAdapter())
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36', 'Accept': 'application/json'})
        self.existing_data = {}
        self.new_data = []
        self.lock = threading.Lock()
        self.processed_count = 0
        self.discovered_count = 0
        self.request_error_count = 0
        self.first_request_error = ''
        self.callback = callback
        self.stop_event = stop_event or threading.Event()
        self.manga_list_file = str(Path(manga_list_file or MANGA_LIST_FILE))

    def load_existing_data(self):
        """读取现有 TXT，建立缓存用于去重"""
        if os.path.exists(self.manga_list_file):
            try:
                print(f'正在读取现有文件: {self.manga_list_file} ...')
                if self.callback:
                    self.callback(f'正在读取现有文件...')
                with open(self.manga_list_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        if '|' in line:
                            parts = [p.strip() for p in line.split('|')]
                            mid_str = parts[0]
                            if mid_str.isdigit():
                                mid = int(mid_str)
                                title = parts[1] if len(parts) > 1 else ''
                                author = parts[2] if len(parts) > 2 else ''
                                self.existing_data[mid] = {'title': title, 'author': author}
                print(f'已加载 {len(self.existing_data)} 条现有数据')
                if self.callback:
                    self.callback(f'已加载 {len(self.existing_data)} 条现有数据')
                if self.existing_data:
                    return max(self.existing_data.keys())
            except Exception as e:
                print(f'读取 TXT 失败: {e}')
        return 0

    def get_manga_info(self, manga_id):
        """请求 API 获取标题和作者"""
        url = f'{self.base_url}/comic/detail/{manga_id}?_v=2.2.5'
        try:
            res = self.session.get(url, verify=False, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get('errno') == 0:
                    payload = data.get('data') or {}
                    d = payload.get('data') or {}
                    title = d.get('title')
                    authors = []
                    for a in d.get('authors') or []:
                        if 'tag_name' in a:
                            authors.append(a['tag_name'])
                    author_str = ','.join(authors)
                    if title:
                        return (title, author_str)
        except Exception as exc:
            with self.lock:
                self.request_error_count += 1
                if not self.first_request_error:
                    self.first_request_error = f'{type(exc).__name__}: {exc}'
        return (None, None)

    def worker(self, manga_id):
        """线程工作函数"""
        if self.stop_event.is_set():
            return
        title, author = self.get_manga_info(manga_id)
        with self.lock:
            self.processed_count += 1
            if self.processed_count % 50 == 0:
                msg = f'进度: 已处理 {self.processed_count} 个任务...'
                print(msg)
                if self.callback:
                    self.callback(msg)
            if title:
                print(f'发现: ID {manga_id} -> {title} [{author}]')
                self.discovered_count += 1
                self.new_data.append({'ID': manga_id, 'Title': title, 'Author': author})
                if len(self.new_data) >= CRAWLER_SAVE_INTERVAL:
                    self.save_to_txt()

    def save_to_txt(self):
        """保存数据到 TXT"""
        if not self.new_data:
            return
        print(f'正在保存数据到 {self.manga_list_file}...')
        if self.callback:
            self.callback('正在保存数据...')
        try:
            all_data = self.existing_data.copy()
            for item in self.new_data:
                all_data[item['ID']] = {'title': item['Title'], 'author': item['Author']}
            sorted_ids = sorted(all_data.keys())
            with open(self.manga_list_file, 'w', encoding='utf-8') as f:
                for mid in sorted_ids:
                    info = all_data[mid]
                    f.write(f"{mid} | {info['title']} | {info['author']}\n")
            self.existing_data = all_data
            self.new_data = []
            print('保存成功！')
            if self.callback:
                self.callback('保存成功！')
        except Exception as e:
            print(f'保存失败: {e}')
            if self.callback:
                self.callback(f'保存失败: {e}')

    def run(self, start_id, end_id):
        """运行爬虫"""
        max_id = self.load_existing_data()
        if start_id > end_id:
            print('起始 ID 不能大于结束 ID')
            return
        print('正在生成任务队列...')
        all_ids = range(start_id, end_id + 1)
        tasks = [i for i in all_ids if i not in self.existing_data]
        msg = f'范围: {start_id}-{end_id} | 总数: {len(all_ids)} | 跳过: {len(all_ids) - len(tasks)} | 待抓取: {len(tasks)}'
        print(msg)
        if self.callback:
            self.callback(msg)
        if not tasks:
            print('所有 ID 均已存在，无需更新！')
            if self.callback:
                self.callback('所有 ID 均已存在，无需更新！')
            return
        print(f'启动 {CRAWLER_MAX_WORKERS} 个线程开始抓取...')
        if self.callback:
            self.callback(f'启动 {CRAWLER_MAX_WORKERS} 个线程...')
        start_time = time.time()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=CRAWLER_MAX_WORKERS) as executor:
                futures = {executor.submit(self.worker, mid): mid for mid in tasks}
                for future in concurrent.futures.as_completed(futures):
                    if self.stop_event.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
        except KeyboardInterrupt:
            print('用户中断！正在保存已抓取的数据...')
        finally:
            self.save_to_txt()
            elapsed = time.time() - start_time
            if self.stop_event.is_set():
                msg = f'索引更新已停止！耗时: {elapsed:.2f}秒'
            elif self.discovered_count == 0 and self.request_error_count > 0:
                msg = (
                    f'索引更新失败: 共 {self.request_error_count} 次请求异常，'
                    f'首个错误: {self.first_request_error}'
                )
            else:
                msg = f'任务结束！耗时: {elapsed:.2f}秒'
            print(msg)
            if self.callback:
                self.callback(msg)
