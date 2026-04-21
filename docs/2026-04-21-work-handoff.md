# 2026-04-21 工作收尾

> 本文用于今天的知识回收、计划变更和明日交接。  
> 规则仍以 `AGENTS.md` 为准，当前阶段目标以 `docs/project-goals-and-plan.md` 和 `docs/current-priority-checklist.md` 为准。

## 今日结论

- CLI/runtime 方向继续成立，但不能被表述为第二条生产链；`cst_runtime/` 是共享能力层，`python -m cst_runtime` 是面向 agent 的 CLI 调用面，MCP 先保留为稳定生产链和兼容 adapter。
- 本地跨 agent 基础兼容性已经补强：`doctor`、`usage-guide`、结构化 JSON 错误、显式参数优先于 stdin、`--args-stdin` 显式读管道、`python -m cst_runtime` fallback。
- 原生管道协议已形成：默认不因非 TTY stdin 而阻塞；显式 `--args-json` / `--args-file` 优先，只有 `--args-stdin` 或无显式参数时才考虑 stdin。
- results/S11 和 farfield 相关能力已迁入 runtime 代码层，但 fresh-session 真实 CST 远场导出/读取仍是 `needs_validation`。
- 旧 `tools/` 旁路脚本已归档到 `archive/tools-legacy-20260421/`，默认调用入口不再落在 `tools/cst_cli.py`。
- 今日门控结论：不进入 `P1` 优化指导功能原型；P0 还缺第三方 agent 低上下文端到端验证。

## 已完成

- 完成 CLI 错误出口改造：错误用法、缺参、非法 JSON 现在应返回 JSON，而不是只输出 argparse 文本。
- 完成 stdin/显式参数读取规则修正：解决 Trae 类环境中非 TTY stdin 可能导致阻塞的问题。
- 增加 `doctor` 和 `usage-guide`，降低其他 coding agent 不知道如何调用 CLI 的风险。
- 以原生管道为目标补齐参数合并规则，支持把上游 JSON 结果显式接入下游工具。
- 迁移 results 和 farfield 相关 runtime 能力，保留真实 CST fresh-session 验证门槛。
- 清理 `tools/`：历史调试脚本归档，当前工具目录只保留支持脚本和 MCP client/helper 类能力。
- 同步更新 Skill、runtime 使用说明、原生管道说明、topic index、计划清单和仓库 MEMORY。

## 工作审视

### 原定目标

- 跑最小优化 demo，记录卡点。
- 尝试用原生管道串联部分操作。
- 以原生管道为目标重构 CLI，并加入其他 MCP 工具能力。
- 迁移远场相关功能，检查工具目录并清理不必要工具。
- 解决其他 agent 不会用、误用无返回、Trae stdin 阻塞等兼容性问题。

### 完成情况

- [x] 已完成：CLI/runtime 的基础兼容性、管道规则、错误 JSON、使用说明、工具清理和文档同步。
- [x] 已完成：results/S11 和 farfield runtime 代码迁移与现有导出文件解析/预览验证。
- [ ] 未完成：第三方 coding agent 环境中的完整低上下文端到端验证。
- [ ] 未完成：fresh-session 真实 CST 远场导出/读取生产验证。

### 发现的问题

| 严重程度 | 问题描述 | 根本原因 | 改进动作 |
| --- | --- | --- | --- |
| 必须修正 | `_load_json_args` 在非 TTY stdin 环境下可能无条件读 stdin，导致 Trae 等环境阻塞 | CLI 输入来源优先级没有显式建模 | 已改为显式参数优先，`--args-stdin` 才强制读 stdin |
| 必须修正 | 其他 agent 误用 CLI 时不容易知道正确调用方式，错误也不稳定返回 JSON | 缺少面向 agent 的使用契约和自检入口 | 已增加 `doctor`、`usage-guide` 和 JSON usage error |
| 应当修正 | 远场 runtime 迁移已有代码和离线解析验证，但 fresh-session CST 实测未完成 | 今天重点转向 CLI 兼容性和工具清理，真实 CST 导出验证未闭环 | 明天先补 fresh-session 远场实测，再考虑扩大迁移范围 |
| 应当修正 | 旧工具在 `tools/` 中容易被其他 agent 误当生产入口 | 历史脚本和当前入口混放 | 已归档到 `archive/tools-legacy-20260421/`，并更新索引 |

## 残留问题

### 阻塞项

- Trae/其他 coding agent 低上下文端到端验证未完成，P0 不能标记为 `validated`。
- fresh-session 真实 CST 远场导出/读取未验证，farfield runtime 不能宣称生产完成。

### 非阻塞项

- 当前收尾检查发现 CST 残留进程：
  - PID 7148：`CSTDCMainController_AMD64`
  - PID 7156：`CSTDCSolverServer_AMD64`
- 已尝试 `Stop-Process -Force`，两者均返回 `Access is denied`。本次没有声称进程已清理。

### 观察项

- 仓库中仍存在历史 `.lok` 文件，分布在 `backup/`、旧 `tasks/` 和 `ref/` 目录；本次是文档/CLI 收尾任务，没有删除这些文件。
- 迁移到其他机器时，`uv run python -m cst_runtime ...` 可能先因本机 CST 绝对路径配置失败；目标机应先用配置好的 Python 环境跑 `python -m cst_runtime doctor`。
- `tools/` 清理后，如果旧说明或外部 agent 仍引用 `tools/cst_cli.py`，应改指向 `python -m cst_runtime` 或归档路径。

## 明天第一任务

1. 在 Trae/其他 coding agent 环境，用最小上下文执行 `python -m cst_runtime doctor` 和 `python -m cst_runtime usage-guide`。
2. 用 `describe-tool` / `args-template` / `--args-file` 跑一次低上下文完整流程，并确认错误分支仍返回 JSON。
3. 补做 fresh-session 真实 CST 远场导出/读取验证，确认导出路径、字段语义、单位和 `close(save=False)`。

## 明天禁止事项

- 不进入 `P1` 优化指导功能原型。
- 不把 farfield runtime 代码迁移完成说成生产验证完成。
- 不把旧 `tools/cst_cli.py` 当作当前入口继续扩展。
- 不迁移几何建模、材料、边界、网格等建模类工具。
- 不删除历史 `.lok` 或旧 run 文件，除非先明确它们属于当前清理范围并有备份/验证依据。
