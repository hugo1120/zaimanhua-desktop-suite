# Library Smart Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**同步状态（2026-05-19）：** 智能更新后端接口、前端入口、回归测试和 README smoke 清单已在当前代码中落地；reviewer subagent 记录未在仓库文档中找到，保持对应项未完成。

**Goal:** 把书库页改成缓存优先，并新增“智能更新”路径，只处理最近更新里真正需要补更的本地漫画，同时保留全量补漏入口。

**Architecture:** 后端在 `LibraryService` 中新增“智能更新候选”接口，直接用书库缓存和最近更新 API 计算候选列表，不触发本地目录扫描。前端书库页移除挂载自动刷新，新增 `智能更新` 按钮，同时把现有重操作按钮明确成 `全量更新`，让默认路径和补漏路径分离。

**Tech Stack:** FastAPI、Pydantic、React 19、Mantine 8、React Query、Vitest、Pytest

---

**执行约束：** 按仓库约定，本计划不包含 `git commit` / `git push` 步骤；实现完成后先做独立 Code Review，再做编译与测试。

### Task 1: 锁定后端智能更新筛选规则

**Files:**
- Create: `tests/test_library_service.py`

- [x] 新增 pytest 用例，构造临时书库缓存和假 API，覆盖四个场景：远端比本地新时入选、本地已最新时跳过、缺少本地 id 时跳过并计数、最近更新跨页重复 id 只保留一次。
- [x] 用单独用例覆盖“最近更新接口异常时返回明确失败，不回退为全量更新”。
- [x] 运行 `python -m pytest -q "tests/test_library_service.py"`，预期在新方法和新响应模型尚未实现前失败。

### Task 2: 实现后端智能更新候选接口

**Files:**
- Modify: `zaimanhua/backend/schemas/library.py`
- Modify: `zaimanhua/backend/schemas/__init__.py`
- Modify: `zaimanhua/backend/app_services/library_service.py`
- Modify: `zaimanhua/backend/api/routes/library.py`
- Modify: `zaimanhua/services/api.py`

- [x] 在 `library.py` 中新增智能更新响应模型，至少包含候选 `items`、`scanned_pages`、`recent_total`、`matched_total`、`candidate_total`、`missing_id_total` 和消息字段。
- [x] 在 `api.py` 中新增一个面向智能更新的原始最近更新接口，例如 `get_recent_updates_raw(page)`，返回包含 `id`、`title`、`last_updatetime` 等原始字段的列表；请求失败时不要静默吞掉错误，要让上层能明确判定失败。
- [x] 在 `LibraryService` 里新增候选生成方法，直接基于缓存恢复出的书库条目构建 `local_by_id`，扫描最近更新固定页数上限，按 `remote_ts > local.last_update_ts` 规则筛候选并去重。
- [x] 为缺少 `id` 的本地作品做单独计数，供前端提示用户后续使用“补全”。
- [x] 在 `library` 路由新增智能更新接口，例如 `POST /api/library/smart-update`，复用现有登录校验。
- [x] 重新运行 `python -m pytest -q "tests/test_library_service.py"`，确认新增测试通过。

### Task 3: 锁定书库页缓存优先与双更新入口行为

**Files:**
- Modify: `ui_web/frontend/src/pages/library/library-page.test.tsx`

- [x] 改写现有书库页测试，明确断言页面挂载时只拉取 `fetchLibrary()`，不再自动调用 `refreshLibrary()`。
- [x] 新增 `智能更新` 用例，mock 智能更新候选接口只返回少量作品，断言前端只对候选作品调用 `addDownload()`。
- [x] 保留 `全量更新` 回归用例，断言旧的批量入队和进度统计仍然可用。
- [x] 新增缓存提示与“无可更新作品”反馈断言，防止文案回退。
- [x] 运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/library/library-page.test.tsx"`，预期在接口和 UI 未落地前失败。

### Task 4: 实现前端缓存优先与智能更新 UI

**Files:**
- Modify: `ui_web/frontend/src/lib/api/contracts.ts`
- Modify: `ui_web/frontend/src/lib/api/library.ts`
- Modify: `ui_web/frontend/src/pages/library/library-page.tsx`

- [x] 在前端 contracts 中新增智能更新响应类型，并在 `library.ts` 中新增对应 API 调用函数。
- [x] 删除书库页挂载后的自动 `refreshMutation.mutate()`，让首屏只依赖 `fetchLibrary()`。
- [x] 当后端返回 `source === "cache"` 时，显示“当前显示缓存，未校验磁盘”的轻提示；手动点击“刷新”后再更新反馈文案。
- [x] 新增 `智能更新` 按钮，调用候选接口后仅将候选条目批量入队；候选为空时直接提示并停止。
- [x] 将旧的重操作按钮改名为 `全量更新`，保留原有整库批量入队逻辑，作为手动补漏入口。
- [x] 把现有“本地已存在”文案改成准确表述，例如“队列重复”，避免把“已在下载队列中”和“磁盘已有内容”混为一谈。
- [x] 重新运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/library/library-page.test.tsx"`，确认书库页测试通过。

### Task 5: 更新回归文档与人工验证清单

**Files:**
- Modify: `ui_web/frontend/README.md`

- [x] 更新书库页回归说明，把“更新全部”拆成“智能更新”和“全量更新”两条路径。
- [x] 增加一条人工验证：已有缓存时首次打开书库页不应触发刷新按钮 loading。
- [x] 增加一条人工验证：智能更新空结果时不应产生任何入队请求。

### Task 6: 独立 Code Review

**Files:**
- Reuse: 本次改动涉及的后端、前端和文档文件

- [ ] 启动 reviewer subagent，对智能更新候选规则、缓存优先行为、文案准确性和回归测试覆盖做独立审查。
- [ ] 如果 reviewer 提出高优先级问题，先回到对应实现任务修复，再继续后续验证。

### Task 7: 编译与测试

**Files:**
- Reuse: 本次改动涉及的后端、前端和文档文件

- [x] 运行 `python -m pytest -q`
- [x] 运行 `npm --prefix "ui_web/frontend" run test -- run "src/pages/library/library-page.test.tsx"`（由全量 Vitest 覆盖）
- [x] 运行 `npm --prefix "ui_web/frontend" run build`
- [x] 记录任何外部阻塞；只有在测试通过或阻塞明确后，才宣布任务完成。
