# CLI 化架构研判与阶段门控

> 本文档是当前 CLI 化方向的架构决策记录，不是规则源。规则与红线仍以 `AGENTS.md` 为准，正式执行流程仍以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 一句话结论

当前工作的主线应调整为：

**先把项目剪枝成轻量 CLI-first 架构，再继续做低上下文迁移验证。**

CLI 不应成为第二条生产链，也不应替代 `tasks/task_xxx_slug/` 这个正式任务入口。正确方向是：

**正式任务入口不变，核心能力下沉为可复用 runtime 层，CLI 成为主要人机/agent 调用界面，MCP 暂时保留为兼容 adapter，成熟后逐步弃用。**

## 剪枝结论

### `prototype_optimizer`

结论：

**不应继续作为主线保留。**

当前检查到：

- `prototype_optimizer/core/orchestrator.py` 仍是占位执行器，只写模拟 run 和模拟指标。
- `prototype_optimizer/app.py` 和 `ui/pages/` 主要服务 Streamlit UI、SQLite 历史记录和结果展示。
- `prototype_optimizer/data/` 占该目录绝大多数体积，包含旧工作区、旧参考工程和历史数据。
- 主项目依赖声明没有把 Streamlit、Pandas、Plotly 作为正式核心依赖，说明 UI 栈已经不是轻量主线的一部分。

处理策略：

1. `prototype_optimizer` 不再进入 portable bundle 默认内容。
2. `prototype_optimizer/data/` 应优先归档或删除，不再作为项目事实来源。
3. UI 源码若暂时保留，只能放在 `legacy/` 或 `archive/` 语义下，作为“可参考的旧展示原型”。
4. 后续如果需要 UI，应新建一个轻量 dashboard，直接读取 `tasks/task_xxx_slug/runs/run_xxx/`，不得继续依赖 `prototype_optimizer/data/optimizer.db`。

### `prototype_optimizer` 外围旧功能处置

| 组件 | 当前作用 | 处置 | 原因 |
| --- | --- | --- | --- |
| `prototype_optimizer/app.py` | Streamlit 原型首页，启动模拟任务并展示旧 SQLite 记录 | 冻结，不再维护；后续迁到 `legacy/prototype_optimizer/` 或删除 | 它不是正式入口，且依赖旧 DB 和占位 orchestrator |
| `prototype_optimizer/ui/` | 历史 run 页面、结果对比页面、报告页面 | 可短期保留作展示逻辑参考；不得接入新主线 | 图表布局可能有参考价值，但数据源应改为标准 `tasks/runs` |
| `prototype_optimizer/storage/` | SQLite repository 层 | 归档候选，不再扩展 | 新主线状态落盘以 `status.json`、`stages/`、`logs/` 为准 |
| `prototype_optimizer/data/optimizer.db` | 旧 UI 数据库 | 归档或删除；不得作为事实来源 | 与标准 run 结构并行，继续使用会形成第二套状态系统 |
| `prototype_optimizer/data/workspaces/`、`prototype_optimizer/data/ref/` | 旧工程副本、旧参考工程和结果数据 | 优先归档到 `archive/` 或外部备份；轻量主线不携带 | 体积大、含历史工程数据，且不符合当前蓝本只读和 task/run 结构 |
| `prototype_optimizer/core/orchestrator.py` | 占位执行器 | 删除或保留为 legacy 示例；不得继续命名为生产 orchestrator | 只写模拟指标，不执行真实 CST 主链 |
| `prototype_optimizer/core/sampler.py`、`scorer.py`、`evaluator.py` | 旧采样/评分/评估代码 | 逐个审查；有价值逻辑迁入未来 `cst_runtime/metrics.py` 或优化策略模块 | 只迁移纯算法，不迁移旧目录结构和 DB 假设 |
| `prototype_optimizer/adapters/` | 旧 MCP/result/farfield 适配器 | 归档候选；不得作为新 CLI/runtime 的依赖 | 新 adapter 应直接围绕 `cst_runtime/` 重建 |
| `prototype_optimizer/reports/` | 旧报告生成 | 参考；不接入主线 | 后续报告应读取标准 run 产物 |
| `startup_prototype_optimizer.ps1` | 启动旧 Streamlit UI | 废弃候选；从默认 README/迁移包移除 | 会暗示旧 UI 仍是入口 |

推荐执行顺序：

1. 先把 `prototype_optimizer/data/` 从默认工作树或迁移包中移走，避免继续被误用。
2. 在 `docs/project-layout.md` 中把 `prototype_optimizer/` 标成 legacy/归档候选。
3. 后续若需要保留旧 UI 源码，整体移动到 `legacy/prototype_optimizer/`，并在入口处加说明：只读参考，不是生产入口。
4. 若要重建 UI，只做一个新轻量 viewer，输入是 `tasks/task_xxx_slug/runs/run_xxx/`，不再使用 SQLite。
5. 等 CLI/runtime 跑通后，再决定是否删除 legacy UI 源码。

### MCP

结论：

**CLI 当前不能立即完全替代 MCP，但可以作为最终主方向。**

2026-04-21 更新：
**当前采用并行策略：保留 MCP 工具链作为稳定生产链，同时新增 CLI/runtime Skill 流程。只有当 CLI 覆盖当前生产优化闭环、远场/真实 gain 读取边界清楚、低上下文验证通过后，才推动 MCP 退场。**

不能立即替代的原因：

- 当前 CLI POC 只验证了 run 创建、单工程打开、参数读取/修改和关闭。
- results 读取、远场导出、fresh-session、S11 对比、状态落盘的完整生产链还没有 CLI parity。
- 多 CST 工程并发、按路径 attach project、锁文件等待、results/modeler session 分离还没有稳定 CLI 安全层。
- 现有 MCP 工具里已经沉淀了不少可用生产能力，直接丢弃会破坏当前已验证流程。

但 MCP 不应继续作为新能力的首要开发目标。接下来应：

1. 冻结 MCP 为兼容层和回归验证层。
2. 新能力优先进入 `cst_runtime/`。
3. CLI adapter 优先暴露新 runtime 能力。
4. MCP adapter 只薄包装 runtime，直到 CLI 覆盖生产路径后再退场。
5. 在退场前，MCP Skill 与 CLI Skill 并行维护，避免把尚未完成的 CLI 链路误宣称为唯一生产入口。

### runtime 层

结论：

**必须做 runtime 层；不能维持 CLI 从 `mcp/*.py` 源文件加载工具的状态。**

当前 `tools/cst_cli.py` 直接加载 `mcp/advanced_mcp.py` 只是 POC 手段。它的问题是：

- CLI 依赖 MCP 文件结构，职责倒置。
- 业务规则继续沉在 MCP adapter 里，CLI 只能复用而不能独立演进。
- 后续若要弃用 MCP，会发现 CLI 的关键实现仍挂在 MCP 文件上。

正确结构是：

```text
tasks/task_xxx_slug/
        |
        v
Skill / agent 判断层
        |
        v
cst_runtime/ 共享运行层
        |
        +-- CLI adapter: cst_runtime/cli.py
        |
        +-- MCP adapter: 后续另建薄包装；原 `mcp/*.py` 暂不修改
```

### 后续开发主线

结论：

**可以把后续开发完全围绕 CLI-first runtime 来推进。**

这里的“CLI”不是一堆不可审计的脚本，而是：

- 每个命令都有 `list-tools` / `describe-tool` / `invoke` 或等价发现机制。
- 输入是 JSON 或明确参数。
- stdout 只输出机器可解析 JSON。
- 每次生产调用写入当前 run 的 `logs/`、`stages/`、`status.json`。
- 必要展示通过命令摘要、JSON 返回、HTML 预览文件、日志路径和状态文件给出，而不是依赖 GUI MCP tool call。

如果这些展示足够清晰，MCP 的可见 tool call 优势就不再是刚需。

## 矛盾分析

### 矛盾清单

- `[可迁移、低上下文、非 Codex 依赖] vs [当前主链强依赖 MCP HTTP/GUI 会话和熟悉上下文]`
- `[CLI 轻量、可脚本化、易被 agent 调用] vs [直接扩展 CLI 容易形成第二条生产链]`
- `[继续阶段 D 验证] vs [被验证的架构形态尚未定型]`
- `[快速把 POC 扩大] vs [项目身份、session、results 分层还未抽象清楚]`

### 主要矛盾

⭐ 主要矛盾是：

**生产能力还没有从 MCP tool 实现中抽出稳定核心层，而 CLI 化又要求同一能力能被非 MCP 入口可靠调用。**

解决这个矛盾后，阶段 D 的低上下文验证、CLI 扩展、portable bundle、非 Codex 执行器都会随之变清楚；否则继续验证只是在验证一个未定型的外壳。

### 矛盾性质

这是非对抗性的技术架构矛盾。MCP 和 CLI 不是二选一关系；冲突来自职责层次未分清，而不是目标冲突。

### 应对方法

接下来应先做架构定型：

1. 保持 `tasks/task_xxx_slug/` 为唯一正式任务入口。
2. 把 run 管理、项目身份校验、状态落盘、session 操作、results fresh-session 读取等能力从 MCP 适配层中逐步抽到共享 core/runtime 层。
3. 让 MCP tools 和 CLI tools 都调用同一 core/runtime 层。
4. CLI 只按阶段迁入最小必要能力，先做项目身份层，再做 modeler 仿真层，最后做 results/export 层。
5. 阶段 D 低上下文验证改为验证“新架构形态能否被低上下文执行者理解并启动”，而不是只验证当前 MCP-only 迁移包。

### 需监控

需监控的次要矛盾：

- CLI POC 是否因为扩展过快而变成新的旁路生产链。
- MCP tools 是否继续沉积业务逻辑，导致 core/runtime 层抽不出来。
- portable bundle 是否只验证文件齐全，而没有验证正式架构边界。

## 架构边界

### 保持不变

- 正式任务入口仍是 `tasks/task_xxx_slug/`。
- 标准 run 结构仍是 `runs/run_xxx/{projects,exports,logs,stages,analysis}`。
- 生产流程仍受 `AGENTS.md`、`docs/project-goals-and-plan.md`、`docs/current-priority-checklist.md` 和正式 Skill 约束。
- `prototype_optimizer` 仍不是正式生产入口。

### 需要调整

当前 `tools/cst_cli.py` 直接加载 `mcp/advanced_mcp.py` 复用 `prepare_new_run`，这对 POC 可以接受，但不是长期架构。新的 runtime 迁移不继续往 `tools/` 增加入口，也不修改原有 `mcp/*.py` 源文件；先在 `cst_runtime/` 内另起边界。

长期结构应改为：

```text
tasks/task_xxx_slug/
        |
        v
Skill / agent 判断层
        |
        v
core/runtime 共享能力层
        |
        +-- MCP adapter: mcp/*.py
        |
        +-- CLI adapter: cst_runtime/cli.py
```

MCP adapter 负责 MCP 协议、GUI/HTTP 服务和工具注册；CLI adapter 负责 JSON 输入输出、退出码、stdout 纯净和命令行发现机制。两者不应各自实现不同的业务规则。

## CLI 分阶段路线

### 阶段 E0：架构定型

目标：

- 明确 core/runtime 层目录、职责和迁移边界。
- 明确 MCP adapter 与 CLI adapter 的共同输入输出契约。
- 明确哪些现有 MCP 函数先抽到 core/runtime，哪些暂时保持不动。

完成信号：

- 有一份明确的 core/runtime 模块切分方案。
- 至少选定第一批迁移对象：run 管理和项目身份校验。
- 当前 CLI POC 被标记为 adapter POC，而不是生产主链。

## 第一版 core/runtime 切分方案

### 目标目录

第一版不做大规模重构，只新增一个共享运行层：

```text
cst_runtime/
    __init__.py
    __main__.py
    cli.py
    run_workspace.py
    project_identity.py
    audit.py
    modeler.py
    results.py
```

目录职责：

| 模块 | 职责 | 第一批来源 |
| --- | --- | --- |
| `run_workspace.py` | task/run 路径解析、run 编号、工程副本复制、`config.json` / `status.json` / `summary.md` 初始化、run context 读取 | `mcp/advanced_mcp.py` 中的 `prepare_new_run`、`get_run_context` 及其私有 helper |
| `audit.py` | `stages/*.json`、`logs/production_chain.md`、`status.json` 更新 | `record_run_stage`、`update_run_status` 及 CLI POC 的 `_write_audit` 可复用部分 |
| `project_identity.py` | `project_path` 规范化、run_dir 推断、打开工程列表、目标工程唯一性校验、锁文件等待 | `tools/cst_cli.py` 中的 `_normalize_path`、`_infer_run_dir`、`_attach_expected_project` 思路 |
| `cli.py` / `__main__.py` | runtime 自带 CLI adapter，提供 `list-tools`、`describe-tool`、`invoke` 与直接命令入口 | 新建，不放入 `tools/`，避免辅助脚本目录继续膨胀 |
| `modeler.py` | 优化闭环所需的 modeler 运行能力：打开/关闭/保存工程、参数读写、仿真启动与轮询 | 只迁移优化流程运行能力，不迁移几何建模、材料、边界、网格等建模工具 |
| `results.py` | 优化闭环所需的 results 读取能力：打开结果工程、run_id、参数组合、1D JSON 导出、S11 对比 HTML | 直接使用 `cst.results`，不依赖旧 `mcp/cst_results_mcp.py` |

### 第一批迁移对象

只迁移不依赖 CST 活对象、或风险较低且边界清楚的能力：

1. `prepare_new_run(...)`
2. `get_run_context(...)`
3. `record_run_stage(...)`
4. `update_run_status(...)`
5. `project_path -> run_dir` 推断
6. `wait_project_unlocked(project_path, timeout_seconds=...)`

第一批不迁移：

- `open_project`
- `change_parameter`
- `start_simulation`
- results 读取
- 远场导出

原因：这些能力涉及 CST session、保存/关闭、results fresh-session 或导出红线，必须等项目身份层稳定后再迁。

### Adapter 形态

MCP adapter 应变成：

```text
mcp/advanced_mcp.py
    @mcp.tool()
    def prepare_new_run(...):
        return cst_runtime.run_workspace.prepare_new_run(...)
```

CLI adapter 应变成：

```text
cst_runtime/cli.py
    command prepare-run
        -> cst_runtime.run_workspace.prepare_new_run(...)
    command verify-project-identity
        -> cst_runtime.project_identity.verify_project_identity(...)
```

这样做的标准是：

- 业务规则只写在 `cst_runtime/`。
- MCP adapter 只处理 MCP 入参、工具注册和返回。
- CLI adapter 位于 `cst_runtime/cli.py`，只处理 argparse、JSON 输入输出、退出码和 stdout 纯净。
- 两个 adapter 的返回结构应尽量一致，便于 Skill 和 agent 判断。

### 第一版验收

第一版 core/runtime 切分完成后，必须验证：

- `cst-modeler.prepare_new_run(task_path=...)` 仍能通过真实 MCP tools/call 创建标准 run。
- `python -m cst_runtime prepare-run ...` 能调用同一 `cst_runtime` 实现创建等价 run。
- 两条 adapter 路径生成的 `config.json`、`status.json`、`summary.md` 字段一致。
- `record_run_stage` 与 CLI audit 都写入标准 `logs/`、`stages/`。
- `project_identity.py` 在多工程打开时返回拒绝写操作的结构化错误，而不是猜测 active project。

### 第一版落地状态（2026-04-21）

已新增第一版 `cst_runtime/`：

- `run_workspace.py`：已支持 `prepare_new_run(...)` 与 `get_run_context(...)`。
- `audit.py`：已支持 `record_run_stage(...)`、`update_run_status(...)` 与 CLI tool call 审计。
- `project_identity.py`：已支持 `project_path` 规范化、`run_dir` 推断、锁文件等待、打开工程列表与目标工程身份校验入口。
- `cli.py` / `__main__.py`：已支持 `python -m cst_runtime list-tools`、`describe-tool`、`invoke` 与直接工具命令。

当前验证范围已覆盖 run workspace、路径身份辅助、锁文件检查、stage/status/audit 落盘、未知工具错误分支、modeler 参数读写、项目身份校验、solver 状态查询、异步仿真启动与轮询、保存/关闭/解锁、results run_id 读取、参数组合读取、1D S 参数 JSON 导出、S11 HTML 对比生成。尚未迁移几何建模工具和远场导出。原有 `mcp/*.py` 未修改。

### 优化闭环迁移实测（2026-04-21）

临时验证任务：

```text
tmp/runtime_optimization_flow_validation_task/runs/run_001/
```

实测通过：

- `prepare-run` 创建标准 run 并复制 `ref_0` 工作副本。
- `open-project` 打开 `projects/working.cst`，并写入 `logs/tool_calls.jsonl` / `stages/cli_*.json`。
- `list-parameters` 读取 19 个参数，初始 `R=0.1`。
- `change-parameter` 修改 `R=0.102`，再次 `list-parameters` 读回 `R=0.102`。
- `verify-project-identity` 确认目标工程是唯一打开工程。
- `is-simulation-running` 返回 `running=false`。
- `close-project(save=false)` 正常关闭，`wait-project-unlocked` 确认无锁。
- `start-simulation-async` 启动真实仿真，`is-simulation-running` 第 6 次轮询返回 `running=false`，总耗时约 80 秒。
- `save-project`、`close-project(save=false)`、`wait-project-unlocked` 完成保存、关闭和解锁。
- 仿真后 `list-run-ids` 返回 `[0, 1]`，可导出 `exports/s11_runtime_run0_after_sim.json`。
- `open-results-project` / `list-run-ids` / `get-parameter-combination` / `get-1d-result` 可读取工作副本 S 参数结果，并导出 `exports/s11_runtime_run1.json`。
- `generate-s11-comparison` 生成 `exports/s11_runtime_after_sim_comparison.html`，且无 `project_path` 的输出型工具也能通过输出路径反推 run 目录并写审计。
- 非法 JSON 入参返回结构化 `invalid_json_args`，不再污染 stdout 为 traceback。

收尾状态：

- `CST DESIGN ENVIRONMENT_AMD64` 已停止。
- 当前无打开工程，工作副本无 `.lok`。
- `cstd` PID 51040、`CSTDCMainController_AMD64` PID 7148、`CSTDCSolverServer_AMD64` PID 7156 因 `Access is denied` 无法强杀，已按非阻塞残留记录到验证 run。

### 阶段 E1：项目身份层

优先实现：

- `inspect-project`
- `verify-project-identity`
- `wait-project-unlocked`

原因：

项目身份层是 CLI 化的安全底座。没有它，后续 `change-parameter`、仿真、results 读取都会存在误操作风险。

### 阶段 E2：modeler 执行层

在项目身份层通过后，再迁入：

- `open-project`
- `close-project`
- `list-parameters`
- `change-parameter`
- `start-simulation`
- `poll-simulation`

原则：

- 每个写操作必须显式传入 `project_path`。
- 多工程打开时默认拒绝写操作，直到有稳定的按路径 attach 能力。
- 所有调用必须写入当前 run 的 `logs/` 和 `stages/`。

### 阶段 E3：results/export 层

最后再做：

- results fresh-session 打开/关闭
- `list-run-ids`
- `get-1d-result`
- `generate-s11-comparison`
- farfield/export 相关能力

原则：

- results 与 modeler 仍是两个独立 session。
- 远场和 results 导出不得因为 CLI 化而退回旧链路。
- CLI adapter 只能复用正式 results core/runtime，不允许另造导出逻辑。

## 对阶段 D 的影响

阶段 D 不取消，但顺序要调整。

原计划是直接验证 portable bundle 的低上下文迁移能力。现在应改为：

1. 先完成 CLI 化架构门控。
2. 再决定阶段 D 验证对象：
   - 如果 core/runtime + MCP/CLI adapter 边界已经清楚，阶段 D 验证新架构。
   - 如果边界仍不清楚，阶段 D 只能标记 `needs_validation`，不能宣称 P0 `validated`。

## 当前禁止事项

- 不把 CLI POC 宣称为正式生产入口。
- 不把 `tools/cst_cli.py` 扩展成第二套完整生产链。
- 不把新的 runtime CLI 入口继续放进 `tools/`；入口归入 `cst_runtime/cli.py`。
- 不修改原有 `mcp/*.py` 来做第一阶段迁移；后续若需要 MCP adapter，应新建薄包装或在明确验收后再处理。
- 不迁移几何建模、材料、边界、网格等建模工具到当前 runtime 主线。
- 不在远场导出和多任务低上下文验证完成前，把 runtime 宣称为完整生产替代。
- 不迁移远场导出；远场仍保留既有 results-MCP 正式链路，直到单独设计和验收。
- 不为了低上下文验证而跳过 CLI 架构研判。

## 下一步

下一步只做一件事：

**在当前优化闭环基础工具与真实仿真链路已实测通过的基础上，下一步只做低上下文/迁移包验证或远场导出专项设计，不进入几何建模迁移。**
