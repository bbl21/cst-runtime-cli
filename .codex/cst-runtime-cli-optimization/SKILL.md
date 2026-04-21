---
name: cst-runtime-cli-optimization
description: 当用户明确要求使用 CLI/runtime 执行 CST 参数优化、验证低上下文 CLI 流程、或在保留 MCP 主链的同时试运行 `cst_runtime` 优化闭环时，调用此 Skill。它适用于 `python -m cst_runtime` 的 run 创建、参数读写、仿真、results 读取、S11 JSON/HTML 产物和审计落盘；不用于几何建模、远场导出或替代尚未退场的 MCP 稳定链。
---

# CST Runtime CLI 优化 Skill

## 定位

本 Skill 是与现有 MCP 优化 Skill 并行的新流程。

- MCP 工具链仍是当前稳定生产链，尤其是远场导出、GUI 可见验收和历史兼容流程。
- CLI/runtime 链用于低上下文、脚本化、agent-friendly 的优化闭环验证和逐步迁移。
- 两条链共享同一正式任务结构：`tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}`。
- CLI 完成全量生产能力前，不宣称 MCP 退场。

## 触发条件

使用本 Skill 的情况：

- 用户明确说“走 CLI”、“runtime CLI”、“低上下文 CLI 验证”。
- 任务目标是 S 参数/参数扫描/仿真闭环，且不涉及远场导出。
- 需要验证 `cst_runtime` 是否能独立完成优化流程。
- 需要生成可审计的 CLI 调用链，落到 run 的 `logs/` 和 `stages/`。

不要使用本 Skill 的情况：

- 远场导出、Realized Gain 网格读取、方向图专项任务：继续走现有 results-MCP 正式链。
- 几何建模、材料、边界、网格、结构创建：当前不迁入 CLI runtime。
- 用户要求 GUI 可见 MCP tool call 或正式 MCP 回归验收。

## CLI 调用原则

- 入口固定为：`uv run python -m cst_runtime ...`
- 简单发现命令可直接调用：`list-tools`、`describe-tool`。
- 所有带路径或复杂参数的命令必须使用 `--args-file`。
- 不手写复杂 `--args-json`，尤其不要在 PowerShell 中内联 Windows 路径 JSON。
- args 文件放在当前 task 或 run 附近，便于复查。
- 每次调用必须检查 JSON 返回的 `status`；不得只看退出码。

PowerShell args-file 模板：

```powershell
$argsPath = "C:\path\to\args.json"
@{
  project_path = "C:\path\to\tasks\task_xxx\runs\run_001\projects\working.cst"
  run_id = 1
  module_type = "3d"
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $argsPath -Encoding UTF8

uv run python -m cst_runtime get-parameter-combination --args-file $argsPath
```

## 工具清单

发现工具：

```powershell
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime describe-tool --tool get-1d-result
```

已实测的优化闭环工具：

- run：`prepare-run`、`get-run-context`
- 审计：`record-stage`、`update-status`
- 身份/锁：`verify-project-identity`、`wait-project-unlocked`
- modeler：`open-project`、`list-parameters`、`change-parameter`、`start-simulation-async`、`is-simulation-running`、`save-project`、`close-project`
- results：`open-results-project`、`list-run-ids`、`get-parameter-combination`、`get-1d-result`、`generate-s11-comparison`

## 最小优化闭环

### 1. 创建 run

输入 task 目录应包含 `task.json`，其中至少有 `source_project`。

```powershell
$task = "C:\path\to\tasks\task_xxx"
@{ task_path = $task } |
  ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\prepare_args.json" -Encoding UTF8

uv run python -m cst_runtime prepare-run --args-file "$task\prepare_args.json"
```

成功后读取上下文：

```powershell
uv run python -m cst_runtime get-run-context --args-file "$task\prepare_args.json"
```

后续所有路径使用返回的 `working_project`、`exports_dir`、`logs_dir`。

### 2. 打开并确认工程身份

```powershell
@{ project_path = $workingProject } |
  ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\project_args.json" -Encoding UTF8

uv run python -m cst_runtime open-project --args-file "$task\project_args.json"
uv run python -m cst_runtime verify-project-identity --args-file "$task\project_args.json"
uv run python -m cst_runtime list-parameters --args-file "$task\project_args.json"
```

若返回 `ambiguous_open_projects`，必须先关闭无关 CST 工程；禁止继续写参数。

### 3. 修改参数

```powershell
@{
  project_path = $workingProject
  name = "R"
  value = 0.102
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\change_parameter_args.json" -Encoding UTF8

uv run python -m cst_runtime change-parameter --args-file "$task\change_parameter_args.json"
uv run python -m cst_runtime list-parameters --args-file "$task\project_args.json"
```

必须读回确认参数生效后再启动仿真。

### 4. 异步仿真与轮询

```powershell
uv run python -m cst_runtime start-simulation-async --args-file "$task\project_args.json"
```

轮询示例：

```powershell
for ($i = 1; $i -le 80; $i++) {
  $raw = uv run python -m cst_runtime is-simulation-running --args-file "$task\project_args.json"
  $json = ($raw -join "`n") | ConvertFrom-Json
  if ($json.status -ne "success") { throw ($raw -join "`n") }
  if ($json.running -eq $false) { break }
  Start-Sleep -Seconds 15
}
```

不要默认用同步 `start-simulation`；同步调用更容易超时。

### 5. 保存、关闭、解锁

```powershell
uv run python -m cst_runtime save-project --args-file "$task\project_args.json"

@{
  project_path = $workingProject
  save = $false
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\close_project_args.json" -Encoding UTF8

uv run python -m cst_runtime close-project --args-file "$task\close_project_args.json"

@{
  project_path = $workingProject
  timeout_seconds = 30
  poll_interval_seconds = 0.5
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\wait_unlock_args.json" -Encoding UTF8

uv run python -m cst_runtime wait-project-unlocked --args-file "$task\wait_unlock_args.json"
```

若 `save-project` 失败但仿真已完成，不要反复保存；关闭后用 results `list-run-ids` 判断结果是否已落盘。

### 6. 刷新 results 并读取最新结果

```powershell
@{
  project_path = $workingProject
  treepath = "1D Results\S-Parameters\S1,1"
  module_type = "3d"
  max_mesh_passes_only = $false
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\list_run_ids_args.json" -Encoding UTF8

uv run python -m cst_runtime list-run-ids --args-file "$task\list_run_ids_args.json"
```

选择最新可用 `run_id` 后导出：

```powershell
@{
  project_path = $workingProject
  treepath = "1D Results\S-Parameters\S1,1"
  module_type = "3d"
  run_id = $runId
  export_path = "$exportsDir\s11_run$runId.json"
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\get_1d_result_args.json" -Encoding UTF8

uv run python -m cst_runtime get-1d-result --args-file "$task\get_1d_result_args.json"
```

读取参数组合：

```powershell
@{
  project_path = $workingProject
  run_id = $runId
  module_type = "3d"
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\get_parameter_combination_args.json" -Encoding UTF8

uv run python -m cst_runtime get-parameter-combination --args-file "$task\get_parameter_combination_args.json"
```

### 7. 生成 S11 对比

```powershell
@{
  file_paths = @("$exportsDir\s11_run0.json", "$exportsDir\s11_run1.json")
  output_html = "$exportsDir\s11_comparison.html"
  page_title = "S11 Comparison"
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\s11_comparison_args.json" -Encoding UTF8

uv run python -m cst_runtime generate-s11-comparison --args-file "$task\s11_comparison_args.json"
```

### 8. 阶段记录与状态更新

每轮至少记录参数、run_id、指标文件、HTML 输出、异常和耗时。

```powershell
@{
  task_path = $task
  run_id = "run_001"
  stage = "cli_runtime_iteration"
  status = "completed"
  message = "CLI runtime iteration completed"
  details_json = '{"parameter_changes":{"R":0.102},"result_run_ids":[0,1]}'
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\record_stage_args.json" -Encoding UTF8

uv run python -m cst_runtime record-stage --args-file "$task\record_stage_args.json"
```

```powershell
@{
  task_path = $task
  run_id = "run_001"
  status = "validated"
  stage = "cli_runtime_iteration"
  output_files_json = '{"s11_json":"exports/s11_run1.json","s11_comparison_html":"exports/s11_comparison.html"}'
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\update_status_args.json" -Encoding UTF8

uv run python -m cst_runtime update-status --args-file "$task\update_status_args.json"
```

## 错误处理

- `invalid_json_args`：不要修 CLI，改用 `--args-file`。
- `ambiguous_open_projects`：关闭无关 CST 工程后重试。
- `project_not_open`：先 `open-project`。
- `lock_not_released`：确认项目已关闭，等待或清理当前任务相关 CST 窗口。
- `no_cst_session`：如果只是 results 读取，通常不阻塞；如果要 modeler 写操作，需要先 `open-project`。
- `Access is denied` 杀不掉 CST 后台进程：若无打开工程且无 `.lok`，记录 PID/进程名/原因，标为非阻塞残留；禁止声称已杀掉。

## 退场门控

MCP 退出必须满足：

- CLI/runtime 覆盖当前生产优化闭环。
- 远场导出与真实 gain/dBi 读取有等价 runtime 链或明确替代。
- 低上下文验证能只凭文档和 Skill 完成。
- MCP 与 CLI 产物均能落到同一标准 run 结构，且审计可追溯。

未满足前，MCP 保留为稳定生产链，CLI 保留为并行迁移链。
