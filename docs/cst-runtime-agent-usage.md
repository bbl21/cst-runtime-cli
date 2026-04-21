# CST Runtime Agent 使用说明

本文是给其他 agent 使用 `cst_runtime` CLI 的最小说明。它不是规则源；项目红线仍以 `AGENTS.md` 为准。

## 一句话入口

所有调用都从仓库根目录执行：

```powershell
uv run python -m cst_runtime <command>
```

若目标环境没有 `uv`，或 `uv` 无法解析 `pyproject.toml` 中的 CST Python 库绝对路径，可在已经配置好 `PYTHONPATH` / CST Python 库的环境里使用：

```powershell
python -m cst_runtime <command>
```

不要调用 `archive/tools-legacy-20260421/` 下的旧脚本；不要直接编辑 `ref/` 工程。

## Agent 固定四步

0. 新环境、迁移包、不同 coding agent 或不同终端里，先做兼容性自检：

```powershell
uv run python -m cst_runtime doctor
```

如果 `uv run` 在目标环境里因 CST 绝对路径依赖失败，改用：

```powershell
python -m cst_runtime doctor
```

1. 再读取机器可读说明：

```powershell
uv run python -m cst_runtime usage-guide
```

2. 发现工具：

```powershell
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime describe-tool --tool get-1d-result
```

3. 生成参数模板，保存到当前 task/run 附近：

```powershell
uv run python -m cst_runtime args-template --tool get-1d-result --output "$run\stages\get_1d_result_args.json"
```

4. 修改 args 文件后调用：

```powershell
uv run python -m cst_runtime get-1d-result --args-file "$run\stages\get_1d_result_args.json"
```

每一步都必须解析 stdout JSON。只有 `status == "success"` 才能进入下一步。

## 错误返回契约

CLI 使用错误也返回 JSON，例如缺命令、缺 `--tool`、未知工具名：

```json
{
  "status": "error",
  "error_type": "cli_usage_error",
  "message": "...",
  "next_steps": ["Run: uv run python -m cst_runtime usage-guide"]
}
```

参数 JSON 错误返回：

```json
{
  "status": "error",
  "error_type": "invalid_json_args",
  "message": "..."
}
```

工具执行错误返回：

```json
{
  "status": "error",
  "error_type": "...",
  "message": "..."
}
```

缺少工具业务参数，例如没有传 `project_path`：

```json
{
  "status": "error",
  "error_type": "missing_required_arg",
  "message": "project_path is required",
  "runbook": {
    "template": "uv run python -m cst_runtime args-template --tool open-project --output <args.json>"
  }
}
```

不要只看退出码；退出码非零时也要读取 stdout JSON，按 `error_type` 和 `message` 判断。

## 推荐输入方式

优先使用 `--args-file`，尤其是 Windows 路径：

```powershell
uv run python -m cst_runtime <tool> --args-file C:\path\to\args.json
```

需要串联时可用 stdin：

```powershell
@{ project_path = "$run\projects\working.cst" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime infer-run-dir |
  uv run python -m cst_runtime wait-project-unlocked
```

合并规则：

```text
final_args = stdin_json + explicit_args
```

同名字段以 `--args-file` / `--args-json` 为准。和 `--args-file` / `--args-json` 合并 stdin 时必须加 `--args-stdin`：

```powershell
@{ file_path = "$exportsDir\result.json" } |
  ConvertTo-Json -Depth 8 |
  uv run python -m cst_runtime plot-exported-file --args-stdin --args-file "$run\stages\plot_args.json"
```

如果已经提供 `--args-file` / `--args-json` 且没有 `--args-stdin`，CLI 不会读取 stdin，避免 Trae 等非 TTY 终端阻塞。

## 迁移兼容性检查

不同 coding agent 或不同机器上的常见问题：

- `uv` 不在 PATH：`doctor` 会给出 `uv_on_path=warning`，可改用 `python -m cst_runtime`。
- CST 安装路径不同：`doctor` 会检查 `pyproject_cst_path_dependency`。如果为 warning，`uv run` 可能在 CLI 启动前失败。
- CST Python 库不可导入：`doctor` 的 `import:cst.interface` / `import:cst.results` 会是 warning；此时 `usage-guide`、`list-tools`、`args-template` 仍可用，但 CST 项目操作不可用。
- 非 TTY stdin：CLI 默认不会在已有 `--args-file` / `--args-json` 时读 stdin；需要合并时显式加 `--args-stdin`。
- shell 引号差异：优先 `--args-file`，不要让 agent 手写复杂 `--args-json`。
- 编码差异：args 文件统一 UTF-8；agent 解析 stdout JSON，不要依赖终端显示编码。
- stdout JSON 使用 ASCII-safe 转义输出，避免 GBK/UTF-8 终端差异影响机器解析。

迁移验收的最低命令：

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime describe-tool --tool get-1d-result
```

若第一条因 `uv` 环境失败，先用：

```powershell
python -m cst_runtime doctor
```

## 常用工具族

- run：`prepare-run`、`get-run-context`
- audit：`record-stage`、`update-status`
- project_identity：`infer-run-dir`、`wait-project-unlocked`、`verify-project-identity`
- modeler：`open-project`、`list-parameters`、`change-parameter`、`start-simulation-async`、`is-simulation-running`、`save-project`、`close-project`
- results：`list-run-ids`、`get-parameter-combination`、`get-1d-result`、`generate-s11-comparison`、`plot-exported-file`
- farfield 试迁移：`export-farfield-fresh-session`、`read-realized-gain-grid-fresh-session`、`inspect-farfield-ascii`、`plot-farfield-multi`

远场增益证据必须走 `Realized Gain` / `Gain` / `Directivity`；`Abs(E)` 只能作为场强，不得标记为 dBi。

## 最小安全自检

不启动 CST 的自检：

```powershell
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime describe-tool --tool get-1d-result
uv run python -m cst_runtime args-template --tool get-1d-result
```

错误出口自检：

```powershell
uv run python -m cst_runtime
uv run python -m cst_runtime describe-tool
uv run python -m cst_runtime no-such-tool
```

以上三条都应返回 `status="error"` 的 JSON，而不是普通 argparse usage 文本。
