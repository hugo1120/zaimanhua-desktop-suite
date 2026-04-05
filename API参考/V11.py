import customtkinter as ctk
import sys
import requests
import hashlib
import json
import time
import os
import zipfile
import tempfile
import ssl
import urllib3
import warnings
import threading
import queue
import concurrent.futures
import subprocess
import platform
import shutil
import tkinter as tk
from typing import List, Dict, Any, Optional, Callable
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
# from bs4 import BeautifulSoup  # 延迟导入优化：移到 search_web_scrape 中
from tkinter import messagebox
from PIL import Image, ImageTk
import io

# ================= 配置与常量 =================
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 使用脚本所在目录作为基准路径
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', SCRIPT_DIR)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = SCRIPT_DIR
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")
COMPLETED_DIR = os.path.join(SCRIPT_DIR, "已完结")
MANGA_LIST_FILE = os.path.join(SCRIPT_DIR, "manga_list.txt")  # 本地数据库文件
MANGA_LIST_FILE_BUNDLE = os.path.join(BUNDLE_DIR, "manga_list.txt")
CRAWLER_MAX_WORKERS = 20  # 爬虫并发线程数
CRAWLER_SAVE_INTERVAL = 100  # 每抓取多少个保存一次
IMAGE_LOADER = concurrent.futures.ThreadPoolExecutor(max_workers=16)  # 全局图片加载线程池（增大并发）
COVER_CACHE = {}  # 封面缓存 {url: CTkImage}

# ================= 性能优化：全局索引缓存 =================
MANGA_INDEX = {}  # 内存缓存 {id: {'title': str, 'author': str}}
MANGA_INDEX_LOADED = False  # 标记是否已加载

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
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                mid = parts[0]
                title = parts[1] if len(parts) > 1 else ""
                author = parts[2] if len(parts) > 2 else ""
                MANGA_INDEX[mid] = {'title': title, 'author': author}
        MANGA_INDEX_LOADED = True
        print(f"[性能] 已加载 {len(MANGA_INDEX)} 条漫画索引到内存")
    except Exception as e:
        print(f"[性能] 加载索引失败: {e}")

# ================= 主题颜色 =================
THEME = {
    "primary": "#6366F1",       # 主色调 - 靛蓝
    "primary_hover": "#4F46E5", # 主色调悬停
    "success": "#10B981",       # 成功 - 翠绿
    "success_hover": "#059669",
    "warning": "#F59E0B",       # 警告 - 琥珀
    "warning_hover": "#D97706",
    "danger": "#EF4444",        # 危险 - 红色
    "danger_hover": "#DC2626",
    "purple": "#8B5CF6",        # 紫色
    "purple_hover": "#7C3AED",
    "orange": "#F97316",        # 橙色
    "teal": "#14B8A6",          # 青色
    "card_bg": ("gray92", "gray18"),       # 卡片背景
    "card_hover": ("gray88", "gray22"),    # 卡片悬停
    "toolbar_bg": ("white", "gray20"),     # 工具栏背景
}

# ================= 1. 网络与 API 层 =================

class CustomSSLAdapter(HTTPAdapter):
    """强制兼容旧版 SSL 协议"""
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = create_urllib3_context()
        try: ctx.set_ciphers('ALL:@SECLEVEL=1')
        except: pass
        try: ctx.options |= 0x4
        except: pass
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx
        )

class ZaimanhuaAPI:
    def __init__(self):
        self.base_url = "https://v4api.zaimanhua.com/app/v1"
        self.account_url = "https://account-api.zaimanhua.com/v1"
        self.mobile_url = "https://m.zaimanhua.com"
        self.web_search_url = "https://manhua.zaimanhua.com/dynamic/"
        self.token = ""
        
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount('https://', CustomSSLAdapter())
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

    def _md5_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _get_headers(self, include_token: bool = True) -> Dict[str, str]:
        headers = self.session.headers.copy()
        if include_token and self.token:
            headers['authorization'] = f'Bearer {self.token}'
        return headers
    
    def login(self, username, password) -> bool:
        try:
            password_hashed = self._md5_hash(password)
            data = {'username': username, 'passwd': password_hashed}
            res = self.session.post(f"{self.account_url}/login/passwd", data=data, headers=self._get_headers(False), verify=False)
            if res.status_code == 200 and res.json().get('errno') == 0:
                self.token = res.json()['data']['user'].get('token', '')
                return True
        except Exception as e:
            print(f"登录错误: {e}")
        return False

    def get_manga_detail(self, manga_id: str) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/comic/detail/{manga_id}?_v=2.2.5"
            return self.session.get(url, headers=self._get_headers(), verify=False).json()
        except: return {}

    def search_api(self, keyword: str) -> List[Dict[str, str]]:
        """API 搜索 (V10 Feature)"""
        results = []
        try:
            url = f"{self.base_url}/search/comic?_v=2.2.5&limit=20&page=1&q={keyword}"
            res = self.session.get(url, headers=self._get_headers(), verify=False)
            if res.status_code == 200:
                data = res.json()
                if data.get('errno') == 0:
                    for item in data['data']['data']:
                        title = item.get('title')
                        mid = str(item.get('comic_id'))
                        cover = item.get('cover')
                        authors = [a.get('tag_name') for a in item.get('authors', [])]
                        author_str = ",".join(authors) if authors else ""
                        
                        if title and mid:
                            results.append({
                                "title": title,
                                "id": mid,
                                "author": author_str,
                                "source": "api",
                                "cover_url": cover
                            })
        except Exception as e:
            print(f"API Search Error: {e}")
        return results

    def search_web_scrape(self, keyword: str) -> List[Dict[str, str]]:
        """原有网页爬虫搜索 (保留作为 fallback)"""
        results = []
        clean_kw = keyword.replace("_", " ").strip()
        target_url = self.web_search_url + clean_kw
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://manhua.zaimanhua.com/'
            }
            res = requests.get(target_url, headers=headers, verify=False, timeout=10)
            res.encoding = 'utf-8'
            if res.status_code == 200:
                # 延迟导入 BeautifulSoup（性能优化：只在需要时才导入）
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('p.title > a[href^="/details/"]')
                count = 0
                for a in items:
                    if count >= 100: break
                    title = a.get('title', '').strip() or a.get_text().strip()
                    href = a.get('href', '')
                    mid = href.rstrip('/').split('/')[-1]
                    if title and mid:
                        if not any(d['id'] == mid for d in results):
                            results.append({"title": title, "id": mid, "source": "web"})
                            count += 1
        except Exception as e:
            print(f"Web Search Error: {e}")
        return results

    def search_dynamic(self, keyword: str) -> List[Dict[str, str]]:
        """解析网页搜索结果 + ID智能识别 + API优先"""
        results = []
        
        # 1. 尝试 ID 直达逻辑
        if keyword.isdigit():
            # 调用详情接口获取真实名字
            detail = self.get_manga_detail(keyword)
            if detail and detail.get('errno') == 0:
                real_title = detail['data']['data'].get('title', f"ID: {keyword}")
                results.append({"title": real_title, "id": keyword, "source": "id_match"})
            else:
                # 兜底：即便详情失败也给出可下载的 ID 项
                results.append({"title": f"ID: {keyword}", "id": keyword, "source": "id_guess"})

        # 2. API 搜索 (优先)
        api_results = self.search_api(keyword)
        if api_results:
            results.extend(api_results)
            
        # 3. 网页搜索 (Fallback / Supplement)
        # 只有当 API 结果少于 5 个或者完全没有时，才尝试网页搜索补充
        if not api_results:
             print("API returned no results, falling back to Web Scrape...")
             web_results = self.search_web_scrape(keyword)
             # 去重合并
             existing_ids = {r['id'] for r in results}
             for w in web_results:
                  if w['id'] not in existing_ids:
                      results.append(w)
        
        return results

    def get_chapter_images(self, manga_id: str, chapter_id: str) -> Dict[str, Any]:
        """获取章节图片列表 (参考 Tachiyomi 扩展实现)"""
        try:
            url = f"{self.base_url}/comic/chapter/{manga_id}/{chapter_id}?_v=2.2.5"
            # 添加 Platform: h5 请求头，与参考代码保持一致
            headers = self._get_headers()
            headers['Platform'] = 'h5'
            
            result = self.session.get(url, headers=headers, verify=False).json()
            
            # 权限检查 (参考代码: if (!result.data.data!!.canRead) throw Exception)
            data = result.get('data', {}).get('data', {})
            can_read = data.get('canRead', True)  # 注意: API 返回的是驼峰命名 canRead
            if can_read == False or can_read == 0:
                print(f"[权限不足] 章节 {chapter_id} 需要升级账号等级")
                return {'errno': -1, 'errmsg': '用户权限不足，请升级账号等级'}
            
            return result
        except Exception as e:
            print(f"获取章节图片失败: {e}")
            return {}

    def download_image_content(self, url: str) -> Optional[bytes]:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': self.mobile_url}
        for _ in range(3): # 重试3次
            try:
                res = self.session.get(url, headers=headers, timeout=15, verify=False)
                if res.status_code == 200: return res.content
            except: time.sleep(0.5)
        return None

    def _sanitize(self, name: str) -> str:
        return "".join([c if c not in '<>:"/\\|?*' else '_' for c in name]).strip()

    def download_cover(self, url: str, folder_path: str, filename: str):
        """下载封面并保存 (如果有过一次就不要在求封面了)"""
        if not url: return
        try:
            full_path = os.path.join(folder_path, filename)
            if os.path.exists(full_path): return # 已存在则跳过

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://manhua.zaimanhua.com/'
            }
            res = self.session.get(url, headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                with open(full_path, 'wb') as f:
                    f.write(res.content)
        except Exception as e:
            print(f"Cover download failed: {e}")


    def get_status_label(self, tags: list) -> str:
        """解析状态标签"""
        for t in tags:
            try:
                tid = int(t.get('tag_id', 0))
                if tid == 2310: return "已完结"
                if tid == 2309: return "连载中"
            except: pass
    def get_recent_updates(self, page: int = 1) -> List[Dict[str, Any]]:
        """获取最近更新 (V10 Feature)"""
        results = []
        try:
            # URL: https://v4api.zaimanhua.com/app/v1/comic/update/list/0/{page}
            url = f"{self.base_url}/comic/update/list/0/{page}"
            res = self.session.get(url, headers=self._get_headers(), verify=False)
            if res.status_code == 200:
                data = res.json()
                # data['data'] is a list of items
                # Item structure (based on probe/guess):
                # {
                #   "comic_id": 123, "id": 0, "title": "xxx", "authors": "xxx", 
                #   "status": "连载中", "cover": "url", "last_update_chapter_name": "第xx话", 
                #   "last_updatetime": timestamp
                # }
                # Note: 'authors' might be a string or list, need robustness. 
                # The reference code says 'latestUpdatesParse' maps to SManga. 
                
                # The update list API returns {"data": [...]} without errno
                raw_data = data.get('data')
                if raw_data:
                    for item in raw_data:
                        # Extraction
                        mid = item.get('comic_id')
                        # Fallback id
                        if not mid or mid == 0: mid = item.get('id')
                        
                        title = item.get('title', item.get('name', 'Unknown'))
                        cover = item.get('cover')
                        authors = item.get('authors', '') # simple string in update list usually
                        status = item.get('status', '')
                        
                        # Latest chapter info
                        last_ch = item.get('last_update_chapter_name', '')
                        
                        # Timestamp
                        ts = item.get('last_updatetime', 0)
                        import datetime
                        time_str = ""
                        if ts:
                            try:
                                dt = datetime.datetime.fromtimestamp(int(ts))
                                time_str = dt.strftime("%Y-%m-%d %H:%M")
                            except: pass
                            
                        results.append({
                            "id": str(mid),
                            "title": title,
                            "cover": cover,
                            "author": authors,
                            "status": status,
                            "latest": last_ch,
                            "time": time_str
                        })
        except Exception as e:
            print(f"Recent Updates Error: {e}")
        return results


# ================= 2. 内嵌爬虫模块 =================

class MangaCrawler:
    """内嵌的漫画索引爬虫，用于更新 manga_list.txt"""
    def __init__(self, callback=None, stop_event=None):
        self.base_url = "https://v4api.zaimanhua.com/app/v1"
        self.session = requests.Session()
        self.session.mount('https://', CustomSSLAdapter())
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        
        self.existing_data = {}  # {id: {'title': str, 'author': str}}
        self.new_data = []  # List of {'ID': int, 'Title': str, 'Author': str}
        self.lock = threading.Lock()
        self.processed_count = 0
        
        # UI 集成接口
        self.callback = callback  # function(msg)
        self.stop_event = stop_event or threading.Event()

    def load_existing_data(self):
        """读取现有 TXT，建立缓存用于去重"""
        if os.path.exists(MANGA_LIST_FILE):
            try:
                print(f"正在读取现有文件: {MANGA_LIST_FILE} ...")
                if self.callback: self.callback(f"正在读取现有文件...")
                with open(MANGA_LIST_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        if "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            mid_str = parts[0]
                            if mid_str.isdigit():
                                mid = int(mid_str)
                                title = parts[1] if len(parts) > 1 else ""
                                author = parts[2] if len(parts) > 2 else ""
                                self.existing_data[mid] = {'title': title, 'author': author}
                                    
                print(f"已加载 {len(self.existing_data)} 条现有数据")
                if self.callback: self.callback(f"已加载 {len(self.existing_data)} 条现有数据")
                
                # 返回最大 ID 以便自动后延
                if self.existing_data:
                    return max(self.existing_data.keys())
            except Exception as e:
                print(f"读取 TXT 失败: {e}")
        return 0

    def get_manga_info(self, manga_id):
        """请求 API 获取标题和作者"""
        url = f"{self.base_url}/comic/detail/{manga_id}?_v=2.2.5"
        try:
            res = self.session.get(url, verify=False, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get('errno') == 0:
                    d = data['data']['data']
                    title = d.get('title')
                    
                    # 解析作者
                    authors = []
                    for a in d.get('authors', []):
                        if 'tag_name' in a:
                            authors.append(a['tag_name'])
                    author_str = ",".join(authors)
                    
                    if title:
                        return title, author_str
        except:
            pass
        return None, None

    def worker(self, manga_id):
        """线程工作函数"""
        if self.stop_event.is_set():
            return

        title, author = self.get_manga_info(manga_id)
        
        with self.lock:
            self.processed_count += 1
            # 打印进度 (每 50 个打印一次)
            if self.processed_count % 50 == 0:
                msg = f"进度: 已处理 {self.processed_count} 个任务..."
                print(msg)
                if self.callback: self.callback(msg)

            if title:
                print(f"发现: ID {manga_id} -> {title} [{author}]")
                self.new_data.append({'ID': manga_id, 'Title': title, 'Author': author})
                
                # 定期保存
                if len(self.new_data) >= CRAWLER_SAVE_INTERVAL:
                    self.save_to_txt()

    def save_to_txt(self):
        """保存数据到 TXT"""
        if not self.new_data:
            return

        print(f"正在保存数据到 {MANGA_LIST_FILE}...")
        if self.callback: self.callback("正在保存数据...")
        try:
            # 合并数据
            all_data = self.existing_data.copy()
            for item in self.new_data:
                all_data[item['ID']] = {'title': item['Title'], 'author': item['Author']}
            
            # 排序并写入
            sorted_ids = sorted(all_data.keys())
            
            with open(MANGA_LIST_FILE, 'w', encoding='utf-8') as f:
                for mid in sorted_ids:
                    info = all_data[mid]
                    f.write(f"{mid} | {info['title']} | {info['author']}\n")
            
            # 更新缓存
            self.existing_data = all_data
            self.new_data = [] 
            print("保存成功！")
            if self.callback: self.callback("保存成功！")
        except Exception as e:
            print(f"保存失败: {e}")
            if self.callback: self.callback(f"保存失败: {e}")

    def run(self, start_id, end_id):
        """运行爬虫"""
        max_id = self.load_existing_data()

        if start_id > end_id:
            print("起始 ID 不能大于结束 ID")
            return

        # 生成任务列表 (剔除已存在的)
        print("正在生成任务队列...")
        all_ids = range(start_id, end_id + 1)
        tasks = [i for i in all_ids if i not in self.existing_data]
        
        msg = f"范围: {start_id}-{end_id} | 总数: {len(all_ids)} | 跳过: {len(all_ids) - len(tasks)} | 待抓取: {len(tasks)}"
        print(msg)
        if self.callback: self.callback(msg)
        
        if not tasks:
            print("所有 ID 均已存在，无需更新！")
            if self.callback: self.callback("所有 ID 均已存在，无需更新！")
            return

        print(f"启动 {CRAWLER_MAX_WORKERS} 个线程开始抓取...")
        if self.callback: self.callback(f"启动 {CRAWLER_MAX_WORKERS} 个线程...")
        start_time = time.time()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=CRAWLER_MAX_WORKERS) as executor:
                futures = {executor.submit(self.worker, mid): mid for mid in tasks}
                for future in concurrent.futures.as_completed(futures):
                    if self.stop_event.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
        except KeyboardInterrupt:
            print("用户中断！正在保存已抓取的数据...")
        finally:
            self.save_to_txt()
            elapsed = time.time() - start_time
            msg = f"任务结束！耗时: {elapsed:.2f}秒"
            print(msg)
            if self.callback: self.callback(msg)

# ================= 3. 双重并发任务管理器 =================

class DownloadTask:
    def __init__(self, manga_id, title=None):
        self.id = manga_id
        self.title = title
        self.status = "waiting" # waiting, downloading, finished, error, canceled
        self.progress = 0.0 # 0.0 - 1.0 (章节比例)
        self.message = "排队中..."
        self.total_chapters = 0
        self.done_chapters = 0
        self.stop_event = threading.Event()  # 单任务停止旗标

class DownloadManager:
    def __init__(self, api: ZaimanhuaAPI, ui_callback: Callable):
        self.api = api
        self.ui_callback = ui_callback
        
        # 默认并发设置 (会被 config 覆盖)
        self.max_books = 1
        self.max_images = 5
        
        # Refactor: Replace queue.Queue with Thread-Safe List for random remove support
        self.waiting_list = [] 
        self.queue_lock = threading.Lock()
        
        self.active_tasks = [] 
        self.stop_flag = threading.Event()
        
        threading.Thread(target=self._scheduler_loop, daemon=True).start()

    def set_concurrency(self, books, images):
        self.max_books = int(books)
        self.max_images = int(images)
        print(f"并发设置更新: 书籍={self.max_books}, 图片={self.max_images}")

    def stop_all_tasks(self):
        """停止所有任务 (Globals Stop)"""
        self.stop_flag.set()
        
        # 1. 清空等待队列 (Lock protected)
        with self.queue_lock:
            self.waiting_list.clear() # List clear
            
        # 2. 标记所有活跃任务为停止
        # Copy list to avoid iteration issues
        current_active = list(self.active_tasks) 
        for task in current_active:
            task.stop_event.set()
            task.status = "canceled"
        
        self.ui_callback("stop_all", None)
        # V10 Fix: Removed unreliable timer, rely on add_task clearing flag

    def add_task(self, manga_id, title=None):
        # V10 Fix: Auto-resume if stopped
        if self.stop_flag.is_set():
            self.stop_flag.clear()
            
        task = DownloadTask(manga_id, title)
        with self.queue_lock:
            self.waiting_list.append(task)
        self.ui_callback("task_added", task)

    def cancel_task(self, task):
        """停止单个任务 (无论是在队列中还是正在下载)"""
        task.status = "canceled"
        task.stop_event.set()
        task.message = "已取消"
        
        # 1. 尝试从等待队列移除
        with self.queue_lock:
            if task in self.waiting_list:
                self.waiting_list.remove(task)
                self.ui_callback("queue_changed", None) # Notify UI to update count
                return

        # 2. 如果在 Active 中，它会被 stop_event 捕获并退出
        
    def get_waiting_tasks(self):
        """Thread-safe getter for UI"""
        with self.queue_lock:
            return list(self.waiting_list)

    def get_queue_size(self):
        with self.queue_lock:
            return len(self.waiting_list)

    def _scheduler_loop(self):
        """书籍调度器"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor: 
            futures = []
            while True:
                # Cleanup active tasks
                self.active_tasks = [t for t in self.active_tasks if t.status == 'downloading']
                futures = [f for f in futures if not f.done()]
                
                # Check slot availability
                if len(futures) < self.max_books and not self.stop_flag.is_set():
                    # Try get task from List
                    task = None
                    with self.queue_lock:
                        if self.waiting_list:
                            task = self.waiting_list.pop(0)
                    
                    if task:
                        if self.stop_flag.is_set():
                            continue # Drop it if stopping
                            
                        self.active_tasks.append(task)
                        f = executor.submit(self._process_book, task, self.max_images)
                        futures.append(f)
                        self.ui_callback("queue_changed", None) # Notify UI
                    else:
                        time.sleep(0.5) # Empty queue wait
                else:
                    time.sleep(1) # Full slot wait 

    def _process_book(self, task: DownloadTask, img_concurrency: int):
        task.status = "downloading"
        task.message = "获取信息..."
        self.ui_callback("progress", task)
        
        try:
            detail = self.api.get_manga_detail(task.id)
            if not detail or detail.get('errno') != 0:
                raise Exception("API Fail")
            
            data = detail['data']['data']
            real_title = data.get('title', task.title or "未知漫画")
            task.title = real_title
            
            safe_name = self.api._sanitize(real_title)
            manga_dir = os.path.join(DOWNLOAD_DIR, safe_name)
            os.makedirs(manga_dir, exist_ok=True)

            info_path = os.path.join(manga_dir, "info.json")
            status_label = self.api.get_status_label(data.get('status', []))

            # 读取现有数据以保留额外字段
            existing_data = {}
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except: pass
            
            # Parse Author Name
            raw_author = data.get('authors', [])
            author_text = ""
            if isinstance(raw_author, list):
                author_text = ",".join([str(a.get('tag_name', '')) for a in raw_author if isinstance(a, dict)])
            elif isinstance(raw_author, str):
                author_text = raw_author

            existing_data.update({
                "id": str(task.id), 
                "title": real_title, 
                "author": author_text,
                "status": status_label
            })

            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            # --- 下载封面 (Feature: 补全资料增加一下在每个漫画文件夹 加个获取到的封面命名为 漫画id_漫画名_cover) ---
            cover_url = data.get('cover')
            if cover_url:
                cover_name = f"{task.id}_{safe_name}_cover.jpg"
                self.api.download_cover(cover_url, manga_dir, cover_name)
            # ----------------------------------------------------------------------------------

            chapters = []
            for group in data.get('chapters', []):
                g_title = group.get('title', '')
                for ch in group.get('data', []):
                    t = ch.get('chapter_title', '')
                    full_t = t if g_title == '连载' else f"{g_title}-{t}"
                    chapters.append({'title': full_t, 'id': ch.get('chapter_id')})
            
            task.total_chapters = len(chapters)
            if task.total_chapters == 0:
                raise Exception("无章节")

            task.done_chapters = 0
            
            for ch in chapters:
                c_title = self.api._sanitize(ch['title'])
                cbz_path = os.path.join(manga_dir, f"{safe_name}_{c_title}.cbz")
                
                task.message = f"下载: {c_title}"
                self.ui_callback("progress", task)


                     
                # Stop Check (Global or Local)
                if self.stop_flag.is_set() or task.stop_event.is_set():
                    raise Exception("任务已停止")

                if os.path.exists(cbz_path):
                    task.done_chapters += 1
                else:
                    self._download_chapter_images(task.id, ch['id'], cbz_path, img_concurrency)
                    task.done_chapters += 1
                
                task.progress = task.done_chapters / task.total_chapters
                self.ui_callback("progress", task)

            task.status = "finished"
            task.message = "✅ 完成"
            self.ui_callback("task_finish", task)

        except Exception as e:
            task.status = "error"
            task.message = f"❌ {str(e)}"
            self.ui_callback("task_error", task)

    def _download_chapter_images(self, mid, cid, cbz_path, concurrency):
        c_res = self.api.get_chapter_images(mid, cid)
        if not c_res or c_res.get('errno') != 0: return
        
        urls = c_res['data']['data'].get('page_url', [])
        if not urls: return

        with tempfile.TemporaryDirectory() as tmp:
            img_paths = [None] * len(urls)
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                future_to_idx = {
                    pool.submit(self.api.download_image_content, url): idx 
                    for idx, url in enumerate(urls)
                }
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        data = future.result()
                        if data:
                            p = os.path.join(tmp, f"{idx+1:03d}.jpg")
                            with open(p, 'wb') as f: f.write(data)
                            img_paths[idx] = p
                    except: pass
            
            valid_paths = [p for p in img_paths if p]
            if valid_paths:
                with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for p in valid_paths: zf.write(p, os.path.basename(p))

# ================= 3. UI 组件 =================

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, current_books, current_imgs, callback):
        super().__init__(master)
        self.callback = callback
        self.title("设置")
        self.geometry("300x200")
        
        ctk.CTkLabel(self, text="并发设置", font=("bold", 16)).pack(pady=15)
        
        f1 = ctk.CTkFrame(self, fg_color="transparent")
        f1.pack(pady=5)
        ctk.CTkLabel(f1, text="最大同时下载书籍:").pack(side="left")
        self.ent_books = ctk.CTkEntry(f1, width=60)
        self.ent_books.pack(side="left", padx=10)
        self.ent_books.insert(0, str(current_books))
        
        f2 = ctk.CTkFrame(self, fg_color="transparent")
        f2.pack(pady=5)
        ctk.CTkLabel(f2, text="每本书图片并发数:").pack(side="left")
        self.ent_imgs = ctk.CTkEntry(f2, width=60)
        self.ent_imgs.pack(side="left", padx=10)
        self.ent_imgs.insert(0, str(current_imgs))
        
        ctk.CTkButton(self, text="保存生效", command=self.on_save).pack(pady=20)
        self.grab_set()

    def on_save(self):
        try:
            b = int(self.ent_books.get())
            i = int(self.ent_imgs.get())
            if b < 1 or i < 1: raise ValueError
            self.callback(b, i)
            self.destroy()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数")

class MetadataFixDialog(ctk.CTkToplevel):
    """元数据修复交互对话框"""
    def __init__(self, master, folder_name, results, callback):
        super().__init__(master)
        self.callback = callback
        self.title(f"修复资料: {folder_name}")
        self.geometry("450x500")
        
        ctk.CTkLabel(self, text=f"文件夹: {folder_name}", font=("bold", 14)).pack(pady=10)
        ctk.CTkLabel(self, text="未找到 info.json，请选择对应的漫画:", text_color="gray").pack(pady=(0,10))
        
        self.scroll = ctk.CTkScrollableFrame(self, height=200)
        self.scroll.pack(fill="x", padx=10, pady=5)
        
        self.selected_val = tk.StringVar(value="")
        
        if not results:
            ctk.CTkLabel(self.scroll, text="未找到自动匹配结果").pack(pady=20)
        else:
            for item in results:
                # 来源标识
                src = "本地" if item.get('source') == 'local' else "网络"
                val = f"{item['id']}|{item['title']}"
                text = f"[{src}] {item['title']} (ID:{item['id']})"
                rb = ctk.CTkRadioButton(self.scroll, text=text, variable=self.selected_val, value=val)
                rb.pack(anchor="w", pady=2, padx=5)
                
        # 手动输入区
        manual_frame = ctk.CTkFrame(self)
        manual_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(manual_frame, text="或者手动输入:").pack(anchor="w", padx=5, pady=2)
        
        self.ent_mid = ctk.CTkEntry(manual_frame, placeholder_text="ID")
        self.ent_mid.pack(side="left", padx=5, expand=True, fill="x")
        
        self.ent_title = ctk.CTkEntry(manual_frame, placeholder_text="标题 (留空用文件夹名)")
        self.ent_title.pack(side="left", padx=5, expand=True, fill="x")
        self.ent_title.insert(0, folder_name)

        # 按钮区
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=20)
        
        ctk.CTkButton(btn_frame, text="跳过", fg_color="gray", width=80, command=self.on_skip).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="确认修复", width=120, command=self.on_confirm).pack(side="right", padx=10)
        
        self.protocol("WM_DELETE_WINDOW", self.on_skip)
        self.grab_set() # 模态对话框

    def on_confirm(self):
        mid = self.ent_mid.get().strip()
        mtitle = self.ent_title.get().strip()
        
        if mid:
            self.callback({'id': mid, 'title': mtitle})
            self.destroy()
            return
            
        sel = self.selected_val.get()
        if sel:
            pid, ptitle = sel.split("|", 1)
            self.callback({'id': pid, 'title': ptitle})
            self.destroy()
        else:
            messagebox.showwarning("提示", "请选择一项或手动输入ID")

    def on_skip(self):
        self.callback(None)
        self.destroy()


class SearchResultCard(ctk.CTkFrame):
    def __init__(self, master, title, mid, download_cmd, author=None, cover_url=None):
        super().__init__(master, fg_color=THEME["card_bg"], corner_radius=8)
        self.grid_columnconfigure(1, weight=1) # Title column
        self.title = title
        self.mid = mid
        self.download_cmd = download_cmd
        self.cover_url = cover_url
        
        # Hover 效果
        self.bind("<Enter>", lambda e: self.configure(fg_color=THEME["card_hover"]))
        self.bind("<Leave>", lambda e: self.configure(fg_color=THEME["card_bg"]))
        
        # 1. 封面图片 (Left)
        self.img_label = ctk.CTkLabel(self, text="📖", width=60, height=80, 
                                     fg_color=("gray80", "gray30"), corner_radius=6, cursor="hand2")
        self.img_label.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
        
        # 2. 信息区 (Middle)
        title_text = title
        if author:
            title_text = f"{title}"
        
        self.lbl_title = ctk.CTkLabel(self, text=title_text, font=("Microsoft YaHei UI", 13, "bold"), 
                                     anchor="w", wraplength=200, justify="left")
        self.lbl_title.grid(row=0, column=1, padx=5, pady=(8, 2), sticky="ew")
        
        # 作者和ID信息
        info_text = f"ID: {mid}" + (f" · {author}" if author else "")
        ctk.CTkLabel(self, text=info_text, font=("Arial", 11), text_color="gray", anchor="w") \
            .grid(row=1, column=1, padx=5, pady=(0, 8), sticky="ew")
        
        # 3. 按钮 (Right) - 使用主色调
        self.btn = ctk.CTkButton(self, text="⬇️", width=50, height=36, font=("Arial", 16),
                                fg_color=THEME["primary"], hover_color=THEME["primary_hover"],
                                corner_radius=8, command=self._on_click)
        self.btn.grid(row=0, column=2, rowspan=2, padx=10)

        # 加载图片
        if self.cover_url:
            self._load_image_async()
        else:
            self.img_label.configure(text="📖")

    def _on_click(self):
        self.btn.configure(state="disabled", text="✔", fg_color="gray")
        self.download_cmd(self.mid, self.title)
        self.after(2000, lambda: self.btn.configure(state="normal", text="⬇️", fg_color="#1f6aa5"))
        
    def _load_image_async(self):
        def _fetch():
            try:
                # Use standard Chrome User-Agent
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://manhua.zaimanhua.com/'
                }
                res = requests.get(self.cover_url, headers=headers, timeout=5, verify=False)
                if res.status_code == 200:
                    data = res.content
                    image = Image.open(io.BytesIO(data))
                    # Resize to V9 standard (approx 60 width)
                    w, h = image.size
                    new_w = 60
                    new_h = int(h * (new_w / w))
                    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    return image
            except Exception as e:
                print(f"Cover load error: {e}")
            return None

        def _safe_update(img=None, error=False, failed=False):
            try:
                if not self.winfo_exists(): return
                
                if img:
                    self._show_image(img)
                elif failed:
                    self.img_label.configure(text="Fail")
                else: 
                    self.img_label.configure(text="Err")
            except Exception: pass

        def _done(future):
            try:
                img = future.result()
                if img:
                     self.after(0, lambda: _safe_update(img=img))
                else:
                     self.after(0, lambda: _safe_update(error=True))
            except:
                self.after(0, lambda: _safe_update(failed=True))

        IMAGE_LOADER.submit(_fetch).add_done_callback(_done)

    def _show_image(self, pil_image):
        try:
            ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
            self.img_label.configure(image=ctk_img, text="")
        except: pass

    def update_info(self, title, author=None, cover_url=None):
        """Smart update: only update fields that changed"""
        # Update title/author
        new_text = title
        if author: new_text = f"{title} [{author}]"
        
        if self.lbl_title.cget("text") != new_text:
            self.lbl_title.configure(text=new_text)
            
        # Update cover if new one is provided
        if cover_url and cover_url != self.cover_url:
            self.cover_url = cover_url
            self._load_image_async()


class TaskCard(ctk.CTkFrame):
    def __init__(self, master, task: DownloadTask, stop_command=None):
        super().__init__(master, fg_color=("gray90", "gray17"), corner_radius=6)
        self.task = task
        self.stop_cmd = stop_command
        self.grid_columnconfigure(0, weight=1)
        
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=10, pady=(8,5), sticky="ew")
        
        # Title
        self.lbl_title = ctk.CTkLabel(top, text=task.title or f"ID: {task.id}", font=("bold", 12), anchor="w")
        self.lbl_title.pack(side="left")
        
        # Stop Button
        if self.stop_cmd:
            self.btn_stop = ctk.CTkButton(top, text="❌", width=25, height=20, fg_color="transparent", text_color="red", hover_color="gray",
                                         command=lambda: self.stop_cmd(self.task))
            self.btn_stop.pack(side="right", padx=(5,0))

        # Status Label
        self.lbl_status = ctk.CTkLabel(top, text="准备中...", font=("Arial", 10), text_color="gray")
        self.lbl_status.pack(side="right")
        
        self.progress_bar = ctk.CTkProgressBar(self, height=8)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.lbl_info = ctk.CTkLabel(self, text="...", font=("Arial", 10), anchor="w")
        self.lbl_info.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="ew")

    def update_state(self):
        self.progress_bar.set(self.task.progress)
        self.lbl_status.configure(text=self.task.message)
        if self.task.title: self.lbl_title.configure(text=self.task.title)
        
        if self.task.total_chapters > 0:
            pct = int(self.task.progress * 100)
            self.lbl_info.configure(text=f"{self.task.done_chapters}/{self.task.total_chapters} 话 ({pct}%)")
        else:
            self.lbl_info.configure(text=self.task.message)

class BulkProgressCard(ctk.CTkFrame):
    """批量更新时的聚合进度条 (Throttled UI Updates)"""
    def __init__(self, master, total_count=0):
        super().__init__(master, fg_color=("gray90", "gray17"), corner_radius=6)
        
        # State Data (Thread Safe-ish for simple assignment)
        self.total = total_count
        self.finished = 0
        self.last_msg = "初始化..."
        
        # Throttling
        self._running = True
        
        self.grid_columnconfigure(0, weight=1)
        
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=10, pady=(8,5), sticky="ew")
        
        self.lbl_title = ctk.CTkLabel(top, text="批量更新任务", font=("bold", 12), anchor="w")
        self.lbl_title.pack(side="left")
        
        self.lbl_count = ctk.CTkLabel(top, text=f"0/{total_count}", font=("Arial", 12), text_color="#1f6aa5")
        self.lbl_count.pack(side="right")
        
        self.progress_bar = ctk.CTkProgressBar(self, height=10)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.lbl_info = ctk.CTkLabel(self, text="...", font=("Arial", 10), anchor="w", text_color="gray")
        self.lbl_info.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="ew")
        
        # Start UI Refresh Loop
        self._ui_loop()

    def destroy(self):
        self._running = False
        super().destroy()

    def _ui_loop(self):
        if not self._running: return
        try:
            pct = 0
            if self.total > 0:
                pct = self.finished / self.total
                if pct > 1.0: pct = 1.0
            
            self.progress_bar.set(pct)
            self.lbl_count.configure(text=f"已更新: {self.finished} / 总数: {self.total}")
            self.lbl_info.configure(text=f"正在处理: {self.last_msg}")
        except: pass
        
        # Refresh every 500ms
        self.after(500, self._ui_loop)

    # These methods are called from thread, just update data
    def update_progress(self, current_msg=None):
        if current_msg: self.last_msg = current_msg
        
    def add_total(self, n=1):
        self.total += n
        
    def add_finished(self, n=1):
        self.finished += n

class LibraryCard(ctk.CTkFrame):
    def __init__(self, master, info, update_cmd):
        super().__init__(master, fg_color=("gray85", "gray20"), corner_radius=6)
        self.info = info 
        self.grid_columnconfigure(1, weight=1)
        
        # 1. 封面 (Left)
        self.img_label = ctk.CTkLabel(self, text="...", width=50, height=70, fg_color="gray70", cursor="hand2")
        self.img_label.grid(row=0, column=0, rowspan=2, padx=8, pady=5)
        self.img_label.bind("<Button-1>", lambda e: self.open_folder(info['title']))
        
        # 2. 信息 (Middle)
        title = info.get('title', 'Unknown')
        mid = info.get('id', '???')
        author = info.get('author', '')
        status = info.get('status', '未知状态')
        
        # Clean author if it looks like the raw list string (Backward compatibility for what user just saw)
        # However, `_backend_load_library` should handle this ideally. 
        # But let's be safe here for display.
        if author and author.startswith("[{"):
             # Simple heuristic cleanup if parsing failed previously
             # But better to assume info['author'] is clean string now.
             pass

        self.lbl_title = ctk.CTkLabel(self, text=title, font=("Microsoft YaHei UI", 12, "bold"), 
                                     anchor="w", wraplength=250, justify="left")
        self.lbl_title.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="ew")
        
        meta = f"ID: {mid} | {status}"
        if author: meta += f" | {author}"
        
        ctk.CTkLabel(self, text=meta, text_color="gray", font=("Arial", 10), anchor="w").grid(row=1, column=1, padx=5, pady=(0, 5), sticky="ew")
        
        # 3. 按钮 (Right)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=5)
        
        self.btn_upd = ctk.CTkButton(btn_frame, text="更新", width=50, height=24, fg_color="#1f6aa5", 
                     command=lambda: self._on_update(update_cmd, info))
        self.btn_upd.pack(pady=2)
        
        ctk.CTkButton(btn_frame, text="打开", width=50, height=24, fg_color="gray", 
                     command=lambda: self.open_folder(info['title'])).pack(pady=2)

        # 加载本地封面
        self._load_local_cover()

    def _load_local_cover(self):
        # 尝试寻找 [mid]_[title]_cover.jpg
        # 这里需要一些智能查找，因为 title 可能会有 sanitize 的差异
        # 最简单是遍历文件夹找 *_cover.jpg
        try:
            path = self.info.get('path')
            if not path or not os.path.exists(path): return
            
            cover_path = None
            
            # 1. 尝试精确匹配 (如果 info 中记录了 cover_path 更好，但现在没有)
            # 扫描目录下是否有 *_cover.jpg
            for f in os.listdir(path):
                if f.endswith("_cover.jpg"):
                    cover_path = os.path.join(path, f)
                    break
            
            if cover_path:
                self._load_image_async(cover_path)
            else:
                self.img_label.configure(text="No Cover", font=("Arial", 8))
        except: pass

    def _load_image_async(self, path):
        def _read():
            try:
                img = Image.open(path)
                w, h = img.size
                new_w = 50
                new_h = int(h * (new_w / w))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                return img
            except: return None
            
        def _done(future):
            try:
                img = future.result()
                if img:
                    if not self.winfo_exists(): return
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    self.img_label.configure(image=ctk_img, text="")
            except: pass

        IMAGE_LOADER.submit(_read).add_done_callback(_done)

    def _on_update(self, cmd, info):
        cmd(info.get('id'), info.get('title'))
        orig_text = self.btn_upd.cget("text")
        self.btn_upd.configure(text="已加入", state="disabled", fg_color="green")
        self.after(2000, lambda: self.btn_upd.configure(text=orig_text, state="normal", fg_color="#1f6aa5"))

    def open_folder(self, title):
        # Use stored path if available
        path = self.info.get('path')
        if not path:
            safe_title = "".join([c if c not in '<>:"/\\|?*' else '_' for c in title]).strip()
            path = os.path.join(DOWNLOAD_DIR, safe_title)
            
        if os.path.exists(path):
            if platform.system() == "Windows": os.startfile(path)
            else: subprocess.Popen(["open", path])


# ================= 4. 主程序 =================

class CrawlerDialog(ctk.CTkToplevel):
    """简单配置爬虫的对话框"""
    def __init__(self, master, on_start, max_id=0):
        super().__init__(master)
        self.on_start = on_start
        self.title("更新云端索引")
        self.geometry("380x250")
        
        default_start = max_id + 1 if max_id > 0 else 1
        
        ctk.CTkLabel(self, text="更新本地漫画索引", font=("bold", 16)).pack(pady=15)
        ctk.CTkLabel(self, text=f"当前本地最大ID: {max_id}", text_color="gray").pack()
        
        f1 = ctk.CTkFrame(self, fg_color="transparent")
        f1.pack(pady=5)
        ctk.CTkLabel(f1, text="起始 ID:").pack(side="left")
        self.ent_start = ctk.CTkEntry(f1, width=100)
        self.ent_start.pack(side="left", padx=5)
        self.ent_start.insert(0, str(default_start))
        
        f2 = ctk.CTkFrame(self, fg_color="transparent")
        f2.pack(pady=5)
        ctk.CTkLabel(f2, text="结束 ID:").pack(side="left")
        self.ent_end = ctk.CTkEntry(f2, width=100)
        self.ent_end.pack(side="left", padx=5)
        
        ctk.CTkLabel(self, text="(如果不输入结束ID, 默认无限制跑下去)", font=("Arial", 10), text_color="gray").pack()
        
        ctk.CTkButton(self, text="开始抓取", command=self._on_confirm).pack(pady=20)
        self.grab_set()

    def _on_confirm(self):
        try:
            s = int(self.ent_start.get())
            e_str = self.ent_end.get().strip()
            e = int(e_str) if e_str else 999999
            self.on_start(s, e)
            self.destroy()
        except ValueError:
            messagebox.showerror("错误", "请输入有效数字")

class RecentUpdateCard(ctk.CTkFrame):
    def __init__(self, master, data, download_callback, delay_cover=False):
        super().__init__(master, fg_color=THEME["card_bg"], corner_radius=8)
        self.data = data
        self.download_callback = download_callback
        
        # Hover 效果
        self.bind("<Enter>", lambda e: self.configure(fg_color=THEME["card_hover"]))
        self.bind("<Leave>", lambda e: self.configure(fg_color=THEME["card_bg"]))
        
        # Grid layout: Image Left, Info Right
        self.grid_columnconfigure(1, weight=1)
        
        # 1. Cover (Left) - Spanning 4 rows (Title, Author, Latest, Time)
        self.img_label = ctk.CTkLabel(self, text="📖", width=70, height=90, 
                                     fg_color=("gray80", "gray30"), corner_radius=6)
        self.img_label.grid(row=0, column=0, rowspan=4, padx=8, pady=8)
        
        # 2. Info (Right)
        # Title
        title = data.get('title', 'Unknown')
        self.lbl_title = ctk.CTkLabel(self, text=title, font=("Microsoft YaHei UI", 12, "bold"), 
                                     anchor="w", justify="left", wraplength=140) 
        self.lbl_title.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="nw")
        
        # 3. Action (Bottom) - 使用主色调
        self.btn_dl = ctk.CTkButton(self, text="⬇️ 下载", width=70, height=28, corner_radius=6,
                                   fg_color=THEME["primary"], hover_color=THEME["primary_hover"],
                                   command=self._on_download)
        self.btn_dl.grid(row=4, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

        # 保存标签引用便于后续更新
        # Author
        author = data.get('author', '')
        if len(author) > 12: author = author[:12] + ".."
        self.lbl_author = ctk.CTkLabel(self, text=f"作者: {author}", font=("Arial", 10), text_color="gray", anchor="w")
        self.lbl_author.grid(row=1, column=1, padx=5, sticky="ew")

        # Latest - 使用主色调
        latest = data.get('latest', '')
        self.lbl_latest = ctk.CTkLabel(self, text=f"最新: {latest}", font=("Arial", 10), 
                                      text_color=THEME["primary"], anchor="w")
        self.lbl_latest.grid(row=2, column=1, padx=5, sticky="ew")

        # Time
        time_str = data.get('time', '')
        self.lbl_time = ctk.CTkLabel(self, text=time_str, font=("Arial", 9), text_color="#E65100", anchor="w")
        self.lbl_time.grid(row=3, column=1, padx=5, pady=(0,5), sticky="ew")

        # Async Load Cover (可选延迟加载)
        if not delay_cover and data.get('cover'):
            self._load_cover(data['cover'])

    def _on_download(self):
        self.download_callback(self.data)
        self.btn_dl.configure(text="✔", fg_color="green", state="disabled")
    
    def update_data(self, data, cover_url=None):
        """更新卡片内容（复用卡片时调用）"""
        self.data = data
        
        # 重置下载按钮状态
        self.btn_dl.configure(text="下载", fg_color="#1f6aa5", state="normal")
        
        # 更新标题
        title = data.get('title', 'Unknown')
        self.lbl_title.configure(text=title)
        
        # 更新作者
        author = data.get('author', '')
        if len(author) > 12: author = author[:12] + ".."
        self.lbl_author.configure(text=f"作者: {author}")
        
        # 更新最新章节
        latest = data.get('latest', '')
        self.lbl_latest.configure(text=f"最新: {latest}")
        
        # 更新时间
        time_str = data.get('time', '')
        self.lbl_time.configure(text=time_str)
        
        # 重置封面（只更新文字，不设置image=None避免报错）
        self.img_label.configure(text="...")
        
        # 加载新封面
        if cover_url:
            self._load_cover(cover_url)
    
    def reset(self):
        """重置卡片为空白状态"""
        self.data = {}
        self.lbl_title.configure(text="")
        self.lbl_author.configure(text="")
        self.lbl_latest.configure(text="")
        self.lbl_time.configure(text="")
        self.img_label.configure(text="")  # 只更新文字，不设置image=None
        self.btn_dl.configure(text="下载", fg_color="#1f6aa5", state="disabled")
    
    def load_cover(self, url):
        """公开方法，用于延迟加载封面"""
        if url:
            self._load_cover(url)

    def _load_cover(self, url):
        # 检查缓存
        if url in COVER_CACHE:
            try:
                if self.winfo_exists():
                    self.img_label.configure(image=COVER_CACHE[url], text="")
            except: pass
            return
        
        # 使用全局线程池加载
        def _fetch():
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://manhua.zaimanhua.com/'
                }
                res = requests.get(url, headers=headers, timeout=5, verify=False)
                if res.status_code == 200:
                    image = Image.open(io.BytesIO(res.content))
                    image.thumbnail((70, 90), Image.Resampling.LANCZOS) 
                    return image
            except: pass
            return None

        def _done(future):
            img = future.result()
            if img and self.winfo_exists():
                try:
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    COVER_CACHE[url] = ctk_img  # 存入缓存
                    self.img_label.configure(image=ctk_img, text="")
                except: pass

        IMAGE_LOADER.submit(_fetch).add_done_callback(_done)


class RecentUpdatesDialog(ctk.CTkToplevel):
    def __init__(self, master, api: ZaimanhuaAPI, download_cb):
        super().__init__(master)
        self.api = api
        self.download_cb = download_cb
        self.title("最近更新")
        
        # 从配置读取保存的尺寸
        self._load_dialog_geometry()
        
        # 绑定关闭事件保存尺寸
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # 窗口置顶显示，确保在主窗口之上
        self.lift()
        self.focus_force()
        self.attributes('-topmost', True)  # 置顶
        self.after(200, lambda: self.attributes('-topmost', False))  # 200ms后取消置顶
        
        self.current_page = 1
        self.loading = False
        self.cards = []  # 预创建的固定卡片列表
        self.total_cards = 20  # 每页固定20个卡片
        self.columns = 5
        
        # 1. Header
        header = ctk.CTkFrame(self, height=50)
        header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(header, text="加载较慢请耐心等待", font=("bold", 18)).pack(side="left", padx=10)
        
        self.btn_prev = ctk.CTkButton(header, text="< 上一页", width=80, command=self.prev_page)
        self.btn_prev.pack(side="right", padx=5)
        
        self.btn_next = ctk.CTkButton(header, text="下一页 >", width=80, command=self.next_page)
        self.btn_next.pack(side="right", padx=5)
        
        self.entry_page = ctk.CTkEntry(header, width=50)
        self.entry_page.pack(side="right", padx=5)
        self.entry_page.bind("<Return>", self.jump_page)
        self.entry_page.insert(0, "1")
        
        ctk.CTkLabel(header, text="页码:").pack(side="right")
        
        ctk.CTkButton(header, text="刷新", width=60, fg_color="gray", command=lambda: self.load_page(self.current_page)).pack(side="right", padx=20)

        # 2. Content Container
        self.scroll = ctk.CTkFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 配置网格
        for i in range(self.columns):
            self.scroll.grid_columnconfigure(i, weight=1)
        for i in range(4):
            self.scroll.grid_rowconfigure(i, weight=1)
        
        # 3. 预创建20个固定卡片（使用空数据初始化）
        self._create_fixed_cards()
        
        # 4. 加载第一页数据
        self.load_page(1)

    def _load_dialog_geometry(self):
        """从配置文件读取对话框尺寸"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    w = config.get('recent_dialog_width', 1280)
                    h = config.get('recent_dialog_height', 880)
                    x = config.get('recent_dialog_x')
                    y = config.get('recent_dialog_y')
                    if x is not None and y is not None:
                        self.geometry(f"{w}x{h}+{x}+{y}")
                    else:
                        self.geometry(f"{w}x{h}")
                    return
        except: pass
        self.geometry("1280x880")
    
    def _on_close(self):
        """关闭时保存对话框尺寸"""
        try:
            import re
            geo = self.geometry()
            match = re.match(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', geo)
            if match:
                w = int(match.group(1))
                h = int(match.group(2))
                x = int(match.group(3))
                y = int(match.group(4))
                
                config = {}
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                
                config['recent_dialog_width'] = w
                config['recent_dialog_height'] = h
                config['recent_dialog_x'] = x
                config['recent_dialog_y'] = y
                
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False)
        except Exception as e:
            print(f"保存最近更新对话框尺寸失败: {e}")
        
        self.destroy()

    def _create_fixed_cards(self):
        """预创建20个固定的卡片"""
        empty_data = {'title': '', 'author': '', 'latest': '', 'time': '', 'id': ''}
        for i in range(self.total_cards):
            r = i // self.columns
            c = i % self.columns
            card = RecentUpdateCard(self.scroll, empty_data, self.download_cb, delay_cover=True)
            card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
            card.reset()  # 重置为空白状态
            self.cards.append(card)

    def prev_page(self):
        if self.current_page > 1:
            self.load_page(self.current_page - 1)
            
    def next_page(self):
        self.load_page(self.current_page + 1)
        
    def jump_page(self, event=None):
        try:
            p = int(self.entry_page.get())
            if p > 0: self.load_page(p)
        except: pass

    def load_page(self, page):
        if self.loading: return
        self.loading = True
        
        self.current_page = page
        self.entry_page.delete(0, 'end')
        self.entry_page.insert(0, str(page))
        
        # 更新按钮状态
        self.btn_prev.configure(state="normal" if page > 1 else "disabled")
        
        # === 显示加载遮罩层 ===
        self._show_loading_overlay(f"正在加载第 {page} 页...")
        
        def _task():
            data = self.api.get_recent_updates(page)
            self.after(0, lambda: self._on_loaded(data))
            
        threading.Thread(target=_task, daemon=True).start()
    
    def _show_loading_overlay(self, text="加载中..."):
        """显示加载遮罩层"""
        # 创建遮罩层（覆盖在 scroll 上方）
        self.overlay = ctk.CTkFrame(self, fg_color=("gray90", "gray20"))
        self.overlay.place(relx=0, rely=0.08, relwidth=1, relheight=0.92)  # 覆盖内容区域
        
        # 加载提示
        ctk.CTkLabel(self.overlay, text="⏳", font=("Arial", 48)).pack(pady=(200, 10))
        ctk.CTkLabel(self.overlay, text=text, font=("Microsoft YaHei UI", 16)).pack()
    
    def _hide_loading_overlay(self):
        """隐藏加载遮罩层"""
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.destroy()
            self.overlay = None
        
    def _on_loaded(self, data):
        self.loading = False
        
        if not data:
            self._hide_loading_overlay()
            for card in self.cards:
                card.reset()
            if self.cards:
                self.cards[0].lbl_title.configure(text="加载失败或没有更多数据")
            return
        
        # === 在遮罩层下方静默更新所有卡片 ===
        for i, card in enumerate(self.cards):
            if i < len(data):
                item = data[i]
                card.data = item
                card.btn_dl.configure(text="下载", fg_color="#1f6aa5", state="normal")
                card.lbl_title.configure(text=item.get('title', 'Unknown'))
                author = item.get('author', '')
                if len(author) > 12: author = author[:12] + ".."
                card.lbl_author.configure(text=f"作者: {author}")
                card.lbl_latest.configure(text=f"最新: {item.get('latest', '')}")
                card.lbl_time.configure(text=item.get('time', ''))
                card.img_label.configure(text="...")
                # 立即加载封面
                cover_url = item.get('cover')
                if cover_url:
                    card.load_cover(cover_url)
            else:
                card.reset()
        
        # 强制处理所有UI更新
        self.update_idletasks()
        
        # 延迟移除遮罩层（让封面有时间开始加载）
        self.after(150, self._hide_loading_overlay)

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, login_callback):
        super().__init__(master, corner_radius=16, fg_color=THEME["card_bg"])
        self.login_callback = login_callback
        self.place(relx=0.5, rely=0.5, anchor="center")
        
        # Logo / 标题区域
        ctk.CTkLabel(self, text="📚", font=("Arial", 48)).pack(pady=(30, 5))
        ctk.CTkLabel(self, text="hugoの再漫画下载器", font=("Microsoft YaHei UI", 22, "bold"),
                    text_color=THEME["primary"]).pack(pady=(0, 5))
        ctk.CTkLabel(self, text="V10 Edition", font=("Arial", 12),
                    text_color="gray").pack(pady=(0, 20))
        
        # 用户名输入框
        self.u_entry = ctk.CTkEntry(self, placeholder_text="👤 用户名", width=260, height=42, 
                                   corner_radius=10, font=("Arial", 14))
        self.u_entry.pack(pady=8, padx=40)
        
        # 密码输入框
        self.p_entry = ctk.CTkEntry(self, placeholder_text="🔒 密码", show="*", width=260, height=42,
                                   corner_radius=10, font=("Arial", 14))
        self.p_entry.pack(pady=8, padx=40)
        
        # 自动填充保存的凭据
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    self.u_entry.insert(0, cfg.get('username',''))
                    self.p_entry.insert(0, cfg.get('password',''))
            except: pass

        # 登录按钮
        self.btn = ctk.CTkButton(self, text="🚀 登 录", width=260, height=45, 
                                corner_radius=10, font=("Microsoft YaHei UI", 15, "bold"),
                                fg_color=THEME["primary"], hover_color=THEME["primary_hover"],
                                command=self.do_login)
        self.btn.pack(pady=(20, 30), padx=40)

    def do_login(self):
        u = self.u_entry.get()
        p = self.p_entry.get()
        self.btn.configure(state="disabled", text="登录中...")
        self.login_callback(u, p)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("hugoの再漫画下载器V10")
        
        # 加载配置并恢复窗口位置
        self.current_username = ""
        config = self._load_config()
        win_w = config.get('window_width', 1200)
        win_h = config.get('window_height', 800)
        win_x = config.get('window_x')
        win_y = config.get('window_y')
        
        if win_x is not None and win_y is not None:
            self.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        else:
            self.geometry(f"{win_w}x{win_h}")
        
        # 强制更新窗口几何（解决 customtkinter 可能重置的问题）
        self.update_idletasks()
        if win_x is not None and win_y is not None:
            self.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        
        # 绑定关闭事件保存窗口位置
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set icon if available
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'favicon.ico')
            else:
                icon_path = 'favicon.ico'
            self.iconbitmap(icon_path)
        except: pass
        
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        # 性能优化：预加载漫画索引到内存
        load_manga_index()
        
        self.api = ZaimanhuaAPI()
        self.manager = DownloadManager(self.api, self.on_manager_event)
        self.task_widgets = {}
        
        self.library_full_data = [] 
        self.library_current_index = 0
        self.library_page_size = 30 
        
        # Crawler integration
        self.crawler_thread = None
        self.crawler_stop_event = threading.Event()
        
        self.bulk_mode = False
        self.bulk_card = None
        
        # Recent Updates Dialog Reference
        self.recent_dialog = None
        
        # 检查是否有保存的 token，实现自动登录
        saved_token = config.get('token', '')
        if saved_token:
            # 使用保存的 token 直接进入主界面
            self.api.token = saved_token
            self.current_username = config.get('username', '')
            self._init_main_ui_from_token(config)
        else:
            # 显示登录界面
            self.login_frame = LoginFrame(self, self.handle_login)
    
    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}
    
    def _init_main_ui_from_token(self, config):
        """使用保存的 token 直接初始化主界面"""
        max_b = config.get('max_books', 1)
        max_i = config.get('max_images', 5)
        self.manager.set_concurrency(max_b, max_i)
        self.setup_main_ui(max_b, max_i)
        self.refresh_library()
    
    def on_closing(self):
        """窗口关闭时保存位置和大小"""
        self._save_window_geometry()
        self.destroy()
    
    def _save_window_geometry(self):
        """保存窗口位置和大小到配置"""
        try:
            # 使用 geometry() 解析获取准确值，避免 winfo 方法导致的尺寸累加
            geo = self.geometry()  # 格式: "WxH+X+Y" 或 "WxH-X-Y"
            # 解析几何字符串
            import re
            match = re.match(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', geo)
            if match:
                win_w = int(match.group(1))
                win_h = int(match.group(2))
                win_x = int(match.group(3))
                win_y = int(match.group(4))
            else:
                # 回退方案
                win_w = self.winfo_width()
                win_h = self.winfo_height()
                win_x = self.winfo_x()
                win_y = self.winfo_y()
            
            # 读取现有配置
            data = self._load_config()
            data['window_x'] = win_x
            data['window_y'] = win_y
            data['window_width'] = win_w
            data['window_height'] = win_h
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"保存窗口位置失败: {e}")

    def handle_login(self, u, p):

        def _t():
            if self.api.login(u, p):
                self.after(0, lambda: self.login_success(u, p))
            else:
                self.after(0, self.login_fail)
        threading.Thread(target=_t, daemon=True).start()

    def login_success(self, u, p):
        self.login_frame.destroy()
        
        # 保存当前用户名
        self.current_username = u
        
        max_b, max_i = 1, 5
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    max_b = cfg.get('max_books', 1)
                    max_i = cfg.get('max_images', 5)
            except: pass
        
        # 保存配置，包含 token
        self.save_config(u, p, max_b, max_i, token=self.api.token)
        self.manager.set_concurrency(max_b, max_i)

        self.setup_main_ui(max_b, max_i)
        self.refresh_library()

    def login_fail(self):
        self.login_frame.btn.configure(state="normal", text="登录失败", fg_color="red")
        self.after(2000, lambda: self.login_frame.btn.configure(text="登 录", fg_color="#1f6aa5"))

    def save_config(self, u, p, mb, mi, token=None):
        """保存配置，支持保存 token"""
        try:
            # 读取现有配置以保留窗口位置等字段
            data = self._load_config()
            data['username'] = u
            data['password'] = p
            data['max_books'] = int(mb)
            data['max_images'] = int(mi)
            
            if token is not None:
                data['token'] = token
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def setup_main_ui(self, init_books, init_imgs):
        self.paned_win = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, bg="gray60", bd=0, opaqueresize=False)
        self.paned_win.pack(fill="both", expand=True)

        # === 左栏 ===
        self.left_frame = ctk.CTkFrame(self.paned_win, corner_radius=0)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(2, weight=1)

        s_box = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        s_box.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.entry_search = ctk.CTkEntry(s_box, placeholder_text="输入 ID / 漫画名 / 作者", height=35)
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.entry_search.bind("<Return>", lambda e: self.do_search())
        ctk.CTkButton(s_box, text="🔍", width=50, height=35, command=self.do_search).pack(side="left")

        self.lbl_search_msg = ctk.CTkLabel(self.left_frame, text="支持 ID 直达 / 关键词搜索", text_color="gray")
        self.lbl_search_msg.grid(row=1, column=0, padx=10, pady=(0,5), sticky="w")

        self.scroll_results = ctk.CTkScrollableFrame(self.left_frame, label_text="搜索结果")
        self.scroll_results.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        ctk.CTkButton(self.left_frame, text="⬇️ 下载本页全部", height=42, corner_radius=8,
                     fg_color=THEME["danger"], hover_color=THEME["danger_hover"],
                     font=("Microsoft YaHei UI", 13, "bold"),
                     command=self.download_all_search).grid(row=3, column=0, padx=10, pady=10, sticky="ew")

        # === 右栏 ===
        self.right_frame = ctk.CTkFrame(self.paned_win, corner_radius=0, fg_color=("gray95", "gray15"))
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)

        # 顶部按钮工具栏 (Compact)
        btn_box = ctk.CTkFrame(self.right_frame, fg_color=THEME["toolbar_bg"], height=55, corner_radius=8)
        btn_box.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # 1. 设置按钮 (动态显示当前并发)
        self.btn_settings = ctk.CTkButton(btn_box, text=f"⚙️ 设置 ({init_books}/{init_imgs})", width=110, height=36,
                                         fg_color="gray50", hover_color="gray40", corner_radius=8,
                                         command=self.open_settings_dialog)
        self.btn_settings.pack(side="left", padx=10, pady=8)
        
        # 2. 账号按钮 (显示当前登录用户，点击可退出)
        account_text = f"👤 {self.current_username}" if self.current_username else "👤 未登录"
        self.btn_account = ctk.CTkButton(btn_box, text=account_text, width=120, height=36,
                                        fg_color=THEME["primary"], hover_color=THEME["primary_hover"], corner_radius=8,
                                        command=self.show_logout_confirm)
        self.btn_account.pack(side="left", padx=4, pady=8)

        # 2. 功能按钮组 (右对齐) - 使用主题色
        # 全部更新
        ctk.CTkButton(btn_box, text="🔄 全部更新", width=90, height=36, corner_radius=8,
                     fg_color=THEME["orange"], hover_color="#EA580C",
                     command=self.update_all_lib).pack(side="right", padx=4)
        
        # 停止
        self.btn_stop = ctk.CTkButton(btn_box, text="🛑 停止", width=70, height=36, corner_radius=8,
                     fg_color=THEME["danger"], hover_color=THEME["danger_hover"],
                     command=self.stop_all_tasks_ui)
        self.btn_stop.pack(side="right", padx=4)

        # 迁移
        ctk.CTkButton(btn_box, text="📥 迁移完结", width=90, height=36, corner_radius=8,
                     fg_color=THEME["success"], hover_color=THEME["success_hover"],
                     command=self.migrate_completed_ui).pack(side="right", padx=4)

        # 补全
        ctk.CTkButton(btn_box, text="🛠️ 补全资料", width=90, height=36, corner_radius=8,
                     fg_color=THEME["warning"], hover_color=THEME["warning_hover"],
                     command=self.check_library_metadata).pack(side="right", padx=4)
        
        # 索引
        self.btn_update_index = ctk.CTkButton(btn_box, text="☁️ 更新索引", width=90, height=36, corner_radius=8,
                     fg_color=THEME["teal"], hover_color="#0D9488",
                     command=self.on_click_update_index)
        self.btn_update_index.pack(side="right", padx=4)

        # 最近更新
        self.btn_recent = ctk.CTkButton(btn_box, text="📅 最近更新", width=90, height=36, corner_radius=8,
                                       fg_color=THEME["purple"], hover_color=THEME["purple_hover"],
                                       command=self.show_recent_updates)
        self.btn_recent.pack(side="right", padx=4)


        self.lbl_status_bar = ctk.CTkLabel(self.right_frame, text="", text_color="gray", anchor="e")
        self.lbl_status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,5))

        self.tabs = ctk.CTkTabview(self.right_frame)
        self.tabs.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        
        self.tab_dl = self.tabs.add("正在下载")
        self.tab_lib = self.tabs.add("我的漫画库")
        
        # ---------------------------------------------------------
        #  下载列表 UI (重构: 只显示 "正在下载区" 和 "等待队列统计")
        # ---------------------------------------------------------
        
        # 1. 统计栏 (Queue Status & Toggle)
        # 用户需求: 像搜索结果一样，把队列做一个展开菜单
        self.frame_queue_status = ctk.CTkFrame(self.tab_dl, height=40, fg_color=("gray90", "gray20"))
        self.frame_queue_status.pack(fill="x", padx=5, pady=5)
        
        # Toggle Button (Acts as Label + Action)
        self.queue_expanded = False
        self.btn_toggle_queue = ctk.CTkButton(self.frame_queue_status, text="📂 查看等待列表 (0)", 
                                             fg_color="transparent", text_color=("gray10", "gray90"), anchor="w",
                                             command=self.toggle_queue_view)
        self.btn_toggle_queue.pack(side="left", fill="both", expand=True, padx=5)
        
        # 隐藏的队列列表容器 (Scrollable)
        self.frame_queue_list = ctk.CTkScrollableFrame(self.tab_dl, height=200, label_text="等待中的任务 (前20个)", fg_color=("gray95", "gray15"))
        # 默认不 pack，点击展开时才 pack
        
        # 2. 活跃任务滚动区 (Active Tasks)
        self.lbl_active_title = ctk.CTkLabel(self.tab_dl, text="正在下载:", anchor="w", font=("bold", 14))
        self.lbl_active_title.pack(fill="x", padx=10, pady=(10,0))
        
        self.scroll_tasks = ctk.CTkScrollableFrame(self.tab_dl, fg_color="transparent") # 保留这个名字兼容旧代码，但仅用于 Active
        self.scroll_tasks.pack(fill="both", expand=True, pady=5)
        self.frame_active_tasks = self.scroll_tasks # Alias for clarity
        
        self.total_queue_count = 0 # UI 计数器
        
        # 库搜索框 (添加到 library tab 顶部)
        lib_search_frame = ctk.CTkFrame(self.tab_lib, height=40, fg_color="transparent")
        lib_search_frame.pack(side="top", fill="x", padx=5, pady=5)
        
        self.entry_lib_search = ctk.CTkEntry(lib_search_frame, placeholder_text="搜索本地库 (回车确认)...", height=30)
        self.entry_lib_search.pack(side="left", fill="x", expand=True)
        self.entry_lib_search.bind("<Return>", lambda e: self.filter_library(self.entry_lib_search.get()))
        
        ctk.CTkButton(lib_search_frame, text="🔍", width=50, height=30, 
                     command=lambda: self.filter_library(self.entry_lib_search.get())).pack(side="left", padx=(5,0))

        ctk.CTkButton(lib_search_frame, text="🔄 刷新", width=60, height=30, fg_color="gray",
                      command=self.refresh_library).pack(side="left", padx=(10,0))

        self.scroll_lib = ctk.CTkScrollableFrame(self.tab_lib, fg_color="transparent")
        self.scroll_lib.pack(fill="both", expand=True)

        self.search_data = []
        self.search_show_limit = 50
        
        self.paned_win.add(self.left_frame, minsize=420, stretch="always")
        self.paned_win.add(self.right_frame, minsize=450, stretch="always")

    # --- 功能逻辑 ---

    def add_task(self, mid, title):
        self.manager.add_task(mid, title)

    def open_settings_dialog(self):
        SettingsDialog(self, self.manager.max_books, self.manager.max_images, self.apply_config_from_dialog)
    
    def show_logout_confirm(self):
        """显示退出登录确认对话框"""
        if messagebox.askyesno("退出登录", f"当前账号: {self.current_username}\n\n确定要退出登录吗？"):
            self.do_logout()
    
    def do_logout(self):
        """执行退出登录"""
        # 清除 token
        self.api.token = ""
        self.current_username = ""
        
        # 清除配置中的 token
        try:
            data = self._load_config()
            data['token'] = ""
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"清除 token 失败: {e}")
        
        # 销毁主界面
        self.paned_win.destroy()
        
        # 显示登录界面
        self.login_frame = LoginFrame(self, self.handle_login)

    def apply_config_from_dialog(self, b, i):
        self.manager.set_concurrency(b, i)
        
        # Update button text
        self.btn_settings.configure(text=f"⚙️ 设置 ({b}/{i})")
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
            else:
                data = {}
            data['username'] = data.get('username', '') 
            data['password'] = data.get('password', '')
            data['max_books'] = b
            data['max_images'] = i
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
            messagebox.showinfo("提示", "并发设置已保存并生效！")
        except Exception as e:
            print(f"Config save error: {e}")

    # --- Search Logic ---

    def search_from_txt(self, keyword):
        """从内存缓存搜索（性能优化：使用 MANGA_INDEX 替代每次读取文件）"""
        results = []
        
        # 确保索引已加载
        if not MANGA_INDEX_LOADED:
            load_manga_index()
        
        # 从内存缓存搜索 - O(n) 遍历但无 I/O 开销
        keyword_lower = keyword.lower()
        for mid, info in MANGA_INDEX.items():
            title = info.get('title', '')
            author = info.get('author', '')
            
            # 搜索 ID、标题、作者（不区分大小写）
            if (keyword_lower in mid.lower() or 
                keyword_lower in title.lower() or 
                keyword_lower in author.lower()):
                results.append({"title": title, "id": mid, "author": author, "source": "local"})
        
        return results

    def do_search(self):
        kw = self.entry_search.get().strip()
        if not kw: return
        
        # Reset UI
        self.lbl_search_msg.configure(text="搜索中...")
        self.search_data = [] # Reset data
        self.search_show_limit = 50
        # self.scroll_results.winfo_children()... We DO NOT clear immediately for smart diffing, 
        # but for a fresh search it might be better to clear or reuse? 
        # Let's clear for a *new* keyword search to avoid confusion, 
        # but we can try to be smart about it.
        # For simplicity in V9 Optimization: Clear first to reset scroll position.
        for w in self.scroll_results.winfo_children(): w.destroy()
        
        self.update()
        
        def _t():
            # --- Phase 1: Local Search (Instant) ---
            local_res = self.search_from_txt(kw)
            if local_res:
                self.after(0, lambda: self.show_results(local_res, is_append=True)) # Show local immediately
            
            # --- Phase 2: Remote Search (Slow) ---
            remote_res = []
            if not kw.isdigit() or len(local_res) == 0:
                 remote_res = self.api.search_dynamic(kw)
            
            # --- Phase 3: Merge & Update ---
            # We need to lock this or run in Main Thread? 
            # Ideally compute the full list then update UI.
            
            final_res = self._merge_results(local_res, remote_res)
            
            # Hydrate Metadata (Covers for local items)
            for item in final_res:
                if not item.get('cover_url'):
                    mid = str(item['id'])
                    try:
                        detail = self.api.get_manga_detail(mid)
                        if detail and detail.get('errno') == 0:
                            data = detail['data']['data']
                            cover = data.get('cover')
                            if cover: item['cover_url'] = cover
                    except Exception: pass
            
            self.after(0, lambda: self.show_results(final_res, is_append=False)) # Full refresh/update
            
        threading.Thread(target=_t, daemon=True).start()

    def _merge_results(self, current_data, new_data):
        merged_map = {str(item['id']): item for item in current_data}
        
        for r in new_data:
            rid = str(r['id'])
            if rid not in merged_map:
                merged_map[rid] = r
            else:
                 # Update existing if remote has better info
                 if r.get('cover_url') and not merged_map[rid].get('cover_url'):
                     merged_map[rid]['cover_url'] = r['cover_url']
        
        return list(merged_map.values())

    def show_results(self, res, is_append=False, reset=False): # reset param kept for compat but unused logic
        # Update Master Data
        if is_append:
             # Merge carefully to avoid duplicates if called multiple times
             current_ids = {str(x['id']) for x in self.search_data}
             for item in res:
                 if str(item['id']) not in current_ids:
                     self.search_data.append(item)
        else:
            self.search_data = res
            
        self.lbl_search_msg.configure(text=f"找到 {len(self.search_data)} 个结果")
        
        if not self.search_data:
             for w in self.scroll_results.winfo_children(): w.destroy()
             ctk.CTkLabel(self.scroll_results, text="未找到结果").pack(pady=20)
             return

        # Prepare for render
        current_data_slice = self.search_data[:self.search_show_limit]
        
        # --- Smart Rendering / Diffing ---
        # 1. Map existing widgets by ID
        existing_widgets = {} # {mid: widget}
        others = []
        for w in self.scroll_results.winfo_children():
            if isinstance(w, SearchResultCard):
                existing_widgets[str(w.mid)] = w
            elif isinstance(w, ctk.CTkButton) and w.cget("text") == "加载更多":
                w.destroy() # Always recreate load button at bottom
            else:
                others.append(w) # Labels etc
                
        # 2. Iterate through data slice and Render/Update
        for item in current_data_slice:
            mid = str(item['id'])
            if mid in existing_widgets:
                # Reuse -> Update
                w = existing_widgets.pop(mid) # Remove from map so we know what's left
                w.update_info(item['title'], item.get('author'), item.get('cover_url'))
                # Re-pack to ensure correct order? 
                # Tkinter pack order is determined by creation or repack. 
                # Calling pack() again on existing widget moves it to the bottom.
                w.pack(fill="x", pady=4) 
            else:
                # Create New
                SearchResultCard(
                    self.scroll_results, 
                    item['title'], 
                    item['id'], 
                    self.add_task,
                    author=item.get('author'),
                    cover_url=item.get('cover_url')
                ).pack(fill="x", pady=4)

        # 3. Cleanup unused widgets (those not in the current slice)
        for w in existing_widgets.values():
            w.destroy()
            
        # 4. Load More Button
        if len(self.search_data) > self.search_show_limit:
             ctk.CTkButton(self.scroll_results, text="加载更多", command=self.load_more_results).pack(pady=10)

    def load_more_results(self):
        self.search_show_limit += 50
        self.show_results(self.search_data, is_append=False)

    def download_all_search(self):
        if not self.search_data: return
        # 移除确认弹窗，直接添加
        count = 0
        for item in self.search_data:
            self.add_task(item['id'], item['title'])
            count += 1
        
        # 右下角提示 (Status Bar)
        self.lbl_status_bar.configure(text=f"✅ 已将 {count} 个任务加入队列")
        # 3秒后恢复
        self.after(3000, lambda: self.lbl_status_bar.configure(text=""))
        
        # 切换到下载标签页 (可选，用户没挂明确说要不要切，但保留这个逻辑比较好，或者不切？用户说“加入成功后不要确认了”，可能也不想被打断视野)
        # 用户说“直接右下角给个提示就好”，暗示不要打断。
        # 还是保留切换吧，或者不切换？"加入队列中" usually implies background. 
        # let's comment out switching tab to be less intrusive based on "give a hint" request.
        # self.tabs.set("正在下载")

    def stop_all_tasks_ui(self):
        if messagebox.askyesno("停止", "确定要停止所有正在进行的下载吗？"):
            self.manager.stop_all_tasks()
            self.btn_stop.configure(state="disabled")
            
            # Reset UI counters
            self.total_queue_count = 0
            self.task_widgets.clear()
            self._update_queue_label()
            
            self.after(3000, lambda: self.btn_stop.configure(state="normal"))

            self.after(3000, lambda: self.btn_stop.configure(state="normal"))

    # --- Recent Updates UI ---
    def show_recent_updates(self):
        if self.recent_dialog is None or not self.recent_dialog.winfo_exists():
            self.recent_dialog = RecentUpdatesDialog(self, self.api, self.add_task_from_recent)
        else:
            self.recent_dialog.focus()

    def add_task_from_recent(self, item_data):
        # Direct add to queue
        mid = item_data['id']
        title = item_data['title']
        self.add_task(mid, title)
        
        # Log toast in Main Log
        msg = f"✅ 已将《{title}》加入下载队列"
        self.lbl_status_bar.configure(text=msg)
        # Auto clear after 3s
        self.after(3000, lambda: self.lbl_status_bar.configure(text=""))


    def on_click_update_index(self):
        # Get max ID from existing file locally (quick check)
        max_id = 0
        if os.path.exists(MANGA_LIST_FILE):
             try:
                 with open(MANGA_LIST_FILE, 'r', encoding='utf-8') as f:
                     for line in f:
                         if "|" in line:
                             p = line.split("|")[0].strip()
                             if p.isdigit():
                                 v = int(p)
                                 if v > max_id: max_id = v
             except: pass
        
        CrawlerDialog(self, self.start_crawler_task, max_id=max_id)

    def start_crawler_task(self, start_id, end_id):
        self.btn_update_index.configure(state="disabled", text="更新中...")
        self.crawler_stop_event.clear()
        
        print(f"Starting crawler: {start_id} - {end_id}")
        
        def _run():
            try:
                crawler = MangaCrawler(callback=self.update_crawler_ui, stop_event=self.crawler_stop_event)
                crawler.run(start_id, end_id)
            except Exception as e:
                print(f"Crawler error: {e}")
                msg = f"爬虫错误: {e}"
                # Safely update GUI from thread
                self.after(0, lambda: self.update_crawler_ui(msg))
            finally:
                self.after(0, self.on_crawler_finish)

        self.crawler_thread = threading.Thread(target=_run, daemon=True)
        self.crawler_thread.start()

    def update_crawler_ui(self, msg):
        # Update status bar
        self.lbl_status_bar.configure(text=msg)

    def on_crawler_finish(self):
        self.btn_update_index.configure(state="normal", text="☁️ 更新索引")
        self.lbl_status_bar.configure(text="索引更新完成")
        messagebox.showinfo("完成", "本地漫画索引更新完成！")
        
        # Verify file creation
        if not os.path.exists(MANGA_LIST_FILE):
            messagebox.showwarning("警告", "manga_list.txt 未生成，可能未找到新数据或爬虫被中断。")

    # --- Library Management ---


    def update_all_lib(self):
        if messagebox.askyesno("全部更新", "确定要更新库中的所有漫画吗？\n(这将在后台静默添加任务，不会卡顿)"):
            self.lbl_status_bar.configure(text="正在后台扫描库文件...")
            
            # 进入批量模式
            self.bulk_mode = True
            self.tabs.set("正在下载")
            
            # 清理旧任务卡片
            for w in self.scroll_tasks.winfo_children(): w.destroy()
            self.task_widgets.clear()
            
            # 创建聚合卡片
            self.bulk_card = BulkProgressCard(self.scroll_tasks, total_count=0)
            self.bulk_card.pack(fill="x", pady=5)
            
            threading.Thread(target=self._backend_update_all, daemon=True).start()

    def _backend_update_all(self):
        tasks_to_add = []
        if self.library_full_data:
            tasks_to_add = self.library_full_data
        else:
            if os.path.exists(DOWNLOAD_DIR):
                for name in os.listdir(DOWNLOAD_DIR):
                    try:
                        with open(os.path.join(DOWNLOAD_DIR, name, "info.json")) as f:
                            tasks_to_add.append(json.load(f))
                    except: pass
        
        for t in tasks_to_add:
            if self.manager.stop_flag.is_set(): break
            self.add_task(t['id'], t['title'])
            time.sleep(0.01) 
            
        self.after(0, lambda: self._on_update_all_finished(len(tasks_to_add)))

    def _on_update_all_finished(self, count):
        self.lbl_status_bar.configure(text=f"✅ 已将 {count} 个更新任务加入队列")

    def check_library_metadata(self):
        if not os.path.exists(DOWNLOAD_DIR): return
        if messagebox.askyesno("检查库", "将扫描缺少 info.json 的文件夹并尝试修复。\n优先参考 manga_list.txt，其次联网搜索。\n是否开始？"):
            self.lbl_status_bar.configure(text="正在检查库元数据...")
            threading.Thread(target=self._backend_fix_metadata, daemon=True).start()

    def _backend_fix_metadata(self):
        folders = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, f))]
        total = len(folders)
        fixed_count = 0
        processed_count = 0
        
        # 线程池并发处理
        max_workers = 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_folder = {executor.submit(self._process_single_metadata, f): f for f in folders}
            
            for future in concurrent.futures.as_completed(future_to_folder):
                folder = future_to_folder[future]
                processed_count += 1
                try:
                    res = future.result()
                    if res:
                        fixed_count += 1
                        self.after(0, lambda r=res: self.lbl_status_bar.configure(text=r))
                except Exception as e:
                    print(f"Fix error {folder}: {e}")
                
                # Update progress sparingly
                if processed_count % 5 == 0:
                    self.after(0, lambda p=processed_count, t=total: self.lbl_status_bar.configure(text=f"资料检查进度: {p}/{t}"))

        self.after(0, lambda: self.lbl_status_bar.configure(text=f"✅ 检查完成，自动修复了 {fixed_count} 个文件夹"))
        self.after(0, self.refresh_library)

    def _process_single_metadata(self, folder_name):
        folder_path = os.path.join(DOWNLOAD_DIR, folder_name)
        info_path = os.path.join(folder_path, "info.json")
        
        # 1. 已有 info.json -> 刷新状态
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    cur_data = json.load(f)
                if 'id' in cur_data:
                    self._save_metadata_with_status(info_path, cur_data['id'], cur_data.get('title', folder_name))
                    return f"状态更新: {folder_name}"
            except: pass
            return None

        # 2. 无 info.json -> 尝试自动修复
        # A. 本地搜索
        local_results = self.search_from_txt(folder_name)
        exact = next((r for r in local_results if r['title'] == folder_name), None)
        if exact:
            self._save_metadata_with_status(info_path, exact['id'], exact['title'])
            return f"本地修复: {folder_name}"
            
        # B. 网络搜索
        remote_results = self.api.search_dynamic(folder_name)
        # Combine
        merged = {r['id']: r for r in local_results}
        for r in remote_results: merged[r['id']] = r
        results = list(merged.values())
        
        selected = next((r for r in results if r['title'] == folder_name), None)
        if selected:
            self._save_metadata_with_status(info_path, selected['id'], selected['title'])
            return f"网络修复: {folder_name}"
            
        return None # 无法自动修复，跳过

    def _save_metadata_with_status(self, path, mid, title):
        """保存元数据时自动获取状态"""
        try:
            status = "连载中"
            # 尝试获取详情更新状态
            try:
                det = self.api.get_manga_detail(str(mid))
                if det and det.get('errno') == 0:
                     data_obj = det['data']['data']
                     status = self.api.get_status_label(data_obj.get('status', []))
                     
                     # --- 补全资料时也保存封面 ---
                     cover_url = data_obj.get('cover')
                     if cover_url:
                         folder_path = os.path.dirname(path)
                         safe_title = self.api._sanitize(title)
                         cover_name = f"{mid}_{safe_title}_cover.jpg"
                         self.api.download_cover(cover_url, folder_path, cover_name)
                     # --------------------------
            except: pass
            
            # 保留旧数据
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except: pass
            
            # Parse Author
            raw_author = data_obj.get('authors', [])
            author_text = ""
            if isinstance(raw_author, list):
                author_text = ",".join([str(a.get('tag_name', '')) for a in raw_author if isinstance(a, dict)])
            elif isinstance(raw_author, str):
                 author_text = raw_author

            data.update({
                "id": str(mid), 
                "title": title, 
                "status": status,
                "author": author_text
            })
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存元数据失败: {e}")

    def refresh_library(self):
        if hasattr(self, "library_loading") and self.library_loading:
            return
        self.library_loading = True
        
        # 启动后台线程加载库，避免卡顿
        threading.Thread(target=self._backend_load_library, daemon=True).start()

    def _backend_load_library(self):
        self.after(0, lambda: self.lbl_status_bar.configure(text="正在加载漫画库..."))
        
        full_data = [] 
        first_batch_shown = False
        batch_limit = 20
        
        if os.path.exists(DOWNLOAD_DIR):
            try:
                # 性能优化：使用全局 MANGA_INDEX 缓存，无需重新读取文件
                # 确保索引已加载
                if not MANGA_INDEX_LOADED:
                    load_manga_index()
                
                count = 0
                # Using scandir for speed
                entries = list(os.scandir(DOWNLOAD_DIR)) 
                entries.sort(key=lambda e: e.name)
                
                # Define helper to clean author locally
                def clean_author_field(val):
                    if not val: return ""
                    val = str(val)
                    if "[{'tag_id'" in val:
                         # Dirty fix for already saved raw data: "[{'tag_id': 1295, 'tag_name': '星野之宣'}]"
                         try:
                             # Extract tag_name using simple regex or string manipulation to avoid eval safety execution issues
                             # Or strict json load if valid JSON components? No, it's python string dump.
                             # Simple find:
                             import re
                             names = re.findall(r"'tag_name': '([^']+)'", val)
                             return ",".join(names)
                         except: return val
                    return val

                for entry in entries:
                    if entry.is_dir():
                        item = {"title": entry.name, "id": "???", "path": entry.path, "author": ""}
                        
                        # Read metadata
                        info_file = os.path.join(entry.path, "info.json")
                        has_info = False
                        if os.path.exists(info_file):
                            try:
                                with open(info_file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    # Normalize author immediately on load
                                    if 'author' in data:
                                        data['author'] = clean_author_field(data['author'])
                                    item.update(data)
                                    has_info = True
                            except: pass
                        
                        # --- Author Fallback (User Request) ---
                        # 性能优化：使用全局 MANGA_INDEX 缓存查找作者
                        if not item.get('author'):
                            # Try by ID first from global cache
                            cached = MANGA_INDEX.get(str(item.get('id')))
                            if cached:
                                item['author'] = cached.get('author', '')
                        # ---------------------------------------
                        
                        full_data.append(item)
                        count += 1
                        
                        # --- First Batch Progressive Render ---
                        if count == batch_limit and not first_batch_shown:
                             # Deep copy to avoid threading issues
                             initial_data = list(full_data)
                             self.after(0, lambda d=initial_data: self._initial_render_library(d))
                             first_batch_shown = True
                        
                        # Update status every 100
                        if count % 100 == 0:
                            msg = f"已扫描: {count} 本..."
                            self.after(0, lambda m=msg: self.lbl_status_bar.configure(text=m))
                            
            except Exception as e:
                print(f"Library load error: {e}")

        # Final Update
        self.library_full_data = full_data
        self.library_display_data = full_data
        self.library_loading = False
        
        self.after(0, lambda: self.lbl_status_bar.configure(text=f"库加载完成: {len(full_data)} 本"))
        
        # If we successfully rendered the first batch, we just need to update the dataset underlying it.
        # But if total items < batch_limit, we haven't rendered yet.
        if not first_batch_shown:
             self.after(0, self._initial_render_library, full_data)
        else:
             # Just update the data reference so "Load More" works with the full set
             # The first page UI is already correct (it's the same 20 items).
             # We might need to refresh if the user sorted? currently default sort.
             pass

    def _initial_render_library(self, data):
        self.library_full_data = data
        self.library_display_data = data
        self._reset_library_ui()


    def _reset_library_ui(self):
        self.library_current_index = 0
        for w in self.scroll_lib.winfo_children(): w.destroy()
        
        # 添加搜索框 (如果还没添加) - 实际上我们把它作为顶部控件常驻比较好
        # 这里我们在 load_library_page 前面加一个过滤逻辑
        
        self.load_library_page()

    def filter_library(self, keyword):
        keyword = keyword.strip().lower()
        if not keyword:
            self.library_display_data = self.library_full_data
        else:
            self.library_display_data = [
                x for x in self.library_full_data 
                if keyword in x['title'].lower() or \
                   keyword in str(x.get('id', '')).lower() or \
                   keyword in str(x.get('author', '')).lower()
            ]
        self._reset_library_ui()

    def load_library_page(self):
        # 使用 library_display_data 而不是 library_full_data
        data_source = getattr(self, "library_display_data", self.library_full_data)
        
        if not data_source: return
        
        end = min(self.library_current_index + self.library_page_size, len(data_source))
        page_items = data_source[self.library_current_index : end]
        
        for item in page_items:
            LibraryCard(self.scroll_lib, item, self.add_task).pack(fill="x", pady=2)

            
        self.library_current_index = end
        
        # Remove old 'Load More' buttons first
        for w in self.scroll_lib.winfo_children():
            if isinstance(w, ctk.CTkButton) and w.cget("text") == "加载更多...":
                w.destroy()

        if self.library_current_index < len(data_source):
            btn = ctk.CTkButton(self.scroll_lib, text="加载更多...", command=self.load_library_page)
            btn.pack(pady=10)

    def on_manager_event(self, event_type, data):
        # 批量模式处理 (直接在调用线程更新数据，不走主线程消息队列，防止卡死)
        if self.bulk_mode and self.bulk_card:
            if event_type == "task_added":
                self.bulk_card.add_total(1)
            elif event_type == "progress":
                if isinstance(data, DownloadTask):
                    self.bulk_card.update_progress(f"{data.title}: {data.message}")
            elif event_type == "task_finish":
                self.bulk_card.add_finished(1)
            elif event_type == "task_error":
                self.bulk_card.add_finished(1)
            return

        # 停止事件 (Stop event)
        if event_type == "stop_all":
            self.after(0, lambda: self._handle_stop_event())
            return

        # 普通模式处理 (Normal mode) - Dispatch to main thread
        self.after(0, lambda: self._handle_normal_event_safe(event_type, data))

    def _handle_stop_event(self):
        self.bulk_mode = False
        self.bulk_card = None
        for w in self.scroll_tasks.winfo_children(): w.destroy()
        self.task_widgets.clear()
        self.lbl_status_bar.configure(text="已停止所有任务")
        # Ensure queue count reset here too just in case (though stop_all_tasks_ui does it)
        self.total_queue_count = 0
        self._update_queue_label()
        self.refresh_library()

    def _handle_normal_event_safe(self, event_type, data):
        # UI 节流 (Throttling)
        current_time = time.time()
        
        # 1. 任务添加事件 (UI 不显示卡片，只更新计数)
        if event_type == "task_added":
            self.total_queue_count += 1
            self._update_queue_label()
            return
            
        # 2. 进度/状态更新
        if event_type == "progress":
             # 只有 "downloading" 状态的任务才创建/更新卡片
             if data.status == "downloading":
                 # 如果卡片不存在，创建它 (这是关键：只创建活跃任务)
                 if data not in self.task_widgets:
                     # 限制并发显示数量 (虽然 Manager 限制了，但为了安全再防一次)
                     if len(self.task_widgets) < 10: 
                         card = TaskCard(self.frame_active_tasks, data, self.stop_single_task)
                         card.pack(fill="x", pady=2)
                         self.task_widgets[data] = card
                         
                         # 既然它开始下载了，就从等待队列计数中减去
                         self.total_queue_count = max(0, self.total_queue_count - 1)
                         self._update_queue_label()
                
                 # 更新卡片内容 (节流)
                 if not hasattr(self, "_last_ui_update"): self._last_ui_update = {}
                 last_t = self._last_ui_update.get(data, 0)
                 if current_time - last_t > 0.5:
                     if data in self.task_widgets:
                         self.task_widgets[data].update_state()
                     self._last_ui_update[data] = current_time

        # 3. 任务结束/错误 (移除卡片)
        elif event_type in ["task_finish", "task_error"]:
            if data in self.task_widgets:
                #最后刷新一次状态
                self.task_widgets[data].update_state()
                
                # 刷新库 (如果是完成)
                if event_type == "task_finish":
                    self.refresh_library()

                # 延迟销毁，让用户看到"完成"
                def _remover(t=data):
                    if t in self.task_widgets:
                        try:
                            w = self.task_widgets[t]
                            if w.winfo_exists(): w.destroy()
                            del self.task_widgets[t]
                            if hasattr(self, "_last_ui_update") and t in self._last_ui_update:
                                del self._last_ui_update[t]
                        except: pass
                self.after(2000, _remover)
                
    # ------------------------------------------------------------------
    #  Queue List Logic (等待队列展开逻辑)
    # ------------------------------------------------------------------

    def toggle_queue_view(self):
        self.queue_expanded = not self.queue_expanded
        
        if self.queue_expanded:
            self.btn_toggle_queue.configure(text="📂 收起等待列表")
            self.frame_queue_list.pack(fill="both", expand=True, pady=5)
            self.refresh_queue_ui()
        else:
            self._update_queue_label_text() # Restore label
            self.frame_queue_list.pack_forget()

    def refresh_queue_ui(self):
        if not self.queue_expanded: return
        
        # Clear old items
        for w in self.frame_queue_list.winfo_children(): w.destroy()
        
        # Get tasks (Thread Safe Copy)
        tasks = self.manager.get_waiting_tasks()
        
        if not tasks:
            ctk.CTkLabel(self.frame_queue_list, text="队列为空", text_color="gray").pack(pady=20)
            return

        # Paging (Only show top 20 to prevent lag)
        limit = 20
        shown_tasks = tasks[:limit]
        
        for t in shown_tasks:
            self._create_queue_item_row(t)
            
        if len(tasks) > limit:
            ctk.CTkLabel(self.frame_queue_list, text=f"...还有 {len(tasks)-limit} 个任务...", text_color="gray").pack(pady=5)
            
    def _create_queue_item_row(self, task):
        row = ctk.CTkFrame(self.frame_queue_list, fg_color=("gray95", "gray25"), height=30)
        row.pack(fill="x", pady=1)
        
        ctk.CTkLabel(row, text="🕒", width=20).pack(side="left", padx=5)
        # Title
        title = task.title or f"ID: {task.id}"
        if len(title) > 30: title = title[:30] + "..."
        ctk.CTkLabel(row, text=title, anchor="w").pack(side="left", fill="x", expand=True)
        
        # Remove Button
        ctk.CTkButton(row, text="移除", width=50, height=20, fg_color="transparent", text_color="red", hover_color="gray",
                     command=lambda t=task: self.remove_queued_task(t)).pack(side="right", padx=5)

    def remove_queued_task(self, task):
        self.manager.cancel_task(task)
        self.refresh_queue_ui() # Refresh list immediately
        self._update_queue_label() # Update count

    def _update_queue_label(self):
        self._update_queue_label_text()
        # If queue is expanded, refresh the list too (maybe throttle this in real app, but ok for now)
        if self.queue_expanded:
            # Simple debounce could be added here
             self.after(50, self.refresh_queue_ui)

    def _update_queue_label_text(self):
        q_size = self.manager.get_queue_size()
        btn_text = "📂 收起等待列表" if self.queue_expanded else f"📂 查看等待列表 ({q_size})"
        self.btn_toggle_queue.configure(text=btn_text)
        
        if q_size == 0 and self.queue_expanded:
             self.refresh_queue_ui() # Show "Empty"
        
        if q_size > 0:
            self.btn_toggle_queue.configure(state="normal")
        else:
            # Keep enabled if expanded so user can collapse
            if not self.queue_expanded:
                self.btn_toggle_queue.configure(state="disabled")

    # ------------------------------------------------------------------
    #  Stop Logic
    # ------------------------------------------------------------------
    
    def stop_single_task(self, task):
        self.manager.cancel_task(task)
        task.message = "正在停止..."
        if task in self.task_widgets:
            self.task_widgets[task].update_state()
            
    def clear_queue_ui(self):
        # Deprecated: The user wanted "Stop All" instead of just clearing queue
        pass 
        
    def stop_all_tasks_ui(self):
        if messagebox.askyesno("全部停止", "确定要【立即停止】所有任务吗？\n - 清空所有排队\n - 强制中断正在下载的任务"):
            self.manager.stop_all_tasks()
            # Force UI refresh
            self.task_widgets.clear()
            for w in self.frame_active_tasks.winfo_children(): w.destroy()
            self._update_queue_label()
            self.lbl_status_bar.configure(text="🛑 已触发全局停止指令")

    def migrate_completed_ui(self):
        if messagebox.askyesno("迁移确认", "是否将 downloads 目录下所有状态为 [已完结] 的漫画\n移动到 [已完结] 文件夹？"):
            self.lbl_status_bar.configure(text="正在迁移完结漫画...")
            threading.Thread(target=self._backend_migrate_completed, daemon=True).start()

    def _backend_migrate_completed(self):
        if not os.path.exists(DOWNLOAD_DIR): return
        os.makedirs(COMPLETED_DIR, exist_ok=True)
        
        moved = 0
        skip = 0
        
        folders = os.listdir(DOWNLOAD_DIR)
        total = len(folders)
        
        for idx, name in enumerate(folders):
            src_path = os.path.join(DOWNLOAD_DIR, name)
            if not os.path.isdir(src_path): continue
            
            info_path = os.path.join(src_path, "info.json")
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    if data.get('status') == "已完结":
                        dest_path = os.path.join(COMPLETED_DIR, name)
                        if os.path.exists(dest_path):
                            try:
                                shutil.rmtree(dest_path)
                            except Exception as e:
                                print(f"Delete existing '{name}' failed: {e}")
                                # If delete fails, move might fail too, or maybe we just continue to try move
                        
                        shutil.move(src_path, dest_path)
                        moved += 1
                        self.after(0, lambda t=name: self.lbl_status_bar.configure(text=f"正在迁移: {t}"))
                except Exception as e:
                    print(f"Migration error {name}: {e}")
            
            # Update progress periodically
            if idx % 10 == 0:
                 self.after(0, lambda i=idx, t=total: self.lbl_status_bar.configure(text=f"扫描中 {i}/{t}"))

        self.after(0, lambda: self.lbl_status_bar.configure(text=f"✅ 迁移完成: 移动 {moved} 个, 跳过 {skip} 个 (重复)"))
        self.after(0, self.refresh_library)

if __name__ == "__main__":
    app = App()
    app.mainloop()
