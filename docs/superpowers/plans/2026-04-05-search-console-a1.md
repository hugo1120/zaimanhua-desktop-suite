# Search Console A1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把搜索页改成更成熟的桌面“搜索控制台”布局，并让昼夜切换的视觉差异更明显。

**Architecture:** 保持现有 React + Mantine 结构不变，只重构搜索页 JSX 层级和 `index.css` 中的搜索页专属样式。结果头信息、搜索控制台、卡片网格统一为一套视觉语言，`返回推荐` 固定放在结果头右侧。

**Tech Stack:** React 19、Mantine 8、React Query、Vitest、Vite

---

### Task 1: 锁定搜索页布局行为

**Files:**
- Modify: `ui_web/frontend/src/pages/search/search-page.test.tsx`

- [ ] 为搜索结果态补回归断言：结果标题、数量、关键词标签、右侧 `返回推荐` 按钮都存在。
- [ ] 运行前端测试命令，记录当前环境里的失败状态或阻塞信息。

### Task 2: 重构搜索页结构

**Files:**
- Modify: `ui_web/frontend/src/pages/search/search-page.tsx`

- [ ] 把页面根节点改成搜索页专属容器。
- [ ] 把搜索条改成控制台结构，去掉内联样式。
- [ ] 把搜索结果头拆成左侧信息区和右侧操作区，`返回推荐` 固定右侧。
- [ ] 为最近更新态补一个与搜索结果态一致的标题区。

### Task 3: 重做搜索页视觉样式

**Files:**
- Modify: `ui_web/frontend/src/styles/index.css`

- [ ] 新增搜索控制台、结果头、关键词标签、操作区样式。
- [ ] 强化深色与浅色模式的背景、边框、阴影、强调色差异。
- [ ] 调整卡片网格和卡片信息层级，让页面在宽屏和常规桌面宽度下都更均衡。

### Task 4: 构建验证与打包

**Files:**
- Reuse: `build_exe.bat`
- Reuse: `dist/hugo-zaimanhua`

- [ ] 运行 `python -m pytest -q`
- [ ] 运行 `npm run build`
- [ ] 重新打包并核对 EXE 时间戳与包内前端资源名
