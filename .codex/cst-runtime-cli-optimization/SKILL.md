---
name: cst-runtime-cli-optimization
description: 当用户明确要求使用 CLI/runtime 执行 CST 参数优化、验证低上下文 CLI 流程、或在保留 MCP 主链的同时试运行 `cst_runtime` 优化/结果/远场闭环时，调用此 Skill。它适用于 `python -m cst_runtime` 的 run 创建、参数读写、仿真、results 读取、S11 JSON/HTML、fresh-session farfield ASCII/HTML/Realized Gain 导出读取和审计落盘；不用于几何建模或替代尚未退场的 MCP 稳定链。
---

# CST Runtime CLI 优化 Skill

## 定位

本 Skill 是与现有 MCP 优化 Skill 并行的新流程。

- MCP 工具链仍是当前稳定生产链，尤其是 GUI 可见验收和历史兼容流程。
- CLI/runtime 链用于低上下文、脚本化、agent-friendly 的优化闭环验证和逐步迁移；远场 fresh-session 导出/读取已在 `ref_0` 10 GHz 正式 run 上通过实机验收，但 MCP 仍保留为稳定生产链和兼容 adapter。
- 两条链共享同一正式任务结构：`tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}`。
- CLI 完成全量生产能力前，不宣称 MCP 退场。

## 触发条件

使用本 Skill 的情况：

- 用户明确说“走 CLI”、“runtime CLI”、“低上下文 CLI 验证”。
- 任务目标是 S 参数/参数扫描/仿真闭环，或明确要求验证 runtime 远场导出、Realized Gain 网格读取、farfield ASCII/HTML 预览。
- 需要验证 `cst_runtime` 是否能独立完成优化流程。
- 需要生成可审计的 CLI 调用链，落到 run 的 `logs/` 和 `stages/`。

不要使用本 Skill 的情况：

- 用户要求 GUI 可见 MCP tool call、正式 MCP 回归验收，或当前任务涉及尚未验证的新模型/新指标且必须以生产远场结果作为最终交付证据。
- 几何建模、材料、边界、网格、结构创建：当前不迁入 CLI runtime。

## CLI 调用原则

- 入口固定为：`uv run python -m cst_runtime ...`
- 简单发现命令可直接调用：`doctor`、`usage-guide`、`list-tools`、`list-pipelines`、`describe-tool`、`describe-pipeline`、`args-template`、`pipeline-template`。
- 其他 agent 第一次使用时必须先跑 `doctor` 和 `usage-guide`；不要靠猜工具名或参数名。
- 低上下文 agent 不应自己发明管道；先跑 `list-pipelines`，再对目标链路跑 `describe-pipeline --pipeline <name>`。
- 跨机器迁移时，`uv run` 可能因 CST 绝对路径依赖先于 CLI 启动失败；此时在已配置 CST Python 库的环境里用 `python -m cst_runtime doctor` 定位问题。
- 带路径或复杂参数的命令优先使用 `args-template` 生成 JSON，再用 `--args-file` 调用；这是低上下文 agent 的首选方法，不是备选方法。
- 不手写复杂 `--args-json`，尤其不要在 PowerShell 中内联 Windows 路径 JSON。
- 优先用 `args-template` 生成 args 文件骨架，再修改其中的路径和参数值。
- 只有已经通过 `describe-tool` 确认支持直接参数时，才使用 `--project-path`、`--name`、`--value` 等 CLI flags；直接参数只服务常用字段，不能替代 args 文件。
- 所有 `project_path`、`source_project`、`working_project` 都必须指向具体 `.cst` 文件，例如 `...\projects\working.cst` 或 `...\ref_0.cst`；不要只传工程目录。
- `change-parameter` 的参数名固定为 `name` 和 `value`；不要写成 `parameter_name` / `parameter_value`。
- args 文件放在当前 task 或 run 附近，便于复查。
- 默认有 `--args-file` / `--args-json` 时不读取 stdin；如需合并 stdin JSON，必须显式加 `--args-stdin`。合并时 stdin 先进入，显式参数后进入并覆盖同名字段。
- 每次调用必须检查 JSON 返回的 `status`；不得只看退出码。
- CLI 使用错误也必须解析 stdout JSON。缺命令、缺 `--tool`、未知命令返回 `error_type="cli_usage_error"`；JSON 入参错误返回 `error_type="invalid_json_args"`；缺少业务参数返回 `error_type="missing_required_arg"` 并带 `runbook`。

推荐调用模板：

```powershell
uv run python -m cst_runtime describe-tool --tool change-parameter
uv run python -m cst_runtime args-template --tool change-parameter --output "$run\stages\change_parameter_args.json"
# 编辑 JSON：project_path 必须是 working.cst；参数字段必须是 name/value。
uv run python -m cst_runtime change-parameter --args-file "$run\stages\change_parameter_args.json"
```

已知且简单的常用字段也可直接传：

```powershell
uv run python -m cst_runtime change-parameter --project-path "$run\projects\working.cst" --name g --value 24
uv run python -m cst_runtime wait-simulation --project-path "$run\projects\working.cst" --timeout-seconds 3600 --poll-interval-seconds 10
```

S11 JSON 结构固定为外层元数据加数据数组：`xdata` 是频率序列；`ydata` 是复数序列，元素通常是 `{"real": <float>, "imag": <float>}`。计算 dB 时必须先取 `sqrt(real^2 + imag^2)`，再做 `20*log10(...)`；不要把 `ydata` 当成单层 dB 数组。

## 低上下文 agent 契约

当把任务交给 Trae 或其他 agent 时，提示词可以很短，但必须包含以下契约。agent 不需要项目记忆；如未读 `AGENTS.md`，也必须只按本 Skill 的流程和 CLI 返回执行。

```text
你在 Windows 项目目录 C:\Users\z1376\Documents\CST_MCP。
只依靠本 Skill 和 `uv run python -m cst_runtime ...` CLI 完成任务。
不要调用 MCP tool，不要使用 archive/ 里的旧脚本，不要写一次性 Python 脚本绕过 CLI，不要修改 ref/ 下参考工程。

先运行：
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline self-learn-cli

每个不熟悉的工具先运行 `describe-tool` 和 `args-template`。
每条不熟悉的管道先运行 `describe-pipeline` 和 `pipeline-template`。
复杂参数一律先用 `args-template` 生成 args JSON 文件，编辑后用 `--args-file` 调用。
路径必须写到具体 `.cst` 文件，不能只写工程目录；改参数字段必须是 `name` 和 `value`。
每次调用后解析 stdout JSON；只有 `status=="success"` 才继续。
失败时停止当前链路，用 `record-stage` / `update-status` 写明 blocked 或 needs_validation。
```

任务命名和 `task.json` 也必须在提示词里给清楚。示例：

```text
任务目录：tasks/task_009_ref0_cli_low_context_validation
task_id：task_009_ref0_cli_low_context_validation
参考模型只读路径：C:\Users\z1376\Documents\CST_MCP\ref\ref_model\ref_0\ref_0.cst
目标：只验证 ref_0 的 S11 CLI 闭环，可做一次最小参数扰动，不追求最优。
参数：优先确认 `g` 与 `thr`；若存在，可把 `g` 从 25 改为 24.5，`thr` 不变；若参数不存在，标记 blocked，不猜其它参数。
验收：run 为 validated，S11 JSON/HTML/status.json/tool_calls.jsonl 均落盘，工程关闭且无 .lok。
```

最终回复必须报告：task 目录、run_id、working_project、关键输出文件、`status.json` 状态、是否只用了 Skill + CLI、CST cleanup 是否有 `Access is denied` 残留。残留进程只能写“未被清理，非阻塞残留”，不能写“已杀掉”。

## 管道自学习与常用链

本节解决低上下文 agent “知道有哪些工具，但不知道如何串起来”的问题。固定学习顺序：

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline self-learn-cli
uv run python -m cst_runtime describe-tool --tool get-1d-result
uv run python -m cst_runtime args-template --tool get-1d-result --output "$run\stages\get_1d_result_args.json"
```

如果任务要走某条链路，先把 pipeline plan 落盘到当前 run 或 task 附近：

```powershell
uv run python -m cst_runtime pipeline-template --pipeline latest-s11-preview --output "$run\stages\latest_s11_pipeline_plan.json"
```

常用管道链：

### 1. `self-learn-cli`

用途：新 agent 入场自学，不启动 CST。

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline latest-s11-preview
```

### 2. `args-file-tool-call`

用途：复杂参数先生成 args 文件，再调用工具，避免 PowerShell 内联 JSON。

```powershell
uv run python -m cst_runtime describe-tool --tool change-parameter
uv run python -m cst_runtime args-template --tool change-parameter --output "$run\stages\change_parameter_args.json"
uv run python -m cst_runtime change-parameter --args-file "$run\stages\change_parameter_args.json"
```

### 3. `project-unlock-check`

用途：从 `working.cst` 推断 run，并检查 `.lok`。

```powershell
@{ project_path = "$run\projects\working.cst" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime infer-run-dir |
  uv run python -m cst_runtime wait-project-unlocked
```

如果仍有锁，先关闭当前任务相关 CST 项目；如需清理进程，只能用 `cleanup-cst-processes`，且记录白名单进程、PID、锁文件扫描和 `Access is denied` 残留。

### 4. `latest-s11-preview`

用途：读取最新 S11，导出 JSON，并生成 HTML 预览。

```powershell
@{
  project_path = "$run\projects\working.cst"
  treepath = "1D Results\S-Parameters\S1,1"
  module_type = "3d"
  max_mesh_passes_only = $false
} |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime list-run-ids |
  uv run python -m cst_runtime get-1d-result |
  uv run python -m cst_runtime plot-exported-file
```

`get-1d-result` 收到 `run_ids` 且没有显式 `run_id` 时，默认取最大 run id。若没有看到新增 run id，先刷新 results，不要硬读旧结果。

### 5. `async-simulation-refresh-results`

用途：启动异步仿真、内置等待、关闭 modeler 后刷新 results，再读取最新 S11。低上下文 agent 不需要手写轮询循环。

```powershell
uv run python -m cst_runtime start-simulation-async --project-path "$run\projects\working.cst"
uv run python -m cst_runtime wait-simulation --project-path "$run\projects\working.cst" --timeout-seconds 3600 --poll-interval-seconds 10
uv run python -m cst_runtime close-project --project-path "$run\projects\working.cst" --save false
uv run python -m cst_runtime list-run-ids --project-path "$run\projects\working.cst" --treepath "1D Results\S-Parameters\S1,1" --module-type 3d --allow-interactive true --max-mesh-passes-only false
uv run python -m cst_runtime args-template --tool get-1d-result --output "$run\stages\get_1d_result_args.json"
uv run python -m cst_runtime get-1d-result --args-file "$run\stages\get_1d_result_args.json"
```

关键规则：结果读取前必须先确认 `wait-simulation` 返回 `running=false`；随后 `close-project --save false` 释放 modeler 工程；results 侧重新打开后以 `list-run-ids` 返回的最新 `run_id` 为准。若最新 `run_id` 不出现，标记 `needs_validation`，不要读取旧缓存。

### 6. `s11-json-comparison`

用途：用 `get-1d-result` 产出的 JSON 生成 S11 对比页；CSV 禁止进入生产链。

```powershell
uv run python -m cst_runtime generate-s11-comparison --args-file "$run\stages\s11_comparison_args.json"
```

多文件对比优先在 args 文件里写 `file_paths`；只有明确要合并上游 JSON 时才使用 `--args-stdin`。

### 7. `farfield-realized-gain-preview`

用途：远场末端流程，导出真实 `Realized Gain` / `Gain` / `Directivity`，检查网格并生成预览。

```powershell
uv run python -m cst_runtime export-farfield-fresh-session --args-file "$run\stages\export_farfield_args.json"
uv run python -m cst_runtime inspect-farfield-ascii --args-file "$run\stages\inspect_farfield_args.json"
uv run python -m cst_runtime plot-farfield-multi --args-file "$run\stages\plot_farfield_args.json"
uv run python -m cst_runtime read-realized-gain-grid-fresh-session --args-file "$run\stages\read_gain_grid_args.json"
```

远场链路必须检查 `unit="dBi"`、`Realized Gain/Gain/Directivity`、输出文件存在、`row_count` 与角度计数；`Abs(E)` 不能写成 dBi 增益。

管道停止规则：

- 每一步都解析 stdout JSON，`status!="success"` 立即停止，除非下一步是明确恢复动作。
- 管道配方是 agent 可读计划，不是隐藏执行器；写操作、仿真、results 读取和远场导出仍要逐步审计。
- 有 `--args-file` / `--args-json` 时默认不读 stdin；需要合并上游 JSON 才加 `--args-stdin`。
- 任何会触发 CST session、保存、关闭、导出、清理进程的链路，都必须遵守 `AGENTS.md` 的 Level 1 红线。

推荐模板生成方式：

```powershell
uv run python -m cst_runtime args-template --tool change-parameter --output "$task\change_parameter_args.json"
uv run python -m cst_runtime change-parameter --args-file "$task\change_parameter_args.json"
```

原生管道示例：

```powershell
@{ project_path = "$run\projects\working.cst" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime infer-run-dir |
  uv run python -m cst_runtime wait-project-unlocked
```

管道合并 args-file 示例：

```powershell
@{ export_path = "$exportsDir\s11_run1.json" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime generate-s11-comparison --args-stdin --args-file "$run\stages\s11_page_args.json"
```

备选 PowerShell args-file 写法：

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
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime describe-tool --tool get-1d-result
uv run python -m cst_runtime args-template --tool get-1d-result
```

已实测的优化闭环工具：

- run：`prepare-run`、`get-run-context`
- 审计：`record-stage`、`update-status`
- 进程清理：`cleanup-cst-processes`
- 身份/锁：`verify-project-identity`、`wait-project-unlocked`
- modeler：`open-project`、`list-parameters`、`change-parameter`、`start-simulation-async`、`is-simulation-running`、`wait-simulation`、`save-project`、`close-project`
- results：`open-results-project`、`list-run-ids`、`get-parameter-combination`、`get-1d-result`、`generate-s11-comparison`
- farfield：`export-farfield-fresh-session`、`export-existing-farfield-cut-fresh-session`、`read-realized-gain-grid-fresh-session`、`inspect-farfield-ascii`、`plot-farfield-multi`、`calculate-farfield-neighborhood-flatness`

## 自包含远场导出/读取流程

本节是给低上下文 agent 使用的完整流程。不要假设 agent 读过 `AGENTS.md`、项目记忆或聊天记录；只按本节和 CLI JSON 返回执行。

### 适用条件

- 用户要求验证或导出 CST farfield，并允许走 `cst_runtime` CLI。
- 参考工程必须是只读蓝本；所有操作必须先创建 `tasks/task_xxx_slug/runs/run_xxx/` 工作副本。
- 远场增益证据只允许使用 `Realized Gain`、`Gain` 或 `Directivity`。`Abs(E)` 只能作为场强，不能写成 dBi 增益。
- 远场导出/读取属于结果流程末端；导出后关闭工程时使用 `save=false`，不要在读取结果后保存工程。

### 命名与目录

任务命名：

```text
tasks/task_NNN_<source>_fresh_session_farfield_validation
```

示例：

```text
tasks/task_010_ref0_fresh_session_farfield_validation
```

`task.json` 至少包含：

```json
{
  "task_id": "task_010_ref0_fresh_session_farfield_validation",
  "title": "Validate ref_0 10 GHz farfield through cst_runtime fresh session",
  "goal": "Run a fresh-session CST farfield export/read validation using cst_runtime.",
  "source_project": "C:/Users/z1376/Documents/CST_MCP/ref/ref_model/ref_0/ref_0.cst",
  "status": "active",
  "target_metric": "Realized Gain dBi farfield grid"
}
```

必须使用 `prepare-run` 创建 run；不要手工复制 `.cst` 后直接工作。成功后只使用返回的：

- `working_project`
- `exports_dir`
- `analysis_dir`
- `stages_dir`
- `logs_dir`

### 0. 固定开场自检

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime describe-tool --tool export-farfield-fresh-session
uv run python -m cst_runtime describe-tool --tool read-realized-gain-grid-fresh-session
uv run python -m cst_runtime describe-tool --tool inspect-farfield-ascii
uv run python -m cst_runtime describe-tool --tool plot-farfield-multi
```

若任何命令返回 `status="error"`，先处理错误，不继续导出。

### 1. 创建 run

```powershell
$task = "C:\Users\z1376\Documents\CST_MCP\tasks\task_010_ref0_fresh_session_farfield_validation"
$prepareArgs = "$task\prepare_run_args.json"
@{ task_path = $task } | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath $prepareArgs -Encoding UTF8

uv run python -m cst_runtime prepare-run --args-file $prepareArgs
uv run python -m cst_runtime get-run-context --args-file $prepareArgs
```

从 `get-run-context` 的 JSON 里取：

```powershell
$run = "...\runs\run_001"
$workingProject = "$run\projects\working.cst"
$exports = "$run\exports"
$analysis = "$run\analysis"
$stages = "$run\stages"
```

### 2. 确认远场名称

优先用文件事实和结果树共同确认。先看 `working\Result` 是否存在类似文件：

```text
farfield (f=10)_1.ffm
farfield (f=10)_1.fme
```

对应 `farfield_name` 通常是：

```text
farfield (f=10) [1]
```

也可以尝试列结果树：

```powershell
$listArgs = "$stages\list_result_items_all_args.json"
@{
  project_path = $workingProject
  module_type = "3d"
  filter_type = "all"
  allow_interactive = $true
  subproject_treepath = ""
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $listArgs -Encoding UTF8

uv run python -m cst_runtime list-result-items --args-file $listArgs
```

注意：`list-result-items` 不一定列出 `Farfields` 节点。若结果目录中已有 `.ffm` / `.fme`，可直接使用推导出的 `farfield_name`。

### 3. Fresh-session 导出 Realized Gain TXT

这是实机验证过的导出路径：fresh GUI session + `FarfieldCalculator` -> `Abs(Realized Gain)[dBi]` TXT。

```powershell
$exportArgs = "$stages\export_farfield_fresh_session_args.json"
@{
  project_path = $workingProject
  farfield_name = "farfield (f=10) [1]"
  output_file = "$exports\farfield_10ghz_port1_realized_gain_fullsphere_5deg.txt"
  plot_mode = "Realized Gain"
  prime_with_cut = $false
  theta_step_deg = 5.0
  phi_step_deg = 5.0
  theta_min_deg = 0.0
  theta_max_deg = 180.0
  phi_min_deg = 0.0
  phi_max_deg = 360.0
  max_attempts = 1
  keep_prime_cut_file = $false
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $exportArgs -Encoding UTF8

uv run python -m cst_runtime export-farfield-fresh-session --args-file $exportArgs
```

成功必须同时满足：

- JSON `status` 是 `success`
- `unit` 是 `dBi`
- `plot_mode` / `exported_quantity` 指向 `Realized Gain`
- `scope` 是预期范围，full sphere 时 `is_full_sphere=true`
- `output_file` 存在且非空
- TXT 表头包含 `Abs(Realized Gain)[dBi]`

如果直接导出失败，且错误像是 full node 不能导出，可把 `prime_with_cut=true` 后重试；重试必须保留 flow log，且最后仍要确认 full 输出不是 cut。

### 4. Fresh-session 读取 Realized Gain JSON

导出 TXT 后，还要另走读取链路，证明真实 gain/dBi 可被 `FarfieldCalculator` 读取，而不是只依赖 TXT 文件。

```powershell
$readArgs = "$stages\read_realized_gain_grid_fresh_session_args.json"
@{
  project_path = $workingProject
  farfield_name = "farfield (f=10) [1]"
  run_id = ""
  theta_step_deg = 5.0
  phi_step_deg = 5.0
  theta_min_deg = 0.0
  theta_max_deg = 180.0
  phi_min_deg = 0.0
  phi_max_deg = 360.0
  selection_tree_path = "1D Results\S-Parameters"
  output_json = "$analysis\realized_gain_grid_10ghz_port1_fullsphere_5deg.json"
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $readArgs -Encoding UTF8

uv run python -m cst_runtime read-realized-gain-grid-fresh-session --args-file $readArgs
```

成功必须同时满足：

- JSON `status` 是 `success`
- `source` 是 `FarfieldCalculator`
- `quantity` 是 `Realized Gain`
- `unit` 是 `dBi`
- `sample_count == theta_count * phi_count`
- `output_json` 存在且可解析

### 5. 检查 TXT 并生成预览

```powershell
$inspectArgs = "$stages\inspect_farfield_ascii_args.json"
@{ file_path = "$exports\farfield_10ghz_port1_realized_gain_fullsphere_5deg.txt" } |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $inspectArgs -Encoding UTF8

uv run python -m cst_runtime inspect-farfield-ascii --args-file $inspectArgs
```

```powershell
$plotArgs = "$stages\plot_farfield_multi_args.json"
@{
  file_paths = @("$exports\farfield_10ghz_port1_realized_gain_fullsphere_5deg.txt")
  output_html = "$exports\farfield_10ghz_port1_realized_gain_fullsphere_5deg.html"
  page_title = "10 GHz Port 1 Realized Gain Full Sphere"
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $plotArgs -Encoding UTF8

uv run python -m cst_runtime plot-farfield-multi --args-file $plotArgs
```

### 6. 解锁与清理

```powershell
$unlockArgs = "$stages\wait_project_unlocked_args.json"
@{
  project_path = $workingProject
  timeout_seconds = 30
  poll_interval_seconds = 0.5
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $unlockArgs -Encoding UTF8

uv run python -m cst_runtime wait-project-unlocked --args-file $unlockArgs
```

```powershell
$cleanupArgs = "$stages\cleanup_cst_processes_args.json"
@{
  project_path = $workingProject
  dry_run = $false
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $cleanupArgs -Encoding UTF8

uv run python -m cst_runtime cleanup-cst-processes --args-file $cleanupArgs
```

`cleanup-cst-processes` 只允许处理白名单进程：

```text
cstd
CST DESIGN ENVIRONMENT_AMD64
CSTDCMainController_AMD64
CSTDCSolverServer_AMD64
```

若返回 `cleanup_status="nonblocking_access_denied_residual"`，必须在状态和总结里记录 PID、进程名、`Access is denied`、`lock_files_after=[]`。禁止写“已杀掉这些进程”。

### 7. 更新 run 状态

```powershell
$statusArgs = "$stages\update_status_validated_args.json"
@{
  task_path = $task
  run_id = "run_001"
  status = "validated"
  stage = "fresh_session_farfield_validation_final"
  best_result_json = @{
    frequency_ghz = 10.0
    farfield_name = "farfield (f=10) [1]"
    quantity = "Realized Gain"
    unit = "dBi"
    scope = "full_sphere"
    theta_step_deg = 5.0
    phi_step_deg = 5.0
    theta_count = 37
    phi_count = 72
    sample_count = 2664
    peak_realized_gain_dbi = 14.144726099856493
    peak_theta_deg = 0.0
    peak_phi_deg = 0.0
    boresight_realized_gain_dbi = 14.144726099856493
  }
  output_files_json = @{
    farfield_ascii = "exports/farfield_10ghz_port1_realized_gain_fullsphere_5deg.txt"
    farfield_preview_html = "exports/farfield_10ghz_port1_realized_gain_fullsphere_5deg.html"
    realized_gain_grid_json = "analysis/realized_gain_grid_10ghz_port1_fullsphere_5deg.json"
    cleanup_stage_json = "stages/cleanup_cst_processes_output.json"
  }
  mark_completed = $true
} | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $statusArgs -Encoding UTF8

uv run python -m cst_runtime update-status --args-file $statusArgs
```

示例数值来自 `ref_0` 10 GHz 验证。其他模型或频率必须使用本次命令返回的实际数值，不得照抄。

### 最终验收清单

- [ ] `status.json` 是 `validated`，且 `stage` 是 farfield 验证阶段。
- [ ] `exports/` 有 farfield TXT 和 HTML。
- [ ] `analysis/` 有 Realized Gain grid JSON。
- [ ] TXT 表头是 `Abs(Realized Gain)[dBi]`、`Abs(Gain)[dBi]` 或 `Abs(Directivity)[dBi]`；不是 `Abs(E)[V/m]`。
- [ ] `sample_count == theta_count * phi_count`。
- [ ] `wait-project-unlocked` 返回 `locked=false`。
- [ ] `cleanup-cst-processes` 的结果已记录；Access denied 残留没有被写成已杀掉。
- [ ] `logs/tool_calls.jsonl` 和 `stages/cli_*.json` 能追溯每一步。

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

收尾时只允许通过白名单清理 CST 进程：

```powershell
@{
  project_path = $workingProject
  dry_run = $false
} | ConvertTo-Json -Depth 8 |
  Set-Content -LiteralPath "$task\cleanup_cst_args.json" -Encoding UTF8

uv run python -m cst_runtime cleanup-cst-processes --args-file "$task\cleanup_cst_args.json"
```

强杀白名单固定为：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`。若这些进程返回 `Access is denied`，且工程已 `close(save=False)`、当前 run 无 `.lok`，只能记录为 `nonblocking_access_denied_residual`，禁止声称已杀掉。

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
- `Access is denied` 杀不掉 CST 后台进程：先确认进程名在强杀白名单内，再用 `cleanup-cst-processes` 记录 PID/进程名/原因；若无打开工程且无 `.lok`，标为非阻塞残留；禁止声称已杀掉。

## 退场门控

MCP 退出必须满足：

- CLI/runtime 覆盖当前生产优化闭环。
- 远场导出与真实 gain/dBi 读取有等价 runtime 链或明确替代。
- 低上下文验证能只凭文档和 Skill 完成。
- MCP 与 CLI 产物均能落到同一标准 run 结构，且审计可追溯。

当前状态：`ref_0` 10 GHz 已完成 fresh-session `Realized Gain` dBi 导出和读取验证，记录见 `docs/2026-04-23-ref0-fresh-session-farfield-validation.md`。对新模型、新指标或用户明确要求 GUI 可见 MCP tool call 的任务，仍需按任务边界重新选择验证入口。

未满足前，MCP 保留为稳定生产链，CLI 保留为并行迁移链。
