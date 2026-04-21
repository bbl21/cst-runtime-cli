# CST CLI 原子工具 POC

> 本文档记录早期 `tools/cst_cli.py` 的最小验证结果。它不是规则源；规则与红线仍以 `AGENTS.md` 为准，正式执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。2026-04-21 起脚本已归档到 `archive/tools-legacy-20260421/cst_cli.py`，当前 runtime 入口是 `uv run python -m cst_runtime`。

## 目标

验证“Skill 指导 agent 调用轻量 CLI 原子工具”是否可行，重点检查：

- 不依赖 MCP HTTP 服务。
- 工具具备 `list-tools` / `describe-tool` / `invoke` 风格的发现与调用入口。
- 每个项目操作都显式传入 `project_path`。
- CLI 工具能跨独立进程重新附着 CST 活动项目。
- 工具返回纯 JSON，供 agent 读取和判断。
- 工具调用写入当前 run 的 `logs/tool_calls.jsonl` 与 `stages/*.json`。

## 当前实现

POC 文件：

- `archive/tools-legacy-20260421/cst_cli.py`

当前工具：

| 工具 | 类别 | 风险 | 说明 |
| --- | --- | --- | --- |
| `list-tools` | meta | read | 列出当前 POC 工具索引 |
| `describe-tool` | meta | read | 返回单个工具说明 |
| `invoke` | meta | varies | 通过工具名和 JSON 参数调用 |
| `prepare-run` | run | filesystem-write | 复用现有 `prepare_new_run` 创建标准 run 工作区 |
| `list-open-projects` | project | read | 列出当前 CST 可见的打开工程 |
| `assert-project-open` | project | read | 校验目标 `project_path` 是当前唯一打开工程 |
| `open-project` | project | session | 按显式 `project_path` 打开 CST 工程 |
| `list-parameters` | modeler | read | 校验项目后读取参数 |
| `change-parameter` | modeler | write | 校验项目后修改单个参数 |
| `close-project` | project | session | 校验项目后关闭，默认 `save=false` |

## 验证记录

验证目录：

```text
tmp/cst_cli_poc_task/
```

测试链路：

1. `uv run python tools/cst_cli.py list-tools`
2. `uv run python tools/cst_cli.py describe-tool --tool change-parameter`
3. `uv run python tools/cst_cli.py prepare-run --args-file tmp/cst_cli_poc_task/prepare_run_args.json`
4. `uv run python tools/cst_cli.py open-project --args-file tmp/cst_cli_poc_task/project_args.json`
5. `uv run python tools/cst_cli.py assert-project-open --args-file tmp/cst_cli_poc_task/project_args.json`
6. `uv run python tools/cst_cli.py list-parameters --args-file tmp/cst_cli_poc_task/project_args.json`
7. `uv run python tools/cst_cli.py change-parameter --args-file tmp/cst_cli_poc_task/change_parameter_args.json`
8. `uv run python tools/cst_cli.py list-parameters --args-file tmp/cst_cli_poc_task/project_args.json`
9. `uv run python tools/cst_cli.py close-project --args-file tmp/cst_cli_poc_task/close_project_args.json`

验证结果：

- `prepare-run` 成功创建 `run_001` 与 `projects/working.cst`。
- `open-project` 成功打开临时工作副本。
- `assert-project-open` 成功确认当前只有目标工程打开。
- `list-parameters` 初次读取到 19 个参数，`R=0.1`。
- `change-parameter` 成功把 `R` 改为 `0.102`。
- 再次 `list-parameters` 成功读到 `R=0.102`。
- `close-project(save=false)` 成功关闭工程。
- `close-project` 后短时间内存在 `Model.lok`，约 3 秒后释放；随后用 `tools/kill_cst.ps1` 清理空 CST 主窗口。
- 最终未发现 `.lok` 锁文件残留，且没有 `CST DESIGN ENVIRONMENT_AMD64` 进程残留。

审计产物：

```text
tmp/cst_cli_poc_task/runs/run_001/logs/tool_calls.jsonl
tmp/cst_cli_poc_task/runs/run_001/stages/cli_*.json
```

## 关键结论

CLI 原子工具路线在最小项目管理链路上成立：

- CLI 进程之间不能继承 Python 内存中的 CST `project` 对象。
- 但在单一打开工程条件下，独立 CLI 进程可以通过 CST API 重新附着到当前活动项目。
- 生产级工具不能只依赖 active project；必须显式传入 `project_path`，并做身份校验。
- 当前 POC 为安全起见，在多个 CST 工程同时打开时直接返回 `ambiguous_open_projects`，拒绝写操作。
- stdout 必须保持纯 JSON；POC 已屏蔽 `DeprecationWarning`，避免污染 agent 解析。

## 当前限制

- POC 只支持“目标工程是唯一打开工程”的安全路径。
- 当前 CST Python API 暂未在 POC 中找到稳定的“按路径获取 project 对象”接口；因此多工程并发管理尚未解决。
- `prepare-run` 复用了 `mcp/advanced_mcp.py` 的实现，因此 POC 不是完整 core/runtime 重构。
- 尚未覆盖仿真启动、仿真轮询、results 读取、远场导出。
- `close-project` 后锁释放存在短延迟，自动化流程需要显式等待锁文件消失或执行清理。

## 后续建议

下一步不应马上全量迁移 95 个 MCP 工具。建议先扩展项目身份层：

1. 增强 `list-open-projects`，记录窗口标题、锁文件、匹配 run。
2. 增加 `wait-project-unlocked`，解决关闭后的锁释放延迟。
3. 增加 `verify-project-identity`，把 path、window title、run 目录做成统一校验。
4. 在 POC 上迁入 `start-simulation` / `poll-simulation`，验证长流程是否仍能由 agent 分步判断。
5. results 侧另做 fresh-session CLI 工具，避免与 modeler 活对象混用。
