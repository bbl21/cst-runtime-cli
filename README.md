# CST_MCP

CST_MCP 是一套面向 **LLM 主导、人工监督** 的 CST 参数化优化执行系统。项目当前重点不是全自动 3D 建模，而是把已有参数化 CST 工程的优化流程做成可迁移、可审计、低上下文可执行的正式底座。

当前系统已经覆盖任务创建、工程副本管理、参数读写、仿真启动、仿真等待、结果刷新、S11/远场导出、HTML 可视化、状态审计和知识沉淀。

## 当前成果

- **统一生产链路**：标准任务与 run 结构已固定，参考工程只读，所有实验在独立工作副本中执行。
- **MCP + CLI 双层协同**：MCP 保留为稳定生产链与兼容 adapter，`cst_runtime` CLI 作为低上下文、可迁移的 agent 调用界面。
- **低上下文自学习**：agent 可通过 `doctor -> usage-guide -> list-tools -> list-pipelines -> describe-pipeline -> describe-tool -> args-template` 自学习工具和管道。
- **结果能力成型**：已支持 results run_id 读取、1D/S11 JSON 导出、S11 HTML 对比、远场 Realized Gain/Gain/Directivity 导出与预览。
- **管道操作可发现**：`list-pipelines`、`describe-pipeline`、`pipeline-template` 提供常用链路配方，不把流程封成不可审计黑盒。
- **P0 底座已验证**：低上下文 CLI-only 流程与 ref_0 10 GHz fresh-session 远场导出/读取均已完成实机验证。

## 标准 run 结构

```text
tasks/task_xxx_slug/
  task.json
  runs/
    run_001/
      projects/
      exports/
      logs/
      stages/
      analysis/
      status.json
      summary.md
```

关键约束：

- `ref/`、`ref_model/` 等参考工程只读。
- 每次任务必须创建独立 run 和工作工程副本。
- `project_path` 必须指向具体 `.cst` 文件，例如 `...\projects\working.cst`。
- 结果读取、导出和状态变化必须落盘到当前 run。

## 快速入口

项目依赖 `uv`、Python 3.13+、CST Studio Suite 2026。

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
```

查看单个工具：

```powershell
uv run python -m cst_runtime describe-tool --tool change-parameter
uv run python -m cst_runtime args-template --tool change-parameter --output .\tmp\change_parameter_args.json
uv run python -m cst_runtime change-parameter --args-file .\tmp\change_parameter_args.json
```

常用字段也支持直接参数：

```powershell
uv run python -m cst_runtime change-parameter --project-path .\tasks\task_xxx\runs\run_001\projects\working.cst --name g --value 24
uv run python -m cst_runtime wait-simulation --project-path .\tasks\task_xxx\runs\run_001\projects\working.cst --timeout-seconds 3600 --poll-interval-seconds 10
```

## 常用管道

```powershell
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline async-simulation-refresh-results
uv run python -m cst_runtime pipeline-template --pipeline latest-s11-preview --output .\tmp\latest_s11_pipeline_plan.json
```

当前已登记的主要管道：

- `self-learn-cli`：低上下文 agent 入场自学习。
- `args-file-tool-call`：生成 args 文件并调用工具。
- `project-unlock-check`：推断 run 并检查 `.lok`。
- `async-simulation-refresh-results`：异步仿真、等待、关闭 modeler、刷新 results、读取最新 run。
- `latest-s11-preview`：读取最新 S11、导出 JSON、生成 HTML 预览。
- `s11-json-comparison`：用 S11 JSON 生成 HTML 对比页。
- `farfield-realized-gain-preview`：远场真实增益导出、检查和预览。

## 结果读取规则

- 仿真完成后，先关闭 modeler 工程：`close-project --save false`。
- results 侧重新打开/刷新后，以 `list-run-ids` 返回的最新 `run_id` 为准。
- S11 JSON 中 `xdata` 是频率序列，`ydata` 是复数序列，元素通常为 `{"real": ..., "imag": ...}`。
- S11 dB 需要按 `20*log10(sqrt(real^2 + imag^2))` 计算。
- 远场绝对增益只能使用 `Realized Gain` / `Gain` / `Directivity`；`Abs(E)` 不能标记为 dBi。

## 关键文档

- 项目目标与阶段计划：[`docs/project-goals-and-plan.md`](docs/project-goals-and-plan.md)
- 当前优先清单：[`docs/current-priority-checklist.md`](docs/current-priority-checklist.md)
- 文档导航：[`docs/topic-index.md`](docs/topic-index.md)
- CLI agent 使用指南：[`docs/cst-runtime-agent-usage.md`](docs/cst-runtime-agent-usage.md)
- Runtime 原生管道：[`docs/cst-runtime-native-pipeline.md`](docs/cst-runtime-native-pipeline.md)
- CLI 架构决策：[`docs/cli-architecture-decision.md`](docs/cli-architecture-decision.md)
- Runtime Skill：[`skills/cst-runtime-cli-optimization/SKILL.md`](skills/cst-runtime-cli-optimization/SKILL.md)

## 当前边界

当前 P0 底座已验证，但系统仍按阶段推进：

- 不把 CLI 当成第二条生产链；它是 `cst_runtime` 能力层的主要低上下文调用界面。
- MCP 仍保留为稳定生产链和兼容 adapter。
- 不把自然语言直接生成 3D 模型作为当前阶段目标。
- 进入 P1 优化指导原型前，应继续保持底座稳定、可审计、可迁移。

