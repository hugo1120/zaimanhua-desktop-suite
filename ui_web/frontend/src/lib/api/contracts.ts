export interface SessionResponse {
  username: string;
  logged_in: boolean;
  remember_password: boolean;
  remembered_password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  remember_password: boolean;
}

export interface OperationResponse {
  ok: boolean;
  message: string;
}

export interface SettingsResponse {
  username: string;
  has_token: boolean;
  max_books: number;
  max_images: number;
  download_dir: string;
}

export interface SettingsUpdateRequest {
  max_books: number;
  max_images: number;
  download_dir?: string;
}

export interface SearchItem {
  id: string;
  title: string;
  author: string;
  source: string;
  status: string;
  cover_url: string;
  description: string;
}

export interface SearchResponse {
  keyword: string;
  items: SearchItem[];
}

export interface AddDownloadRequest {
  id: string;
  title?: string;
  cover?: string;
}

export interface RecentUpdateItem {
  id: string;
  title: string;
  cover: string;
  author: string;
  status: string;
  latest: string;
  time: string;
}

export interface RecentUpdatesResponse {
  page: number;
  items: RecentUpdateItem[];
}

export interface DownloadTaskItem {
  id: string;
  title: string;
  cover: string;
  status: string;
  progress: number;
  message: string;
  total_chapters: number;
  done_chapters: number;
  failed_chapters: number;
}

export interface DownloadQueueResponse {
  active: DownloadTaskItem[];
  waiting: DownloadTaskItem[];
}

export interface LibraryItem {
  id: string;
  title: string;
  author: string;
  status: string;
  description: string;
  path: string;
  cover_path: string;
  mtime?: number;
  last_update_ts?: number;
  last_update_text?: string;
  latest_chapter?: string;
}

export interface LibraryResponse {
  items: LibraryItem[];
  total: number;
  source: string;
}

export interface CrawlerStatusResponse {
  running: boolean;
  last_message: string;
  max_known_id: number;
}

export type CrawlerStatus = CrawlerStatusResponse;

export interface CrawlerStartRequest {
  start_id: number;
  end_id: number;
}

export interface BackendEvent<T = unknown> {
  type: string;
  payload: T | null;
}

export interface MangaDetail {
  id: string;
  title: string;
  description: string;
  author: string;
  status: string;
  cover_url: string;
}

export interface LibraryRepairResponse {
  ok: boolean;
  message: string;
  scanned: number;
  fixed: number;
  skipped: number;
}
