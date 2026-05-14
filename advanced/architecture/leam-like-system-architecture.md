# 类 LEAM 系统架构设计

> 本文档定义 CST_MCP 当前 P1 主线的架构设计交付物。它不是规则源；规则与红线以 `AGENTS.md` 为准，执行流程以当前维护的 Skill 和 CLI/runtime 文档为准。

## 1. 设计目标

当前主线不是立即实现全自动 3D 建模，而是先完成类 LEAM 系统在 CST_MCP 中的架构设计。

目标是把以下链路定义清楚：

```text
自然语言需求
  -> 结构化 model_intent
  -> Check Solid 准入检查
  -> 建模执行（历史 MCP 已退场）
  -> CLI/Skill 正式优化链
```

这条链路的核心价值是把 LLM 建模输出变成可检查、可审计、可阻断、可修复的中间结构，避免 LLM 直接调用 CST 建模原语造成几何、材料、参数、布尔关系和仿真设置错误被一次性放大。

## 2. 分层职责

| 层次 | 职责 | 当前状态 |
| --- | --- | --- |
| 需求理解层 | 将自然语言需求转为结构化 `model_intent` 和优化约束 | 只做接口设计，不接入生产 |
| Check Solid 准入层 | 对 `model_intent` 做确定性检查、问题归因和修复路由 | 当前关键设计对象 |
| 建模执行层（历史 MCP 已退场） | 执行已通过准入的确定性 CST 建模输入 | 历史 MCP 工具已退场，作为迁移参照 |
| CLI/Skill 优化层 | 正式 task/run、仿真、结果读取、指标计算、审计落盘 | 当前唯一正式生产链 |

### 2.1 主 agent / OpenCode worker 分工

OpenCode 是 Codex 的外部 worker 调用机制，不是类 LEAM 系统主链中的业务层。类 LEAM 主链当前为"需求理解 -> `model_intent` -> Check Solid -> CLI/Skill 优化链"；历史 MCP 已退场，只作为迁移参照。

当前架构设计阶段的默认分工：

| 角色 | 负责 | 不负责 |
| --- | --- | --- |
| Codex 主 agent | 主线判断、架构边界、阶段门、接口取舍、风险判断、最终验收、知识回收 | 不把密集读取和机械整理全部留在主上下文里 |
| OpenCode `codex-scout` | 只读检索、批量文件读取、证据摘要、候选问题表 | 不修改文件，不决定架构方向，不创建规则 |
| OpenCode `codex-doc-worker` | 明确文件范围内的文档草稿、表格初稿、任务卡草稿 | 不改 `AGENTS.md` / `MEMORY.md`，不扩大主线 |
| OpenCode `codex-code-worker` | 后续明确 scope 的小实现和测试 | 不在无任务卡授权时执行 CLI/runtime 生产动作，不改 ref 工程，不创建正式 run |

调用原则：

- 凡是批量读取、长文档摘要、diff 表格、候选接口草稿、重复验证输出整理，优先考虑派给 OpenCode，并通过 `.agent_handoff/opencode/outbox/*.summary.json` 回收。
- 凡是架构取舍、阶段门、规则升级、生产链边界、是否进入实现，由 Codex 主 agent 决定。
- OpenCode 任务必须通过短任务卡调用，任务卡只写目标、允许路径、禁止事项、输出格式和验收标准。
- OpenCode 输出只能作为待验收事实或候选草稿；Codex 必须审 `summary.json`、短报告和关键证据后才能纳入设计。
- 未经任务卡明确授权，OpenCode 不得启动 CST、不执行 CLI/runtime 生产动作、不修改 `mcp/*.py`（历史遗留，不再作为正式入口）、不创建正式 `tasks/.../runs/...` 产物。

具体调用方式、agent 名称、`-Async` 和 outbox 回收规则见 [`../runtime/opencode-worker-division.md`](../runtime/opencode-worker-division.md)。

## 3. 当前阶段交付物

P1 当前只交付架构设计，至少包括：

- `model_intent.json` 的职责边界、核心字段和 schema 草案。
- `check_solid_report.json` 的状态语义、issue 格式、`route_to` 取值和阻断规则。
- Check Solid Phase 1/2/3/4 的阶段门。
- 与正式 `tasks/task_xxx_slug/runs/run_xxx/` 结构的落盘契约。
- 与 CLI/Skill 执行层、runtime 的接口边界（历史 MCP 工具只作为迁移参照）。
- 主 agent 与 OpenCode worker 在架构设计、文档草稿、批量验证和后续小实现中的分工边界。
- 明确哪些错误由程序确定性阻断，哪些进入人工或 LLM 语义评审。

## 4. 阶段门

### Phase 1：确定性 intent 检查设计

只定义纯 Python 检查器的输入、输出、状态和验收。此阶段不调用 CST、不调用 MCP 建模工具、不调用 LLM。

验收信号：

- 能说明 `model_intent` 的最小可用字段。
- 能说明 `pass`、`warning`、`blocked`、`needs_review` 的含义。
- 能说明未定义参数、缺失材料、非法 bbox、错误实体引用、布尔引用缺失如何进入 `issues`。
- 能说明报告如何落到 `stages/`、`logs/`、`analysis/`。

### Phase 2：建模执行层设计

历史 MCP 建模工具已退场。当前只设计如何把 `pass` 或允许的 `warning` 交给 CLI/Skill 执行层。LLM 仍不得直接调用建模原语。

### Phase 3：CST 工程与结果契约设计

定义建模完成后如何检查 project identity、参数 readback、baseline 可运行性、results fresh-session 读取和真实 gain/dBi 证据链。

### Phase 4：LLM 语义评审设计

只有确定性检查稳定后，才设计可选 LLM reviewer。LLM reviewer 的输入必须是 `model_intent.json` 和确定性检查报告，输出仍必须是结构化 issues。

## 5. 当前明确不做

- 不把 LEAM 代码当作可直接替换 CST_MCP 的实现。
- 不恢复 LLM 直接调用 CST 建模工具生成完整模型的路线。
- 不在架构设计完成前实现全自动 3D 建模。
- 不把 Check Solid 做成不可审计的黑盒长流程。
- 不绕过正式 task/run 结构形成新的旁路生产链。
- 不把 `ref_2` 多频 realized-gain flatness 优化闭环作为当前主线。