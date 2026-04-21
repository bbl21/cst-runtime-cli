# CST Runtime Native Pipeline

本文记录 `cst_runtime` CLI 的原生管道协议。它服务于当前 CLI-first runtime 方向，但不改变正式任务入口：生产任务仍从 `tasks/task_xxx_slug/` 和标准 `runs/run_xxx/` 结构开始。

## 目标

- 让 `python -m cst_runtime <tool>` 可以直接读取上一步 stdout 中的 JSON。
- 默认有 `--args-file` / `--args-json` 时不读取 stdin；如需合并 stdin JSON，必须显式加 `--args-stdin`。
- 保持每个工具的小粒度返回，继续由 agent / Skill 根据 `status`、`error_type`、输出路径和 run 审计记录判断下一步。
- 保持 stdout 的最终结果为 JSON，工具内部偶发 stdout 会被捕获到 `captured_stdout`，减少管道解析污染。

## 输入规则

其他 agent 不应靠猜参数使用 CLI。固定先跑：

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime describe-tool --tool <tool>
uv run python -m cst_runtime args-template --tool <tool> --output <args.json>
```

如果目标环境 `uv run` 因 CST 绝对路径依赖失败，先尝试：

```powershell
python -m cst_runtime doctor
```

每个直接工具命令和 `invoke` 都支持四种输入：

```powershell
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime open-project --args-file .\project_args.json
uv run python -m cst_runtime open-project --args-json '{"project_path":"C:\\path\\to\\working.cst"}'
@{ project_path = "C:\path\to\working.cst" } | ConvertTo-Json | uv run python -m cst_runtime open-project
```

管道输入可以与显式参数合并，但必须加 `--args-stdin`：

```powershell
@{ export_path = "$exportsDir\s11_run1.json" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime generate-s11-comparison --args-stdin --args-file "$run\stages\s11_page_args.json"
```

合并规则是：

```text
final_args = stdin_json + explicit_args
```

同名字段以显式参数为准。若未加 `--args-stdin`，存在 `--args-file` / `--args-json` 时 stdin 会被忽略，避免 Trae 等非 TTY 终端卡住。

## 已验证串联

项目身份和锁检查：

```powershell
@{ project_path = "$run\projects\working.cst" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime infer-run-dir |
  uv run python -m cst_runtime wait-project-unlocked
```

结果读取：

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

`get-1d-result` 若接收到 `run_ids` 且未显式传 `run_id`，默认选择最大的 run id。

远场 TXT 预览：

```powershell
@{
  file_path = "$exportsDir\farfield_13ghz_port1_realized_gain.txt"
  output_html = "$exportsDir\farfield_preview.html"
  page_title = "Farfield Preview"
} |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime plot-exported-file
```

## 新增 MCP 等价能力

本轮迁移低风险 results 能力，并把远场相关能力纳入 runtime 试运行面：

- `get-version-info`：读取 `cst.results` 版本信息。
- `list-result-items`：列出结果树条目，支持 `filter_type="0D/1D"`、`"colormap"`、`"all"`。
- `get-2d-result`：导出 2D 结果为 JSON。
- `plot-exported-file`：把 runtime 导出的 JSON 结果或 CST farfield ASCII/TXT 渲染为 HTML 预览。
- `export-farfield-fresh-session`：通过 fresh GUI session + `FarfieldCalculator` 导出 `Realized Gain` / `Gain` / `Directivity` 标量网格到 ASCII/TXT；拒绝把 `Efield` / `Abs(E)` 当成增益证据。
- `export-existing-farfield-cut-fresh-session`：导出现有 Farfield Cut tree item 到 ASCII/TXT。
- `read-realized-gain-grid-fresh-session`：读取真实 `Realized Gain` dBi 网格，可写入 `analysis/*.json`。
- `inspect-farfield-ascii`：检查 farfield TXT 的 `row_count`、`theta_count`、`phi_count` 与角度范围。
- `plot-farfield-multi`：把一个或多个 farfield TXT / 2D JSON 渲染成 HTML 热力图。
- `calculate-farfield-neighborhood-flatness`：沿用历史 cut JSON 输入格式计算近轴平坦度。

远场迁移状态：

- 解析和 HTML 预览已用既有 `Abs(Realized Gain)[dBi]` 与 `Abs(E)[V/m]` 文件验证；`Abs(E)` 只按场强单位展示，不标记为 dBi。
- 真正启动 CST 的 fresh-session 远场导出/读取已经接入 CLI 和错误分支，但还需要在无残留锁、可启动 CST 的正式 run 上做实机验收后，才能宣布替代 results-MCP 生产链。

仍不迁移的能力：

- 几何建模、材料、边界、网格等建模类 MCP 工具不进入当前 runtime 主线。

## 验收要求

- 每个管道命令仍必须检查最终 JSON 的 `status`。
- 缺命令、缺必要 CLI 参数、未知命令等使用错误必须返回 `status="error"` 的 JSON，不能只输出普通 argparse usage 文本。
- 写操作和 session 操作不得被压成不可审计的长黑盒；关键步骤仍写入当前 run 的 `logs/tool_calls.jsonl` 和 `stages/cli_*.json`。
- 若管道中某一步返回 `status="error"`，后续步骤应停止或显式记录失败，不得继续伪装为完成。

面向其他 agent 的更短说明见 [`cst-runtime-agent-usage.md`](./cst-runtime-agent-usage.md)。
