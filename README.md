# 再漫画桌面套件

这是再漫画下载器的桌面版发布仓库，包含 FastAPI 后端、React/Vite 前端和 PyWebView 桌面壳。

## 快速开始

### 后端

```powershell
python -m pip install -r "requirements-desktop.txt"
python -m uvicorn "zaimanhua.backend.api.app:create_app" --factory --host 127.0.0.1 --port 8001
```

### 前端

```powershell
cd "D:/github/zaimanhua-desktop-suite/ui_web/frontend"
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

访问 `http://127.0.0.1:5173`。Vite 开发态会把 `/api` 和 `/ws` 代理到 `127.0.0.1:8001`；如果后端端口不同，启动前端前设置 `VITE_BACKEND_PORT`。

### 桌面壳

```powershell
python "D:/github/zaimanhua-desktop-suite/main_desktop.py"
```

桌面壳会自动选择本机空闲端口启动后端，并从 `ui_web/frontend/dist` 提供前端静态资源。

## 验证

```powershell
python -m pytest -q
npm --prefix "ui_web/frontend" run test -- run
npm --prefix "ui_web/frontend" run build
```

## 打包

```powershell
./build_exe.bat
```

`build_exe.bat` 会重新安装前端依赖、构建前端、安装 Python 依赖，并在打包前清理 `build/` 和 `dist/`。产物位于 `dist/hugo-zaimanhua/`。

更多桌面版约定见 [README-DESKTOP.md](README-DESKTOP.md)，前端开发细节见 [ui_web/frontend/README.md](ui_web/frontend/README.md)。
