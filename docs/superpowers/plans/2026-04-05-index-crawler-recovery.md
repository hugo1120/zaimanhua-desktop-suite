# Index Crawler Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**同步状态（2026-05-19）：** 索引更新异常可见性、设置页错误反馈和相关回归测试已在当前代码中落地；打包核验会执行 `build_exe.bat` 并清理 `build/` / `dist/`，本次文档同步未执行。

**Goal:** 在不改变现有索引抓取主逻辑的前提下，把旧版索引更新外层流程补回当前桌面版，并重新打出可直接覆盖发布目录的完整应用。

**Architecture:** 后端继续复用现有 `CrawlerService -> MangaCrawler` 链路，只补线程外层异常处理、任务结束态和请求失败摘要。前端继续使用现有设置页入口，只增强索引更新的错误反馈；最后按现有脚本重新打包完整桌面版。

**Tech Stack:** FastAPI、Pydantic、Python Requests、React 19、Mantine 8、React Query、Vitest、Pytest、PyInstaller

---

**执行约束：** 按仓库约定，本计划不包含 `git commit` / `git push`；实现完成后先做独立 Code Review，再做测试与打包。

### Task 1: 锁定失败可见性回归测试

**Files:**
- Create: `tests/test_crawler_service.py`
- Modify: `ui_web/frontend/src/pages/settings/settings-page.test.tsx`

- [x] 新增 `CrawlerService` 回归测试，覆盖“后台线程抛错后最终状态保留 `爬虫错误` 消息”。
- [x] 新增 `MangaCrawler` 回归测试，覆盖“全部请求失败且没有新数据时返回失败摘要”和“会话 `trust_env` 与主 API 客户端一致”。
- [x] 在设置页测试中新增 `startCrawler()` 失败场景，断言用户能看到错误提示。
- [x] 运行 `python -m pytest -q "tests/test_crawler_service.py"`，确认新增后端测试先失败。
- [x] 运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/settings/settings-page.test.tsx"`，确认前端错误提示测试先失败。

### Task 2: 实现后端索引任务恢复逻辑

**Files:**
- Modify: `zaimanhua/backend/app_services/crawler_service.py`
- Modify: `zaimanhua/services/crawler.py`

- [x] 在 `CrawlerService` 的后台线程执行路径中补回 `try/except/finally` 外层控制，确保线程异常能转换成状态消息。
- [x] 在 `MangaCrawler` 中补充与主 API 客户端一致的会话环境配置。
- [x] 在 `MangaCrawler` 中补充请求失败摘要，仅在“全部失败且没有新增数据”时回传明确错误，不改变正常抓取路径。
- [x] 重新运行 `python -m pytest -q "tests/test_crawler_service.py"`，确认后端回归测试通过。

### Task 3: 实现设置页错误反馈

**Files:**
- Modify: `ui_web/frontend/src/pages/settings/settings-page.tsx`

- [x] 为索引更新的启动请求补充错误状态展示，保留现有布局和按钮行为。
- [x] 成功启动、停止或收到新进度时清理过期错误提示，避免旧错误残留。
- [x] 重新运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/settings/settings-page.test.tsx"`，确认前端回归测试通过。

### Task 4: 独立 Code Review

**Files:**
- Reuse: 本次索引更新涉及的后端、前端和文档文件

- [ ] 以代码审查视角重新检查：异常是否仍会被吞掉、最终状态是否可能被覆盖、前端错误提示是否会残留、测试是否覆盖了失败路径。
- [ ] 若发现高优先级问题，先修复再进入后续验证。

### Task 5: 编译、测试与打包

**Files:**
- Reuse: 本次索引更新涉及的后端、前端和打包脚本

- [x] 运行 `python -m pytest -q "tests/test_crawler_service.py"`（由全量 pytest 覆盖）
- [x] 运行 `python -m pytest -q`
- [x] 运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/settings/settings-page.test.tsx"`（由全量 Vitest 覆盖）
- [x] 运行 `npm --prefix "ui_web/frontend" run build`
- [ ] 运行 `build_exe.bat`（需先确认可清理 `build/` / `dist/`）
- [ ] 确认产物目录 `dist/hugo-zaimanhua/` 存在且可作为完整应用直接覆盖发布目录。
