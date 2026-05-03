# 正式入口与旁路盘点

> 本文档是当前阶段 A 的交付物，用于冻结“唯一正式交互入口”与本周旁路清理范围。  
> 它不是规则源；规则与红线仍以 `AGENTS.md` 为准，执行流程仍以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 一句话结论

当前唯一正式交互入口不是 `prototype_optimizer` 的 Streamlit UI，也不是 `tools/` 或 `tmp/` 下的临时脚本。  
当前唯一正式交互入口定义为：

**以 `tasks/task_xxx_slug/` 任务目录为输入上下文，由主 agent 或自动化编排器按 `AGENTS.md -> docs/project-goals-and-plan.md -> docs/current-priority-checklist.md -> skills/cst-simulation-optimization/SKILL.md` 的顺序读取约束，并从 `cst-modeler.prepare_new_run(task_path=...)` 启动正式主链；后续执行必须走正式 MCP tools / skills 链路。**

其中：
- `tasks/task_xxx_slug/` 是正式任务入口。
- `cst-modeler.prepare_new_run(task_path=...)` 是正式执行起点。
- GUI 可见 MCP tool call 是交互式调试和开发验收的优先展示方式；自动化生产允许内部调用 MCP，但必须把关键调用、状态和结果写入 run 目录，保证可审计。

## 盘点结论

| 类别 | 当前路径/入口 | 判定 | 说明 |
| --- | --- | --- | --- |
| 正式任务入口 | `tasks/task_xxx_slug/task.json` + 对应 `runs/` | 正式入口 | 与项目标准 run 目录一致，是当前正式任务上下文的唯一落点。 |
| 正式执行起点 | `mcp/advanced_mcp.py` 中的 `prepare_new_run` | 正式入口 | 已实现标准 `run_xxx/{projects,exports,logs,stages,analysis}` 初始化和工程副本复制。 |
| 正式执行主链 | `skills/cst-simulation-optimization/SKILL.md` + 正式 MCP tools | 正式入口 | 当前生产过程要求由 Skill 约束流程，并通过 MCP 工具完成执行、读取、导出与收尾；交互式调试和验收优先展示可见 tool call，自动化生产允许内部调用但必须审计落盘。 |
| Modeler/Results 服务启动 | `tools/start_advanced_mcp_http.ps1`、`tools/start_cst_results_http.ps1` | 支撑脚本 | 这是基础设施启动脚本，不是生产任务入口。 |
| 命令行 MCP client | `tools/call_mcp_tool.py` | 验收/排障辅助 | 可用于 `tools/list` 与 `tools/call` 验收或排障，但不是默认生产入口。 |
| 本地直调模块 | `tools/call_local_mcp_tool.py` | 调试辅助 | 规则已明确仅限开发期定位问题，不能作为生产或最终验收入口。 |
| Streamlit UI | `prototype_optimizer/app.py` + `startup_prototype_optimizer.ps1` | 原型外围入口 | 当前只适合做人类交互、历史展示、报告外围能力，不是正式生产入口。 |
| UI 后端编排 | `prototype_optimizer/core/orchestrator.py` | 原型/占位实现 | 当前是占位实现，不执行正式仿真闭环；默认输出路径仍是 `prototype_optimizer/data/runs`，不符合当前主线。 |
| 一次性端到端脚本 | `archive/tools-legacy-20260421/e2e_clean.py`、`archive/tools-legacy-20260421/e2e_final.py` | 已归档旧旁路 | 会绕开正式任务目录与正式 MCP 展示链路，已退出 `tools/`。 |
| 调试/探查脚本 | `archive/tools-legacy-20260421/diag_refresh.py`、`archive/tools-legacy-20260421/explore_results.py`、`archive/tools-legacy-20260421/plot_farfield.py` | 已归档调试辅助 | 不再承担默认生产职责；需要复用逻辑时迁入结构化 runtime/MCP tool。 |
| 历史对比脚本 | `archive/tools-legacy-20260421/generate_s11_comparison.py` | 已归档历史兼容 | 规则已要求生产链改走 `cst-results.generate_s11_comparison(...)` 或 runtime `generate-s11-comparison`。 |
| 临时目录 | `tmp/` 下脚本、日志、参数文件、测试产物 | 非生产路径 | 只允许临时测试与排障，不允许继续承担默认生产职责。 |

## 为什么 `prototype_optimizer` 不是当前正式入口

当前不把 `prototype_optimizer/app.py` 定义为正式入口，理由有三条：

1. `prototype_optimizer/core/orchestrator.py` 仍是占位实现，只写入模拟 run 与模拟指标，不负责真实 MCP 仿真闭环。
2. `prototype_optimizer/config/default_config.json` 的默认输出路径仍是 `prototype_optimizer/data/runs`，与当前项目要求的 `tasks/task_xxx_slug/runs/run_xxx/` 不一致。
3. 既有规划早已将 `prototype_optimizer` 定位为 UI、历史管理、报告外围层，而不是正式仿真执行层。

因此，本周范围内不把它推进成第二条并行主链；它只保留为外围原型，待后续按主链边界接入。

## 正式入口定义

### 最小输入

- 一个标准任务目录：`tasks/task_xxx_slug/`
- `task.json` 中至少可解析出 `source_project`
- 当前任务的目标说明：
  - 优先从 `task.json` 读取
  - 不足时允许由本轮对话显式补充
- 仓库级约束文档：
  - `AGENTS.md`
  - `docs/project-goals-and-plan.md`
  - `docs/current-priority-checklist.md`
  - `skills/cst-simulation-optimization/SKILL.md`

### 最小输出

- 一个新建的 `tasks/task_xxx_slug/runs/run_xxx/`
- 初始化产物：
  - `config.json`
  - `status.json`
  - `summary.md`
  - `projects/working.cst` 与同名目录
- 执行后产物：
  - `exports/` 中的导出文件与预览
  - `logs/` 中的流程日志与报错记录
  - `stages/` 中的阶段状态
  - `analysis/` 中的分析结果

### 最小上下文要求

- 允许依赖的上下文只有：任务目录、仓库知识入口、当前用户明确给出的附加约束
- 不允许把以下内容当作正式入口前提：
  - 某个特定 coding agent 的隐式记忆
  - `prototype_optimizer/data/runs`
  - `tmp/` 中的一次性参数文件或测试脚本
  - 直接 Python 函数调用的本地调试链

### 正式入口负责的阶段

正式入口当前负责以下阶段：

1. 解析任务上下文并创建标准 run 工作区
2. 复制蓝本并生成工作副本
3. 通过 MCP tool 执行建模修改、仿真、results 刷新、结果读取、导出和展示
4. 把状态、摘要、日志和分析结果落到标准 run 目录
5. 按规则完成关闭、退出和收尾

### 不应再由外部脚本或人工兜底的内容

以下内容不应继续由外部脚本、`tmp/` 文件或手工补洞承担默认职责：

- run 目录初始化
- 工程副本复制
- 正式结果导出路径决定
- 主链上的默认 S11 对比页生成
- 正式状态文件写入
- 把调试脚本当成默认执行入口

## 本周旁路冻结清单

### 必须退出生产职责

- `prototype_optimizer/app.py`
- `startup_prototype_optimizer.ps1`
- `prototype_optimizer/core/orchestrator.py`
- `archive/tools-legacy-20260421/e2e_clean.py`
- `archive/tools-legacy-20260421/e2e_final.py`
- `archive/tools-legacy-20260421/diag_refresh.py`
- `archive/tools-legacy-20260421/explore_results.py`
- `archive/tools-legacy-20260421/generate_s11_comparison.py`
- `archive/tools-legacy-20260421/plot_farfield.py`
- `tools/call_local_mcp_tool.py`
- `tmp/` 下所有脚本、参数文件和一次性测试产物

### 保留为辅助，但不得冒充正式入口

- `tools/start_advanced_mcp_http.ps1`
- `tools/start_cst_results_http.ps1`
- `tools/stop_advanced_mcp_http.ps1`
- `tools/stop_cst_results_http.ps1`
- `tools/cleanup_cst.ps1`
- `tools/kill_cst.ps1`
- `tools/close_cst_by_name.ps1`
- `tools/call_mcp_tool.py`

### 本周不做的事

- 不把 `prototype_optimizer` 直接升级成新的正式生产入口
- 不为了“统一入口”再造一层新的临时包装脚本
- 不新增第二条“先跑起来再说”的并行主链

## 阶段判断

今天完成的是“范围冻结与入口定义”，不是“主链收口”。  
这意味着：

- 阶段 A 已具备进入阶段 B 的文档基础
- 阶段 B 仍需把 run 创建、执行、导出、对比、状态落盘真正统一到这条正式主链
- 当前项目整体状态仍然不是 `P0 completed`
