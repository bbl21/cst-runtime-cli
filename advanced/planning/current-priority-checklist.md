# 当前优先清单

> 本清单只维护当前应优先推进的工程事项。  
> 已完成的 P0 长清单已归档到 [`archive/p0-completion-checklist-2026-04-23.md`](./archive/p0-completion-checklist-2026-04-23.md)。

## 1. 当前状态

- P0 基础目标已完成并标记为 `validated`。
- 低上下文 CLI-only 验证已完成，记录见 [`validations/2026-04-23-trae-ref0-cli-low-context-validation.md`](./validations/2026-04-23-trae-ref0-cli-low-context-validation.md)。
- ref_0 10 GHz fresh-session 远场 Realized Gain dBi 验证已完成，记录见 [`validations/2026-04-23-ref0-fresh-session-farfield-validation.md`](./validations/2026-04-23-ref0-fresh-session-farfield-validation.md)。
- 当前项目状态摘要见 [`core/project-current-status.md`](./core/project-current-status.md)。

## 2. 当前主线

**P1 类 LEAM 系统架构设计**

参考研究：`advanced/reference/model-intent-check-solid-research.md`  
架构设计：`advanced/architecture/leam-like-system-architecture.md`

目标：完成“自然语言需求 -> 结构化 model_intent -> Check Solid 准入 -> CLI/runtime 工具 -> CST_MCP 优化链”的架构设计，明确边界、接口、产物、阶段门和验收标准。

### 当前任务拆解

1. 固定类 LEAM 系统的分层职责。
2. 定义 `model_intent.json` 与 `check_solid_report.json` 的接口边界。
3. 定义 Check Solid Phase 1/2/3/4 的阶段门和禁止越级事项。
4. 定义与正式 `tasks/.../runs/...` 的落盘契约。
5. 定义与 CLI/runtime、现有优化链的接口边界，以及历史 MCP 能力的退场边界。
6. 定义 Codex 主 agent 与 OpenCode worker 的调用分工和回收验收边界。

## 3. 当前待办

- [ ] 完成类 LEAM 系统架构设计文档
- [ ] 固定 `model_intent.json` 最小字段与 schema 草案
- [ ] 固定 `check_solid_report.json` 的状态语义、issue 格式和 `route_to`
- [ ] 固定 Phase 1/2/3/4 阶段门和验收标准
- [ ] 固定 CLI/Skill-only 正式生产入口与历史 MCP 退场边界
- [ ] 固定 OpenCode worker 在只读侦察、文档草稿、重复验证和小实现中的调用边界
- [ ] 更新 topic index 和项目现状，确保主线不再指向 `ref_2` 优化闭环

## 4. 当前明确不做

- 不重启旧 `prototype_optimizer` 作为主线。
- 不把临时脚本或旧 `tools/` 路径重新提升为生产入口。
- 不保留 MCP 作为正式生产链或新功能入口。
- 不把 `ref_2` 多频 realized-gain flatness 优化闭环作为当前主线。
- 不在架构设计完成前实现全自动 3D 建模。
- 不让 LLM 直接调用未经 Skill/runtime 约束的底层建模动作生成完整模型。
- 不让 OpenCode 自行决定架构方向、升级规则或执行未授权 CST/CLI 生产动作。
- 不在 Check Solid Phase 1 设计稳定前推进 Phase 2-4 实现。
- 不用 `Abs(E)` 场强代理量冒充 dBi 增益。
- 不在本清单里堆积已完成历史过程；完成项应进入状态文档、验证记录或 run 记录。

## 5. 维护规则

- 若当前主线改变，必须同步更新本文档和 [`core/project-current-status.md`](./core/project-current-status.md)。
- 若新增事项属于规则或红线，应进入 `AGENTS.md`，不写在本文档。
- 若新增事项属于执行流程，应进入对应 Skill，本文档只保留优先级和边界。
- 若某个待办完成并形成长期事实，应分流到状态文档、验证记录或 run 产物，而不是长期留在 checklist 中。
