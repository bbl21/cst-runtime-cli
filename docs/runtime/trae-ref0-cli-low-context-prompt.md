# Trae ref_0 CLI 低上下文验证提示词

> 本文是一段可直接复制给 Trae 的提示词，用于验证“仅靠 Skill 和 `cst_runtime` CLI 工具完成 ref_0 的标准 S11 优化闭环”。  
> 规则仍以 `AGENTS.md` 为准；执行流程以 `skills/cst-runtime-cli-optimization/SKILL.md` 为准。

```text
你现在在 Windows 项目目录：
<repo>

目标：
只依靠仓库内 Skill 和 `uv run python -m cst_runtime ...` CLI 工具，完成一次 ref_0 的低上下文端到端流程验证。不要调用 MCP tool，不要使用 `archive/` 里的旧脚本，不要写一次性 Python 脚本绕过 CLI，不要修改 `ref/` 下参考工程。

必须先读：
1. AGENTS.md
2. docs/current-priority-checklist.md
3. skills/cst-runtime-cli-optimization/SKILL.md

本次任务规范：
- 新任务目录：<repo>\tasks\task_009_ref0_cli_low_context_validation
- task_id：task_009_ref0_cli_low_context_validation
- 任务标题：Validate ref_0 S11 workflow through cst_runtime CLI only
- 参考模型只读路径：<repo>\ref\ref_model\ref_0\ref_0.cst
- 优化目标：验证 ref_0 在 9-11 GHz 范围内的 S11 CLI 闭环；可做一次小参数扰动，不追求最终最优。
- 可调参数规范：优先使用 `g` 和 `thr`；默认参考值 `g=25`、`thr=12.5`；若参数存在，可把 `g` 改为 `24.5` 做一次最小验证，`thr` 保持不变。若参数不存在，停止并把状态记为 `blocked`，不要猜其它参数。

如果任务目录不存在，先创建目录和 `task.json`。`task.json` 内容应包含：
{
  "task_id": "task_009_ref0_cli_low_context_validation",
  "title": "Validate ref_0 S11 workflow through cst_runtime CLI only",
  "goal": "Run one low-context cst_runtime CLI-only validation loop for ref_0 S11 near 10 GHz.",
  "source_project": "<repo>/ref/ref_model/ref_0/ref_0.cst",
  "created_at": "2026-04-23T00:00:00+08:00",
  "owner": "trae",
  "status": "active",
  "frequency_range": "9-11 GHz",
  "target_metric": "S11 near 10 GHz",
  "tunable_parameters": [
    {"name": "g", "default": 25, "min": 20, "max": 30, "step": 0.5},
    {"name": "thr", "default": 12.5, "min": 10, "max": 15, "step": 0.5}
  ]
}

执行规则：
1. 所有生产步骤必须走 `uv run python -m cst_runtime <tool> --args-file <args.json>`。
2. 第一次使用先跑：
   - `uv run python -m cst_runtime doctor`
   - `uv run python -m cst_runtime usage-guide`
   - `uv run python -m cst_runtime list-tools`
3. 每个不熟悉的工具先跑 `describe-tool` 和 `args-template`，复杂参数一律写 args 文件，不在 PowerShell 里手写内联 JSON。
4. 每次调用后解析 stdout JSON，只有 `status == "success"` 才能继续；失败时按 Skill 的错误处理走，不能只看退出码。
5. 不直接复制或修改 `ref/`；必须通过 `prepare-run` 创建 `runs/run_xxx/projects/working.cst` 后，只操作 working copy。
6. 不把 `Abs(E)` 当作 dBi；本任务只做 S11，不做 farfield 生产结论。

建议流程：
1. 用 `prepare-run` 基于上述 task 目录创建新 run。
2. 用 `get-run-context` 读取 `working_project`、`exports_dir`、`logs_dir`、`stages_dir`、`analysis_dir`，后续路径全部使用返回值。
3. `open-project` 打开 `working_project`。
4. `verify-project-identity` 确认当前只附着到这个 working project；如返回 `ambiguous_open_projects`，停止并说明需要关闭无关 CST 工程。
5. `list-parameters` 确认存在 `g` 和 `thr`。
6. `change-parameter` 把 `g` 改为 `24.5`；随后再 `list-parameters` 读回确认。
7. `start-simulation-async` 启动仿真；用 `is-simulation-running` 轮询到结束。不要用同步长阻塞命令。
8. 仿真结束后执行 `close-project`，`save=false`；然后执行 `wait-project-unlocked`。读取结果前不要把 `save-project` 当成默认前置。
9. 用 results 工具读取 S11：
   - `open-results-project`，`allow_interactive=true`
   - `list-run-ids`，treepath 用 `1D Results\S-Parameters\S1,1`，`module_type="3d"`，`max_mesh_passes_only=false`
   - 选择最新 `run_id`
   - `get-parameter-combination`
   - `get-1d-result` 导出到 `exports/s11_run<run_id>.json`
10. 生成 HTML：
   - 优先用当前 run 中可用的两个 S11 JSON 生成 `exports/s11_comparison.html`
   - 如果只有一个 S11 JSON，可先生成单结果预览或记录“只有单文件，无法做真实对比”，不得伪装成优化对比。
11. 收尾清理：
   - 调用 `cleanup-cst-processes`，传入 `project_path=working_project`
   - 强杀白名单只包括：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`
   - 如果返回 `Access is denied`，确认当前 run 无 `.lok` 后只能记录为非阻塞残留；禁止写“已成功杀掉进程”。
12. 用 `record-stage` 记录本次验证摘要：参数变化、最新 run_id、S11 JSON 路径、HTML 路径、cleanup 结果。
13. 用 `update-status` 更新 run：
   - 全流程成功、项目已关闭、无 `.lok`、S11 JSON 和 HTML 存在：`status="validated"`，`stage="cli_ref0_low_context_validation"`
   - 结果未读到、仿真未完成、项目未解锁或路径缺失：`status="blocked"` 或 `needs_validation`，写清原因。

最终回复要求：
- 用中文汇报。
- 列出 task 目录、run_id、working_project、S11 JSON、HTML 输出、status.json 状态。
- 明确说出是否只用了 Skill + `cst_runtime` CLI。
- 如果有 `Access is denied` 残留，列 PID、进程名、原因和是否有 `.lok`；不要声称已清理成功。
- 不要给泛泛建议；只给本次验证事实、阻塞和下一步。
```
