# docs 专题索引

> 本页是 `docs/` 的专题导航，不是规则源。  
> 红线与约束以 `AGENTS.md` 为准；执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准；稳定事实与长期共识以 `MEMORY.md` 为准。

## 使用方式

1. 只有在确认问题属于背景说明、历史方案、经验细节、结构说明时，才进入 `docs/`。
2. 若不知道该看哪篇，先看本页，再按主题下钻。
3. 若 `docs/` 内容与 `AGENTS.md`、`docs/project-goals-and-plan.md`、`SKILL.md`、`MEMORY.md` 冲突，以上四者优先。

## 当前高频入口

- 当前阶段主线、阶段目标、验收标准、风险边界：[`project-goals-and-plan.md`](./project-goals-and-plan.md)
- 本周优先级、是否支撑 P0、是否属于插队：[`current-priority-checklist.md`](./current-priority-checklist.md)
- CST 建模、结果读取、导出、session 相关经验：[`cst-modeling-notes.md`](./cst-modeling-notes.md)
- 仓库结构、标准任务目录、关键源码位置：[`project-layout.md`](./project-layout.md)
- run 目录、日志、导出物和状态文件如何分层落盘：[`file_management_rules.md`](./file_management_rules.md)
- 历史优化方案与旧架构思路：[`optimization_plan.md`](./optimization_plan.md)

## 按主题查

| 主题 | 先看文档 | 主要回答什么 | 状态 |
| --- | --- | --- | --- |
| 当前主线与阶段边界 | [`project-goals-and-plan.md`](./project-goals-and-plan.md) | 当前要解决什么、验收标准是什么、什么暂不做 | `current` |
| 本周优先级 | [`current-priority-checklist.md`](./current-priority-checklist.md) | 新任务是否直接支撑 P0、能不能插队 | `current` |
| 建模与结果经验 | [`cst-modeling-notes.md`](./cst-modeling-notes.md) | 建模细节、远场/S11/session/导出相关坑和经验 | `reference` |
| 目录结构与源码入口 | [`project-layout.md`](./project-layout.md) | 仓库里各目录做什么、关键源码在哪 | `reference` |
| 文件管理与 run 落盘 | [`file_management_rules.md`](./file_management_rules.md) | task/run 目录、日志、导出和分析产物如何归类 | `reference` |
| 历史优化思路 | [`optimization_plan.md`](./optimization_plan.md) | 旧阶段的优化架构设想和背景 | `historical` |

## 按问题查

- 想判断“这件事现在该不该做、算不算偏离主线”：先看 [`project-goals-and-plan.md`](./project-goals-and-plan.md)，再看 [`current-priority-checklist.md`](./current-priority-checklist.md)。
- 想确认“某个建模、results、导出或 session 坑以前有没有踩过”：先看 [`cst-modeling-notes.md`](./cst-modeling-notes.md)。
- 想确认“路径应该放哪、run 结构怎么分、哪些文件该落在哪层”：先看 [`file_management_rules.md`](./file_management_rules.md)，再补看 [`project-layout.md`](./project-layout.md)。
- 想快速知道“仓库哪里是正式入口、哪里只是辅助目录”：先看 [`project-layout.md`](./project-layout.md)。
- 想了解“某个旧文档是不是当前主线依据”：先看其状态；标记为 `historical` 的文档只作背景参考，不直接指导当前任务。

## 维护规则

- `docs/` 新增、删除或明显改边界后，必须同步更新本页。
- 每篇文档至少应能在本页标明：主题、主要用途、当前状态。
- 若某篇文档已经过时但仍保留，应明确标记为 `historical`，避免被误当成当前依据。
