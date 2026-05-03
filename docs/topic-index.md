# docs 专题索引

> 本页是 `docs/` 的专题导航，不是规则源。  
> 红线与约束以 `AGENTS.md` 为准；阶段目标以 `project-goals-and-plan.md` 与 `current-priority-checklist.md` 为准；执行流程以对应 Skill 为准；稳定事实与长期共识以 `MEMORY.md` 为准。

## 使用方式

1. 先判断问题类型：当前状态、阶段计划、执行流程、架构边界、经验参考、验证记录或历史背景。
2. 只读对应分类下的文档，不从平铺文件名里猜入口。
3. 若文档之间冲突，优先级为：`AGENTS.md` > `project-goals-and-plan.md` / `current-priority-checklist.md` > Skill > `MEMORY.md` > 其他 `docs/`。
4. 文档生命周期、是否常维护、是否历史归档，见 [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md)。

## 高频入口

- 想知道项目现在做到哪、哪些能力已验证、下一步工程主线是什么：[`core/project-current-status.md`](core/project-current-status.md)
- 想判断当前任务该不该做、是否偏离主线：[`project-goals-and-plan.md`](./project-goals-and-plan.md) -> [`current-priority-checklist.md`](./current-priority-checklist.md)
- 想确认文档该看哪篇、哪些文档常维护或已归档：[`core/docs-maintenance-map.md`](core/docs-maintenance-map.md)
- 想让低上下文 agent 学会 runtime/CLI：[`runtime/cst-runtime-agent-usage.md`](runtime/cst-runtime-agent-usage.md) -> [`runtime/cst-runtime-native-pipeline.md`](runtime/cst-runtime-native-pipeline.md)
- 想确认正式入口、run 落盘和主生产链：[`workflow/formal-entry-and-bypass-audit.md`](workflow/formal-entry-and-bypass-audit.md) -> [`architecture/phase-b-main-chain-consolidation.md`](architecture/phase-b-main-chain-consolidation.md)

## Core

这些文档是当前状态和阶段管理入口，应保持短、准、可维护。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`core/project-current-status.md`](core/project-current-status.md) | 当前已验证能力、工程边界、ref_0/ref_2 状态、下一步工程主线 | `current` |
| [`project-goals-and-plan.md`](./project-goals-and-plan.md) | 项目定位、阶段目标、当前主攻方向、验收标准 | `current` |
| [`current-priority-checklist.md`](./current-priority-checklist.md) | 当前优先级、当前主线、明确不做事项 | `current` |
| [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md) | docs 文档分类、生命周期、维护建议 | `current` |
| [`topic-index.md`](./topic-index.md) | docs 导航入口 | `current` |

## Architecture

这些文档解释架构决策、阶段收口和系统职责边界。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`architecture/cli-architecture-decision.md`](architecture/cli-architecture-decision.md) | CLI-first 架构决策、runtime 与 MCP adapter 边界、`prototype_optimizer` 剪枝 | `current` |
| [`architecture/phase-b-main-chain-consolidation.md`](architecture/phase-b-main-chain-consolidation.md) | 阶段 B 主生产链收口、状态落盘、旁路降级 | `current` |
| [`architecture/phase-c-system-integration-and-portable-mode.md`](architecture/phase-c-system-integration-and-portable-mode.md) | 阶段 C 系统集成、一键迁移、四类系统职责 | `current` |

## Runtime

这些文档面向 `cst_runtime`、CLI、低上下文 agent 和管道调用。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`runtime/cst-runtime-agent-usage.md`](runtime/cst-runtime-agent-usage.md) | agent 如何发现工具、生成 args、调用 CLI、处理错误 JSON | `current` |
| [`runtime/cst-runtime-native-pipeline.md`](runtime/cst-runtime-native-pipeline.md) | CLI 管道协议、stdin/args 合并、`list-pipelines`、`wait-simulation`、results/farfield 能力 | `current` |
| [`runtime/cst-session-process-management-test-plan.md`](runtime/cst-session-process-management-test-plan.md) | CST 进程/session 管理系统的 full gate 测试矩阵，覆盖 inspect/open/reattach/close/quit/Access denied 残留 | `current` |
| [`runtime/mcp-cli-skill-migration-plan.md`](runtime/mcp-cli-skill-migration-plan.md) | 按通用开发标准规划 MCP/CLI/Skill 分类迁移、管道适配标记和问题工具登记 | `current` |
| [`runtime/mcp-cli-skill-migration-execution-2026-05-03.md`](runtime/mcp-cli-skill-migration-execution-2026-05-03.md) | MCP/CLI/Skill 迁移计划执行记录、台账统计、首批 file-only 迁移和分层验收结果 | `execution-record` |
| [`runtime/trae-ref0-cli-low-context-prompt.md`](runtime/trae-ref0-cli-low-context-prompt.md) | 给 Trae/低上下文 agent 的 ref_0 CLI-only 验证提示词 | `reference` |

## Workflow

这些文档说明正式入口、文件布局、run 落盘和主链流程。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`workflow/formal-entry-and-bypass-audit.md`](workflow/formal-entry-and-bypass-audit.md) | 当前唯一正式入口、旁路冻结范围、旧路径退出生产职责 | `current` |
| [`workflow/file_management_rules.md`](workflow/file_management_rules.md) | task/run 目录、日志、导出物、状态文件如何分层落盘 | `reference` |
| [`workflow/project-layout.md`](workflow/project-layout.md) | 仓库结构、标准任务目录、关键源码位置 | `reference` |

## Reference

这些文档提供背景经验、专题调研和学习路径。它们不能覆盖 `AGENTS.md`、阶段计划或 Skill。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`reference/cst-modeling-notes.md`](reference/cst-modeling-notes.md) | CST 建模、结果读取、导出、session 相关经验 | `reference` |
| [`reference/model-intent-check-solid-research.md`](reference/model-intent-check-solid-research.md) | LEAM 调研、model intent、Check Solid 设计结论 | `reference` |
| [`reference/cst-project-experience-mining.md`](reference/cst-project-experience-mining.md) | 从历史 CST 工程和可能保留的 `run_id`/`1D Results` 中提炼经验库的设想 | `reference` |
| [`reference/cst-mcp-learning-plan.md`](reference/cst-mcp-learning-plan.md) | 项目负责人补齐操作系统、测试、数据建模、CLI 协议和架构能力的学习计划 | `reference` |

## Validations

这些文档是一次性验证或案例记录。它们提供证据，但不自动成为当前流程入口。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`validations/2026-04-23-trae-ref0-cli-low-context-validation.md`](validations/2026-04-23-trae-ref0-cli-low-context-validation.md) | Trae 低上下文 ref_0 CLI-only 验证结果 | `validated-record` |
| [`validations/2026-04-23-ref0-fresh-session-farfield-validation.md`](validations/2026-04-23-ref0-fresh-session-farfield-validation.md) | ref_0 10 GHz fresh-session 远场导出和 Realized Gain dBi 读取验证 | `validated-record` |
| [`validations/2026-04-23-trae-cli-feedback-triage.md`](validations/2026-04-23-trae-cli-feedback-triage.md) | Trae 使用反馈分流、P0/P1/P2 归类 | `triage-record` |
| [`validations/showcase-flatness-optimization.md`](validations/showcase-flatness-optimization.md) | 近轴方向图平坦度优化展示案例 | `case-record` |

## Handoffs

这些文档是日终收尾和次日计划记录。它们只作为历史上下文，不作为当前入口。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`handoffs/2026-04-20-work-handoff.md`](handoffs/2026-04-20-work-handoff.md) | 2026-04-20 工作收尾、知识回收、次日计划 | `archived-record` |
| [`handoffs/2026-04-21-work-handoff.md`](handoffs/2026-04-21-work-handoff.md) | 2026-04-21 工作收尾、残留问题、次日门控 | `archived-record` |

## Historical

这些文档默认不指导当前任务，只在追溯背景时阅读。

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [`archive/cst-cli-atomic-tools-poc.md`](archive/cst-cli-atomic-tools-poc.md) | 早期 CLI 原子工具 POC，当前已被 `cst_runtime` 路线取代 | `historical` |
| [`archive/optimization_plan.md`](archive/optimization_plan.md) | 旧 CST Antenna Optimizer Skill 优化计划 | `historical` |
| [`archive/2026-04-24-cli-first-rearchitecture-ppt.md`](archive/2026-04-24-cli-first-rearchitecture-ppt.md) | CLI-first runtime 底座汇报稿 | `historical` |
| [`archive/p0-completion-checklist-2026-04-23.md`](archive/p0-completion-checklist-2026-04-23.md) | P0 完成长清单归档 | `historical` |
| [`archive/project-goals-and-plan-pre-cleanup-2026-05-02.md`](archive/project-goals-and-plan-pre-cleanup-2026-05-02.md) | 项目目标文档清洗前长版归档 | `historical` |

## 常见问题入口

- 当前任务是否能插队：先看 [`project-goals-and-plan.md`](./project-goals-and-plan.md)，再看 [`current-priority-checklist.md`](./current-priority-checklist.md)。
- 当前项目状态和下一步工程主线：看 [`core/project-current-status.md`](core/project-current-status.md)。
- 文档应该归哪类、是否常维护：看 [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md)。
- 低上下文 agent 如何调用 `cst_runtime`：看 [`runtime/cst-runtime-agent-usage.md`](runtime/cst-runtime-agent-usage.md)。
- CLI 管道和参数如何使用：看 [`runtime/cst-runtime-native-pipeline.md`](runtime/cst-runtime-native-pipeline.md)。
- 要先全量验证 CST 进程/session 管理系统：看 [`runtime/cst-session-process-management-test-plan.md`](runtime/cst-session-process-management-test-plan.md)。
- MCP 工具迁入 CLI/Skill 时如何分类、标记管道适配性、记录问题工具：看 [`runtime/mcp-cli-skill-migration-plan.md`](runtime/mcp-cli-skill-migration-plan.md)。
- MCP/CLI/Skill 迁移计划当前执行到哪一步、哪些验收没有覆盖真实 CST：看 [`runtime/mcp-cli-skill-migration-execution-2026-05-03.md`](runtime/mcp-cli-skill-migration-execution-2026-05-03.md)。
- 正式入口和旁路边界：看 [`workflow/formal-entry-and-bypass-audit.md`](workflow/formal-entry-and-bypass-audit.md)。
- run 目录和导出文件怎么放：看 [`workflow/file_management_rules.md`](workflow/file_management_rules.md)。
- CST session、远场、S11、导出经验：看 [`reference/cst-modeling-notes.md`](reference/cst-modeling-notes.md)。
- 想把历史手工优化后的 `CST` 项目整理成经验库：看 [`reference/cst-project-experience-mining.md`](reference/cst-project-experience-mining.md)。
- 某个文档是不是过时：先看 [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md) 的状态列。

## 维护规则

- `docs/` 新增、删除、拆分或明显改边界后，必须同步更新本文档和 [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md)。
- 索引只做导航；详细状态和维护建议放在 [`core/docs-maintenance-map.md`](core/docs-maintenance-map.md)。
- 标记为 `historical`、`handoff` 或 `validated-record` 的文档，默认不作为当前主线入口。
- 若要做物理目录搬迁，先更新维护地图并盘点链接，再移动文件。
