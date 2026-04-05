from __future__ import annotations

import hashlib
import os
import ssl
import time
from typing import Any, Dict, List, Optional

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

class CustomSSLAdapter(HTTPAdapter):
    """强制兼容旧版 SSL 协议"""

    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = create_urllib3_context()
        try:
            ctx.set_ciphers('ALL:@SECLEVEL=1')
        except:
            pass
        try:
            ctx.options |= 4
        except:
            pass
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = urllib3.poolmanager.PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx)


class ZaimanhuaAPI:

    def __init__(self):
        self.base_url = 'https://v4api.zaimanhua.com/app/v1'
        self.account_url = 'https://account-api.zaimanhua.com/v1'
        self.mobile_url = 'https://m.zaimanhua.com'
        self.web_search_url = 'https://manhua.zaimanhua.com/dynamic/'
        self.token = ''
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.mount('https://', CustomSSLAdapter())
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36', 'Accept': 'application/json'})

    def close(self) -> None:
        self.session.close()

    def _md5_hash(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_headers(self, include_token: bool=True) -> Dict[str, str]:
        headers = self.session.headers.copy()
        if include_token and self.token:
            headers['authorization'] = f'Bearer {self.token}'
        return headers

    def login(self, username, password) -> bool:
        try:
            password_hashed = self._md5_hash(password)
            data = {'username': username, 'passwd': password_hashed}
            res = self.session.post(f'{self.account_url}/login/passwd', data=data, headers=self._get_headers(False), verify=False)
            if res.status_code == 200 and res.json().get('errno') == 0:
                self.token = res.json()['data']['user'].get('token', '')
                return True
        except Exception as e:
            print(f'登录错误: {e}')
        return False

    def get_manga_detail(self, manga_id: str) -> Dict[str, Any]:
        try:
            url = f'{self.base_url}/comic/detail/{manga_id}?_v=2.2.5'
            return self.session.get(url, headers=self._get_headers(), verify=False).json()
        except:
            return {}

    def search_api(self, keyword: str) -> List[Dict[str, str]]:
        """API 搜索 (V10 Feature)"""
        results = []
        try:
            url = f'{self.base_url}/search/comic?_v=2.2.5&limit=20&page=1&q={keyword}'
            res = self.session.get(url, headers=self._get_headers(), verify=False)
            if res.status_code == 200:
                data = res.json()
                if data.get('errno') == 0:
                    payload = data.get('data') or {}
                    for item in payload.get('data') or []:
                        title = item.get('title')
                        mid = str(item.get('comic_id'))
                        cover = item.get('cover')
                        authors = [a.get('tag_name') for a in (item.get('authors') or []) if isinstance(a, dict)]
                        author_str = ','.join(authors) if authors else ''
                        status_text = self.get_status_label(item.get('status') or []) or ''
                        if title and mid:
                            results.append({
                                'title': title,
                                'id': mid,
                                'author': author_str,
                                'source': 'api',
                                'status': status_text,
                                'cover_url': cover,
                            })
        except Exception as e:
            print(f'API Search Error: {e}')
        return results

    def search_web_scrape(self, keyword: str) -> List[Dict[str, str]]:
        """原有网页爬虫搜索 (保留作为 fallback)"""
        results = []
        clean_kw = keyword.replace('_', ' ').strip()
        target_url = self.web_search_url + clean_kw
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://manhua.zaimanhua.com/'}
            res = requests.get(target_url, headers=headers, verify=False, timeout=10)
            res.encoding = 'utf-8'
            if res.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, 'html.parser')
                items = soup.select('p.title > a[href^="/details/"]')
                count = 0
                for a in items:
                    if count >= 100:
                        break
                    title = a.get('title', '').strip() or a.get_text().strip()
                    href = a.get('href', '')
                    mid = href.rstrip('/').split('/')[-1]
                    if title and mid:
                        if not any((d['id'] == mid for d in results)):
                            results.append({'title': title, 'id': mid, 'source': 'web'})
                            count += 1
        except Exception as e:
            print(f'Web Search Error: {e}')
        return results

    def search_dynamic(self, keyword: str) -> List[Dict[str, str]]:
        """解析网页搜索结果 + ID智能识别 + API优先"""
        results = []
        if keyword.isdigit():
            detail = self.get_manga_detail(keyword)
            if detail and detail.get('errno') == 0:
                real_title = detail['data']['data'].get('title', f'ID: {keyword}')
                results.append({'title': real_title, 'id': keyword, 'source': 'id_match'})
            else:
                results.append({'title': f'ID: {keyword}', 'id': keyword, 'source': 'id_guess'})
        api_results = self.search_api(keyword)
        if api_results:
            results.extend(api_results)
        if not api_results:
            print('API returned no results, falling back to Web Scrape...')
            web_results = self.search_web_scrape(keyword)
            existing_ids = {r['id'] for r in results}
            for w in web_results:
                if w['id'] not in existing_ids:
                    results.append(w)
        return results

    def get_chapter_images(self, manga_id: str, chapter_id: str) -> Dict[str, Any]:
        """获取章节图片列表 (参考 Tachiyomi 扩展实现)"""
        try:
            url = f'{self.base_url}/comic/chapter/{manga_id}/{chapter_id}?_v=2.2.5'
            headers = self._get_headers()
            headers['Platform'] = 'h5'
            result = self.session.get(url, headers=headers, verify=False).json()
            data = result.get('data', {}).get('data', {})
            page_urls = data.get('page_url') or data.get('page_url_hd') or []
            if page_urls and not data.get('page_url'):
                data['page_url'] = page_urls
            can_read = data.get('canRead', True)
            if can_read == False or can_read == 0:
                print(f'[权限不足] 章节 {chapter_id} 需要升级账号等级')
                return {'errno': -1, 'errmsg': '用户权限不足，请升级账号等级'}
            return result
        except Exception as e:
            print(f'获取章节图片失败: {e}')
            return {}

    def _get_image_extension(self, data: bytes, url: str) -> str:
        if '.' in url:
            ext = url.split('.')[-1].split('?')[0].lower()
            if ext in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                return '.jpg' if ext == 'jpeg' else f'.{ext}'
        if data.startswith(b'\xff\xd8\xff'):
            return '.jpg'
        if data.startswith(b'\x89PNG'):
            return '.png'
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            return '.webp'
        if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return '.gif'
        return '.jpg'

    def download_image_content(self, url: str) -> Optional[bytes]:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': self.mobile_url}
        for attempt in range(3):
            try:
                res = self.session.get(url, headers=headers, timeout=15, verify=False)
                if res.status_code == 200:
                    return res.content
            except Exception:
                pass
            if attempt < 2:
                time.sleep(0.5)
        return None

    def _sanitize(self, name: str) -> str:
        return ''.join([c if c not in '<>:"/\\|?*' else '_' for c in name]).strip()

    def download_cover(self, url: str, folder_path: str, filename: str):
        """下载封面并保存 (如果有过一次就不要在求封面了)"""
        if not url:
            return
        try:
            full_path = os.path.join(folder_path, filename)
            if os.path.exists(full_path):
                return
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'Referer': 'https://manhua.zaimanhua.com/'}
            res = self.session.get(url, headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                with open(full_path, 'wb') as f:
                    f.write(res.content)
        except Exception as e:
            print(f'Cover download failed: {e}')

    def get_status_label(self, tags: list) -> str:
        """解析状态标签"""
        for t in tags:
            try:
                tid = int(t.get('tag_id', 0))
                if tid == 2310:
                    return '已完结'
                if tid == 2309:
                    return '连载中'
            except:
                pass

    def get_recent_updates_raw(self, page: int=1) -> List[Dict[str, Any]]:
        """获取最近更新原始数据，失败时抛出异常供上层判定。"""
        page_number = int(page or 1)
        if page_number < 1:
            page_number = 1

        url = f'{self.base_url}/comic/update/list/0/{page_number}'
        res = self.session.get(url, headers=self._get_headers(), verify=False, timeout=8)
        res.raise_for_status()

        payload = res.json()
        if payload.get('errno', 0) != 0:
            raise RuntimeError(f"recent updates api errno={payload.get('errno')}")

        raw_data = payload.get('data')
        if not isinstance(raw_data, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            mid = item.get('comic_id')
            if not mid or mid == 0:
                mid = item.get('id')
            if not mid:
                continue
            normalized_item = dict(item)
            normalized_item['id'] = str(mid)
            normalized_item['title'] = str(item.get('title') or item.get('name') or '')
            try:
                normalized_item['last_updatetime'] = int(item.get('last_updatetime') or 0)
            except (TypeError, ValueError):
                normalized_item['last_updatetime'] = 0
            normalized.append(normalized_item)
        return normalized

    def get_recent_updates(self, page: int=1) -> List[Dict[str, Any]]:
        """获取最近更新 (V10 Feature)"""
        results = []
        try:
            raw_data = self.get_recent_updates_raw(page)
            for item in raw_data:
                cover = item.get('cover')
                authors = item.get('authors', '')
                status = item.get('status', '')
                last_ch = item.get('last_update_chapter_name', '')
                ts = item.get('last_updatetime', 0)
                import datetime
                time_str = ''
                if ts:
                    try:
                        dt = datetime.datetime.fromtimestamp(int(ts))
                        time_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                results.append({'id': str(item.get('id') or ''), 'title': str(item.get('title') or ''), 'cover': cover, 'author': authors, 'status': status, 'latest': last_ch, 'time': time_str})
        except Exception as e:
            print(f'Recent Updates Error: {e}')
        return results
