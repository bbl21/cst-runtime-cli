# 当前优先清单

> 本清单只维护当前应优先推进的工程事项。  
> 已完成的 P0 长清单已归档到 [`archive/p0-completion-checklist-2026-04-23.md`](./archive/p0-completion-checklist-2026-04-23.md)。

## 1. 当前状态

- P0 基础目标已完成并标记为 `validated`。
- 低上下文 CLI-only 验证已完成，记录见 [`validations/2026-04-23-trae-ref0-cli-low-context-validation.md`](./validations/2026-04-23-trae-ref0-cli-low-context-validation.md)。
- ref_0 10 GHz fresh-session 远场 Realized Gain dBi 验证已完成，记录见 [`validations/2026-04-23-ref0-fresh-session-farfield-validation.md`](./validations/2026-04-23-ref0-fresh-session-farfield-validation.md)。
- 当前项目状态摘要见 [`core/project-current-status.md`](./core/project-current-status.md)。

## 2. 当前唯一主线

当前默认只集中推进一件事：

**把 ref_2 多频 realized-gain flatness 优化整理成一个正式、可复现、约束清晰的工程优化闭环。**

这件事的第一步不是继续跑仿真，而是先固定任务定义：

- 优化对象：`ref_2` port1。
- 频点：`4 / 8 / 13 / 18 GHz`。
- 主指标：`theta <= 15 deg` 范围内 realized-gain flatness。
- 约束：S11 阈值、boresight realized gain 下降阈值、仿真预算。
- 证据链：每轮必须读取当前 run 的 S11 JSON 与 Realized Gain dBi 网格。
- 落盘：每轮均创建新的 `run_xxx`，不得覆盖已有 run。

## 3. 当前待办

- [ ] 写清 ref_2 正式优化任务的目标、输入、指标、约束、停止条件和验收标准。
- [ ] 明确 baseline 采用 `tasks/task_008_ref2_multifreq_realgain_optimization/runs/run_001`，并核对其 S11 与 Realized Gain 证据链。
- [ ] 明确候选对比是否使用 `run_009`，以及其低频 boresight gain 下滑是否可接受。
- [ ] 明确角度采样策略：链路验证可用 5 deg；正式指标需要按任务精度重新定义角分辨率或角窗。
- [ ] 确认不引用 `Abs(E)` 作为 dBi 增益证据。
- [ ] 任务边界确认后，再创建新的正式 run 继续优化。

## 4. 当前明确不做

- 不重启旧 `prototype_optimizer` 作为主线。
- 不把临时脚本或旧 `tools/` 路径重新提升为生产入口。
- 不把 CLI 当成第二条生产链；`cst_runtime/` 仍是共享能力层。
- 不在任务指标和约束未固定前继续扩大参数扫描。
- 不用 `Abs(E)` 场强代理量冒充 dBi 增益。
- 不在本清单里堆积已完成历史过程；完成项应进入状态文档、验证记录或 run 记录。

## 5. 维护规则

- 若当前主线改变，必须同步更新本文档和 [`core/project-current-status.md`](./core/project-current-status.md)。
- 若新增事项属于规则或红线，应进入 `AGENTS.md`，不写在本文档。
- 若新增事项属于执行流程，应进入对应 Skill，本文档只保留优先级和边界。
- 若某个待办完成并形成长期事实，应分流到状态文档、验证记录或 run 产物，而不是长期留在 checklist 中。
