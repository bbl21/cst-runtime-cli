# docs 维护地图

> 本文档用于给 `docs/` 下的文档分配生命周期、维护责任和整理归属。  
> 本文档不是规则源；规则以 `AGENTS.md` 为准，阶段计划以 `project-goals-and-plan.md` 和 `current-priority-checklist.md` 为准。

## 1. 维护原则

- `docs/` 不是一个平铺日志目录。每篇文档必须有明确用途、状态和维护方式。
- 常维护文档只保留当前有效内容，不长期堆积已完成 checklist 和历史过程。
- 一次性验证、交接和阶段记录可以保留，但应标记为记录类文档，不作为当前主线入口。
- 历史 POC、旧方案和展示材料应标记为归档参考，避免被误读为当前流程。
- 若文档内容变成规则或红线，应升级到 `AGENTS.md`；若变成执行步骤，应进入对应 Skill；若只是 run 细节，应落入 `tasks/.../runs/...`。

## 2. 生命周期分类

| 分类 | 含义 | 维护方式 |
| --- | --- | --- |
| `core` | 当前状态、目标、优先级、索引等高频入口 | 经常更新，保持短而准 |
| `architecture` | 架构决策、主链设计、系统边界 | 阶段变化时更新，稳定后少改 |
| `runtime` | `cst_runtime`、CLI、agent 调用说明 | 工具接口变化时同步更新 |
| `workflow` | run 目录、文件落盘、正式入口、执行链规则说明 | 流程变化时更新 |
| `reference` | 建模经验、项目结构、学习计划、专题调研 | 按需更新，不能覆盖规则源 |
| `validation` | 低上下文验证、fresh-session 验证、反馈分流、展示案例 | 一次性记录，后续只修正明显错误 |
| `handoff` | 日终收尾、次日计划、残留问题 | 一次性记录，不作为当前入口 |
| `historical` | 旧 POC、旧优化计划、汇报稿 | 只作背景参考，默认不指导当前任务 |

## 3. 当前文档台账

| 文档 | 分类 | 状态 | 维护建议 |
| --- | --- | --- | --- |
| `topic-index.md` | `core` | `current` | 总入口，只做导航，不承载长篇背景说明 |
| `core/project-current-status.md` | `core` | `current` | 维护项目当前状态、已验证能力和下一步工程主线 |
| `project-goals-and-plan.md` | `core` | `current` | 建议后续压缩，只保留目标、阶段边界和当前主攻方向 |
| `current-priority-checklist.md` | `core` | `current` | P0 已完成后应逐步压缩，转向下一阶段当前清单 |
| `architecture/cli-architecture-decision.md` | `architecture` | `current` | 保留为 CLI-first 架构决策依据 |
| `architecture/phase-b-main-chain-consolidation.md` | `architecture` | `current` | 阶段 B 主链收口记录，后续少改 |
| `architecture/phase-c-system-integration-and-portable-mode.md` | `architecture` | `current` | 阶段 C 系统集成记录，后续少改 |
| `workflow/formal-entry-and-bypass-audit.md` | `workflow` | `current` | 正式入口和旁路冻结依据 |
| `workflow/file_management_rules.md` | `workflow` | `reference` | 文件和 run 落盘规则说明；若变成强制红线，应同步 `AGENTS.md` |
| `workflow/project-layout.md` | `workflow` | `reference` | 项目结构导航；目录变化时更新 |
| `runtime/cst-runtime-agent-usage.md` | `runtime` | `current` | runtime 使用入口，CLI 接口变化时同步 |
| `runtime/cst-runtime-native-pipeline.md` | `runtime` | `current` | runtime 管道和参数协议，CLI 管道变化时同步 |
| `runtime/mcp-cli-skill-migration-plan.md` | `runtime` | `current` | MCP/CLI/Skill 分类迁移计划；迁移口径、管道适配状态或问题工具登记策略变化时同步 |
| `runtime/trae-ref0-cli-low-context-prompt.md` | `runtime` | `reference` | 给低上下文 agent 的任务提示词模板 |
| `reference/cst-modeling-notes.md` | `reference` | `reference` | CST 建模、结果读取、session 经验 |
| `reference/model-intent-check-solid-research.md` | `reference` | `reference` | Check Solid 和 model intent 专题调研 |
| `reference/cst-project-experience-mining.md` | `reference` | `reference` | 历史 CST 工程经验提炼设想，后续若启动应先定义项目摘要 schema |
| `reference/cst-mcp-learning-plan.md` | `reference` | `reference` | 项目负责人学习计划 |
| `validations/2026-04-23-trae-ref0-cli-low-context-validation.md` | `validation` | `validated-record` | Trae 低上下文验证记录 |
| `validations/2026-04-23-ref0-fresh-session-farfield-validation.md` | `validation` | `validated-record` | ref_0 远场 fresh-session 验证记录 |
| `validations/2026-04-23-trae-cli-feedback-triage.md` | `validation` | `triage-record` | Trae 使用反馈分流记录 |
| `validations/showcase-flatness-optimization.md` | `validation` | `case-record` | 展示案例，不能替代正式 run 记录 |
| `handoffs/2026-04-20-work-handoff.md` | `handoff` | `archived-record` | 一次性交接记录 |
| `handoffs/2026-04-21-work-handoff.md` | `handoff` | `archived-record` | 一次性交接记录 |
| `archive/cst-cli-atomic-tools-poc.md` | `historical` | `historical` | 旧 CLI POC 背景，默认不作为当前入口 |
| `archive/optimization_plan.md` | `historical` | `historical` | 旧优化计划，默认不指导当前任务 |
| `archive/2026-04-24-cli-first-rearchitecture-ppt.md` | `historical` | `historical` | 汇报稿，不作为工程入口 |
| `archive/p0-completion-checklist-2026-04-23.md` | `historical` | `historical` | P0 完成长清单归档，当前优先级以根目录清单为准 |
| `archive/project-goals-and-plan-pre-cleanup-2026-05-02.md` | `historical` | `historical` | 项目目标文档清洗前长版归档，当前目标以根目录文档为准 |

## 4. 需要后续处理的混合文档

### `project-goals-and-plan.md`

问题：同时包含项目定位、阶段目标、执行计划、完成状态和历史说明。

建议：

- 保留项目定位、阶段目标、当前主攻方向和验收标准。
- 已完成的 P0 细节移入状态文档、验证记录或阶段记录。
- 后续只维护当前阶段，不继续堆积完整历史过程。

### `current-priority-checklist.md`

问题：P0 已完成，但文件仍保存大量已完成 checklist。

建议：

- 将 P0 完成细节压缩为一句状态和链接。
- 新增下一阶段当前清单时，只保留未完成项、当前阻塞项和明确不做项。
- 已完成的历史 checklist 归档到阶段记录，不再作为高频入口内容。

### `topic-index.md`

问题：索引容易变成所有文档的长摘要。

建议：

- 只按分类列入口。
- 每个分类保留 1-2 句使用说明。
- 详细状态放到本文档维护，不在索引重复。

## 5. 后续可选的物理目录整理

当前已经完成物理目录初步整理。若后续继续细分，可以保持以下结构：

```text
docs/
  topic-index.md
  project-goals-and-plan.md
  current-priority-checklist.md
  core/
  architecture/
  runtime/
  workflow/
  reference/
  validations/
  handoffs/
  archive/
```

根目录保留 `topic-index.md`、`project-goals-and-plan.md`、`current-priority-checklist.md`，因为它们被 `AGENTS.md` 和 `README.md` 作为稳定入口引用。继续移动前必须先做链接盘点，并在移动后修正所有相对链接。
