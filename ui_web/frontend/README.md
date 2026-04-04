# Zaimanhua WebUI Frontend

## 本机开发启动

推荐在仓库根目录先执行：

```powershell
./start_webui_dev.bat
```

`start_webui_dev.bat` 会在 backend `8001-8010`、frontend `5173-5182` 中选空闲端口，所选端口会写入根目录的 `.webui_ports`，可以配合 `./restart_webui_dev.bat` 与 `./stop_webui_dev.bat` 使用来重启或停止开发环境。

### 1. 启动 backend

在仓库根目录执行：

```powershell
python -m uvicorn "zaimanhua.backend.api.app:create_app" --factory --host 127.0.0.1 --port 8001
```

说明：

- backend 入口是 `create_app`，不是模块级 `app`
- 如果不使用脚本启动，请确保当前终端保持运行以防端口被回收

### 2. 启动 frontend

在 `ui_web/frontend` 目录执行：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

浏览器访问：

```text
http://127.0.0.1:5173
```

说明：

- Vite 开发态默认将 `/api` 与 `/ws` 代理到 `127.0.0.1:8001`
- 如果 backend 不在 `8001`，优先运行根目录脚本；必须手动启动时，在启动 frontend 前显式设置 `VITE_BACKEND_PORT`

## backend 不在默认端口时

如果 backend 手动改到其他端口（比如 `8002`），前端开发态优先通过 `VITE_BACKEND_PORT` 启动。

### 1. backend 改到 8002

在仓库根目录执行：

```powershell
python -m uvicorn "zaimanhua.backend.api.app:create_app" --factory --host 127.0.0.1 --port 8002
```

### 2. frontend 通过 Vite proxy 指向 8002

在 `ui_web/frontend` 目录执行：

```powershell
$env:VITE_BACKEND_PORT="8002"
npm run dev -- --host 127.0.0.1 --port 5176
```

如果是 `file:`、Tauri 壳联调或其他不走 Vite proxy 的场景，再显式指定：

```powershell
$env:VITE_BACKEND_ORIGIN="http://127.0.0.1:8002"
npm run dev -- --host 127.0.0.1 --port 5176
```

浏览器访问：

```text
http://127.0.0.1:5176
```

说明：

- `VITE_BACKEND_PORT` 用于 Vite dev proxy
- `VITE_BACKEND_ORIGIN` 用于直接拼接 HTTP / WebSocket 目标地址

## 自动验证

推荐优先在仓库根目录执行：

```powershell
./run_webui_validation.bat
```

它会按顺序执行：

1. `python -m pytest -q`
2. `cd "ui_web/frontend"; npm test -- --run`
3. `cd "ui_web/frontend"; npm run build`

如果 frontend Vitest 在受限终端报 `spawn EPERM`，请改到正常本机终端补跑该命令，并在任务结论中写明结果。

## 本机浏览器手工 Smoke 清单

建议按这个顺序检查：

1. 打开 `/login`
2. 确认未登录时不会直接进入 `/search`
3. 输入账号密码登录
4. 登录成功后确认默认进入 `/search`
5. 在搜索页输入关键词，确认结果能展示
6. 点击任一结果的“下载”，确认没有前端报错
7. 打开“最近更新”页，点击“下一页”，确认卡片仍保留、内容正常切换
8. 在最近更新页点击“下载”，确认请求正常发出
9. 打开“下载队列”页，确认能看到快照数据
10. 如果后台有下载任务，确认任务状态会自动更新；断开 backend 后恢复，再确认页面会重新拉取队列
11. 打开“书库”页，确认首屏能展示列表
12. 在“书库”页执行筛选、刷新和“更新”操作，确认没有前端报错
13. 打开“设置”页，修改并发并保存，再启动索引更新，确认状态文案会随事件变化
14. 在“书库”页点击“更新全部”，确认页面在处理中仍可见进度反馈，不会整页卡死
15. 在“下载队列”页点击“停止全部”，确认按钮立即进入提交态，并看到停止摘要文案
16. 如果触发了停止全部，确认后续任务状态会继续刷新，不会停留在无反馈状态

## 建议关注的回归点

- 登录后如果是从受保护页面跳回，应该回到原页面，而不是总是跳 `/search`
- 非法外部回跳地址应该被忽略，并回落到 `/search`
- `file:` 或显式 `VITE_BACKEND_ORIGIN` 场景下，HTTP 和 WebSocket 都应连到同一个 backend

## 结束时怎么收尾

优先在仓库根目录执行 `./stop_webui_dev.bat`。如果是手动启动的 backend/frontend，各自在对应终端停止运行，并按实际使用端口检查端口释放：

```powershell
netstat -ano | Select-String ":8001|:8002"
netstat -ano | Select-String ":5173"
netstat -ano | Select-String ":5176"
```

## 验证结果记录

每次准备结束开发任务时，至少记录：

- `python -m pytest -q` 是否通过
- frontend Vitest 是否通过；如果没通过，是否因为 `spawn EPERM`
- `npm run build` 是否通过
- 手工 smoke 实际执行了哪些条目
