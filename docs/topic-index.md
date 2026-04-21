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
- 当前唯一正式入口、旁路冻结范围和本周退出生产职责名单：[`formal-entry-and-bypass-audit.md`](./formal-entry-and-bypass-audit.md)
- 阶段 B 主生产链、状态落盘工具和旁路降级结果：[`phase-b-main-chain-consolidation.md`](./phase-b-main-chain-consolidation.md)
- 阶段 C 系统集成、一键迁移模式和四类系统职责：[`phase-c-system-integration-and-portable-mode.md`](./phase-c-system-integration-and-portable-mode.md)
- 轻量 CLI-first 架构决策、`prototype_optimizer` 剪枝、MCP 退场路线、runtime 与 adapter 边界：[`cli-architecture-decision.md`](./cli-architecture-decision.md)
- 其他 agent 如何正确调用 `cst_runtime`、`doctor` 兼容性自检、错误 JSON 契约和最小自检：[`cst-runtime-agent-usage.md`](./cst-runtime-agent-usage.md)
- `cst_runtime` 原生管道协议、stdin 合并规则、可串联示例和新增 results/farfield 工具：[`cst-runtime-native-pipeline.md`](./cst-runtime-native-pipeline.md)
- 2026-04-21 工作收尾、CLI 兼容性知识回收、残留问题和明日门控任务：[`2026-04-21-work-handoff.md`](./2026-04-21-work-handoff.md)
- 已归档的 CST CLI 原子工具 POC、项目身份校验和无 MCP 服务工具化验证：[`cst-cli-atomic-tools-poc.md`](./cst-cli-atomic-tools-poc.md)
- 2026-04-20 工作收尾、知识回收和明日计划：[`2026-04-20-work-handoff.md`](./2026-04-20-work-handoff.md)
- CST 建模、结果读取、导出、session 相关经验：[`cst-modeling-notes.md`](./cst-modeling-notes.md)
- 仓库结构、标准任务目录、关键源码位置：[`project-layout.md`](./project-layout.md)
- run 目录、日志、导出物和状态文件如何分层落盘：[`file_management_rules.md`](./file_management_rules.md)
- 历史优化方案与旧架构思路：[`optimization_plan.md`](./optimization_plan.md)

## 按主题查

| 主题 | 先看文档 | 主要回答什么 | 状态 |
| --- | --- | --- | --- |
| 当前主线与阶段边界 | [`project-goals-and-plan.md`](./project-goals-and-plan.md) | 当前要解决什么、验收标准是什么、什么暂不做 | `current` |
| 本周优先级 | [`current-priority-checklist.md`](./current-priority-checklist.md) | 新任务是否直接支撑 P0、能不能插队 | `current` |
| 正式入口与旁路冻结 | [`formal-entry-and-bypass-audit.md`](./formal-entry-and-bypass-audit.md) | 当前唯一正式入口是什么、哪些脚本必须退出生产职责 | `current` |
| 主生产链收口 | [`phase-b-main-chain-consolidation.md`](./phase-b-main-chain-consolidation.md) | run 创建、执行、导出、对比、状态落盘如何统一到同一主链 | `current` |
| 系统集成与一键迁移 | [`phase-c-system-integration-and-portable-mode.md`](./phase-c-system-integration-and-portable-mode.md) | MCP、Skill、知识、计划如何集成，如何打包迁移 | `current` |
| CLI-first 架构决策 | [`cli-architecture-decision.md`](./cli-architecture-decision.md) | CLI 是否应成为主调用界面、`prototype_optimizer` 是否保留、MCP 能否退场、runtime 与 adapter 如何分层 | `current` |
| Runtime Agent 使用 | [`cst-runtime-agent-usage.md`](./cst-runtime-agent-usage.md) | 其他 agent 如何发现工具、生成 args、调用 CLI、跑兼容性自检、处理错误 JSON | `current` |
| Runtime 原生管道 | [`cst-runtime-native-pipeline.md`](./cst-runtime-native-pipeline.md) | CLI 如何读取 stdin JSON、如何合并显式参数、哪些 results/farfield 能力已经迁入 runtime | `current` |
| 今日收尾与明日门控 | [`2026-04-21-work-handoff.md`](./2026-04-21-work-handoff.md) | CLI 兼容性、工具清理、残留问题、明天第一任务和 P1 门控结论 | `handoff` |
| CLI 原子工具 POC | [`cst-cli-atomic-tools-poc.md`](./cst-cli-atomic-tools-poc.md) | 早期 `tools/cst_cli.py` POC 如何验证轻量 CLI 暴露给 agent；当前脚本已归档 | `historical` |
| 早期收尾与次日计划 | [`2026-04-20-work-handoff.md`](./2026-04-20-work-handoff.md) | CLI POC 后的知识回收、次日阶段 D 计划和禁止事项 | `handoff` |
| 建模与结果经验 | [`cst-modeling-notes.md`](./cst-modeling-notes.md) | 建模细节、远场/S11/session/导出相关坑和经验 | `reference` |
| 目录结构与源码入口 | [`project-layout.md`](./project-layout.md) | 仓库里各目录做什么、关键源码在哪 | `reference` |
| 文件管理与 run 落盘 | [`file_management_rules.md`](./file_management_rules.md) | task/run 目录、日志、导出和分析产物如何归类 | `reference` |
| 历史优化思路 | [`optimization_plan.md`](./optimization_plan.md) | 旧阶段的优化架构设想和背景 | `historical` |

## 按问题查

- 想判断“这件事现在该不该做、算不算偏离主线”：先看 [`project-goals-and-plan.md`](./project-goals-and-plan.md)，再看 [`current-priority-checklist.md`](./current-priority-checklist.md)。
- 想确认“当前唯一正式入口到底是什么、哪些旧路径本周必须退出生产职责”：先看 [`formal-entry-and-bypass-audit.md`](./formal-entry-and-bypass-audit.md)。
- 想确认“主链每一步该用哪个 MCP 工具、状态和阶段记录怎么落盘”：先看 [`phase-b-main-chain-consolidation.md`](./phase-b-main-chain-consolidation.md)，再看 [`skills/cst-simulation-optimization/SKILL.md`](../skills/cst-simulation-optimization/SKILL.md)。
- 想确认“在保留 MCP 主链的同时，如何用 CLI/runtime 跑优化闭环”：看 [`skills/cst-runtime-cli-optimization/SKILL.md`](../skills/cst-runtime-cli-optimization/SKILL.md)。
- 想确认“如何一键迁移、目标机怎么初始化和校验”：先看 [`phase-c-system-integration-and-portable-mode.md`](./phase-c-system-integration-and-portable-mode.md)。
- 想确认“CLI 化应如何进入正式架构、是否会形成第二条生产链、`prototype_optimizer` 和 MCP 怎么剪枝”：先看 [`cli-architecture-decision.md`](./cli-architecture-decision.md)。
- 想确认“哪些 `cst_runtime` 命令可以用管道串起来、stdin 和 args-file 如何合并”：先看 [`cst-runtime-native-pipeline.md`](./cst-runtime-native-pipeline.md)。
- 想让其他 agent 照着调用 `cst_runtime`，或确认错误用法是否会返回 JSON：先看 [`cst-runtime-agent-usage.md`](./cst-runtime-agent-usage.md)。
- 想确认“能否不依赖 MCP 服务，用 CLI 原子工具给 agent 调用”：当前先看 [`cst-runtime-native-pipeline.md`](./cst-runtime-native-pipeline.md)；早期 POC 背景再看 [`cst-cli-atomic-tools-poc.md`](./cst-cli-atomic-tools-poc.md)。
- 想确认“某个建模、results、导出或 session 坑以前有没有踩过”：先看 [`cst-modeling-notes.md`](./cst-modeling-notes.md)。
- 想确认“路径应该放哪、run 结构怎么分、哪些文件该落在哪层”：先看 [`file_management_rules.md`](./file_management_rules.md)，再补看 [`project-layout.md`](./project-layout.md)。
- 想快速知道“仓库哪里是正式入口、哪里只是辅助目录”：先看 [`formal-entry-and-bypass-audit.md`](./formal-entry-and-bypass-audit.md)，再看 [`project-layout.md`](./project-layout.md)。
- 想了解“某个旧文档是不是当前主线依据”：先看其状态；标记为 `historical` 的文档只作背景参考，不直接指导当前任务。

## 维护规则

- `docs/` 新增、删除或明显改边界后，必须同步更新本页。
- 每篇文档至少应能在本页标明：主题、主要用途、当前状态。
- 若某篇文档已经过时但仍保留，应明确标记为 `historical`，避免被误当成当前依据。
