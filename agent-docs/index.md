# Agent Docs Index

本索引用于记录项目文档位置、适用场景和长期有效事实。局部实现细节不写入这里，优先更新既有文档。

## 文档入口

- [README.md](../README.md)：仓库总览、启动、验证和打包入口，面向首次接手者。
- [README-DESKTOP.md](../README-DESKTOP.md)：桌面版专属工作流和隔离原则。
- [ui_web/frontend/README.md](../ui_web/frontend/README.md)：前端开发、后端联调、验证和手工 smoke 清单。
- [AGENTS.md](../AGENTS.md)：当前项目的 Agent 运行约定和关键事实。

## 历史计划与设计

- [docs/superpowers/plans/2026-04-05-search-console-a1.md](../docs/superpowers/plans/2026-04-05-search-console-a1.md)：搜索控制台视觉与布局计划。
- [docs/superpowers/plans/2026-04-05-library-smart-update.md](../docs/superpowers/plans/2026-04-05-library-smart-update.md)：书库缓存优先与智能更新计划。
- [docs/superpowers/plans/2026-04-05-index-crawler-recovery.md](../docs/superpowers/plans/2026-04-05-index-crawler-recovery.md)：索引更新失败可见性恢复计划。
- [docs/superpowers/specs/2026-04-05-library-smart-update-design.md](../docs/superpowers/specs/2026-04-05-library-smart-update-design.md)：书库智能更新设计。
- [docs/superpowers/specs/2026-04-05-index-crawler-recovery-design.md](../docs/superpowers/specs/2026-04-05-index-crawler-recovery-design.md)：索引更新恢复设计。

## 长期有效事实

- 后端入口是 `zaimanhua.backend.api.app:create_app`，不是模块级 `app`。
- 前端开发态 Vite 默认代理到 `127.0.0.1:8001`，可通过 `VITE_BACKEND_PORT` 调整代理端口，通过 `VITE_BACKEND_ORIGIN` 调整直连后端地址。
- 当前仓库根目录没有 WebUI 启停辅助脚本；使用 README 中记录的手动命令。
- `build_exe.bat` 会删除并重建 `build/` 和 `dist/`，执行前需要确认可以覆盖现有打包产物。
