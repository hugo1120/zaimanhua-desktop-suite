# 桌面版专属工作流

此仓库是完全隔离的桌面版发布环境。所有桌面壳开发、打包和 UI 自适应调试都在此处进行。

### 常用操作
1. **本地调试桌面版**：
   - 安装依赖：`python -m pip install -r "requirements-desktop.txt"`
   - 构建前端：`npm --prefix "ui_web/frontend" run build`
   - 运行：`python "main_desktop.py"`
2. **一键打包**：
   - 双击运行 `build_exe.bat`
   - 注意：脚本会删除并重建 `build/` 与 `dist/`
3. **自适应调整**：
   - 修改 `ui_web/frontend/src` 中的代码。
   - 重新打包或使用 Vite 预览。
4. **验证**：
   - 后端测试：`python -m pytest -q`
   - 前端测试：`npm --prefix "ui_web/frontend" run test -- run`
   - 前端构建：`npm --prefix "ui_web/frontend" run build`

### 隔离原则
不要修改此仓库外的源码，除非需要同步核心功能。
此仓库内的修改不会自动反馈到上游主仓库，旨在为分发提供稳定的桌面版快照。
