# 项目级 Agent 说明

本文件记录 `zaimanhua-desktop-suite` 的项目事实。通用工作约束继续遵循用户级 `~/.codex/AGENTS.md`。

## 项目结构

- `main_desktop.py`：桌面入口，负责设置运行时环境变量、启动 Uvicorn 后端、挂载前端构建产物并创建 PyWebView 窗口。
- `zaimanhua/backend/api/app.py`：FastAPI 工厂入口，使用 `create_app()` 而不是模块级 `app`。
- `zaimanhua/backend/api/routes/`：后端路由；当前主要路由前缀为 `/api`，WebSocket 为 `/ws/events`。
- `zaimanhua/backend/app_services/`：后端应用服务层。
- `zaimanhua/services/`：再漫画 API、下载、索引抓取等底层服务。
- `ui_web/frontend/`：React 19 + Mantine 8 + Vite 前端。
- `docs/superpowers/`：历史功能计划与设计文档；状态以文档内复选框为准。
- `agent-docs/index.md`：项目文档索引和长期有效事实入口。

## 常用命令

```powershell
python -m uvicorn "zaimanhua.backend.api.app:create_app" --factory --host 127.0.0.1 --port 8001
npm --prefix "ui_web/frontend" run dev -- --host 127.0.0.1 --port 5173
python "main_desktop.py"
python -m pytest -q
npm --prefix "ui_web/frontend" run test -- run
npm --prefix "ui_web/frontend" run build
```

当前仓库根目录没有 `start_webui_dev.bat`、`restart_webui_dev.bat`、`stop_webui_dev.bat` 或 `run_webui_validation.bat`，开发与验证默认使用上面的手动命令。

## 运行时与打包事实

- `main_desktop.py` 会默认设置 `ZAIMANHUA_ROOT`、`ZAIMANHUA_DOWNLOAD_DIR`、`ZAIMANHUA_CONFIG_PATH`。
- `BackendContainer` 会从配置目录加载 `manga_list.txt` 和 `library_cache.json`，书库缓存与索引文件跟随配置目录。
- `build_exe.bat` 在打包前会删除 `build/` 和 `dist/`，执行前应确认当前产物目录可以被重建。
- PyInstaller 产物目录为 `dist/hugo-zaimanhua/`，脚本会把 `manga_list.txt`、`zaimanhua/`、前端 `dist/` 和图标资源打入应用。

## 当前关键接口

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/search?q=...`
- `GET /api/recent-updates?page=1&refresh=false`
- `GET /api/manga/{manga_id}`
- `GET /api/library`
- `POST /api/library/refresh`
- `POST /api/library/repair`
- `POST /api/library/smart-update`
- `POST /api/library/open-folder`
- `GET /api/downloads/queue`
- `POST /api/downloads`
- `POST /api/downloads/{task_id}/cancel`
- `POST /api/downloads/stop-all`
- `GET /api/crawler/status`
- `POST /api/crawler/start`
- `POST /api/crawler/stop`
- `GET /api/covers?path=...`
- `WS /ws/events`
