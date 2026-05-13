---
name: cst-runtime-cli
description: CST Studio Suite 正式生产入口。覆盖 session 管理、几何建模、参数优化、仿真、S11/远场结果读取和审计落盘。当用户要求使用 CLI/runtime 执行 CST 操作时调用此 Skill。入口为 scripts/cst_runtime_cli.py。历史 MCP 工具已退场。
---

# CST Runtime CLI Skill

## 定位

本 Skill 是 CST_MCP 项目的当前正式生产链。执行入口为 `python <skill-root>\scripts\cst_runtime_cli.py`。

- CLI/Skill-only 是正式生产链；`mcp/` 目录中的历史 MCP 工具不再作为正式执行依赖。
- 所有生产任务使用标准 `tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}` 结构。
- 参考工程一律视为只读蓝本，操作前必须先 `prepare-run` 创建工作副本。
- 低上下文 agent 不应调用 MCP tools。

## Skill 包结构

- `SKILL.md`：触发条件、调用原则、风险判断、验收格式。
- `scripts/cst_runtime_cli.py`：CLI 入口。
- `scripts/cst_runtime/`：所有工具实现包（session、modeler、project_ops、results、farfield、audit、workspace 等）。
- `tests/`：无 CST 启动的 contract 测试。
- `references/`：任务卡模板、管道指南、材料库。

维护要求：
- 修改 CLI/runtime contract 后，先更新仓库内 Skill 包，再运行 `tools\sync_agent_skills.ps1` 同步 agent 生效副本。
- 无 CST 启动 contract 验证：`uv run python -m unittest discover -s skills\cst-runtime-cli\tests`。

## 触发条件

使用本 Skill 的情况：
- 用户明确说"走 CLI"、"runtime CLI"、"低上下文 CLI 验证"。
- 任务涉及 session 管理、建模、仿真、参数优化、结果读取、远场导出中的任一环节。
- 需要生成可审计的 CLI 调用链，落到 run 的 `logs/` 和 `stages/`。

不要使用本 Skill 的情况：
- 用户要求使用历史 MCP tool 调用（已退场）。

## CLI 调用原则

- 入口固定为：`python <skill-root>\scripts\cst_runtime_cli.py ...`
- 简单发现命令可直接调用：`doctor`、`usage-guide`、`list-tools`、`list-pipelines`、`describe-tool`、`describe-pipeline`、`args-template`、`pipeline-template`。
- 其他 agent 第一次使用时必须先跑 `doctor` 和 `usage-guide`；不要靠猜工具名或参数名。
- 低上下文 agent 不应自己发明管道；先跑 `list-pipelines`，再对目标链路跑 `describe-pipeline --pipeline <name>`。
- 发现类命令不要求工作区已初始化；生产命令需要 task 目录和源 CST 工程。
- 带路径或复杂参数的命令优先使用 `args-template` 生成 JSON，再用 `--args-file` 调用。
- 只有已经通过 `describe-tool` 确认支持直接参数时，才使用 CLI flags。
- 所有 `project_path`、`source_project`、`working_project` 都必须指向具体 `.cst` 文件。
- `change-parameter` 的参数名固定为 `name` 和 `value`。
- 每次调用必须检查 JSON 返回的 `status`；不得只看退出码。

推荐调用模板：

```powershell
python <skill-root>\scripts\cst_runtime_cli.py describe-tool --tool change-parameter
python <skill-root>\scripts\cst_runtime_cli.py args-template --tool change-parameter --output "$run\stages\change_parameter_args.json"
python <skill-root>\scripts\cst_runtime_cli.py change-parameter --args-file "$run\stages\change_parameter_args.json"
```

S11 JSON 结构固定为外层元数据加数据数组：`xdata` 是频率序列；`ydata` 是复数序列。计算 dB 时必须先取 `sqrt(real^2 + imag^2)`，再做 `20*log10(...)`。

## 低上下文 agent 契约

```text
你在 Windows 项目目录 <repo>。
只依靠本 Skill 和 python <skill-root>\scripts\cst_runtime_cli.py ... CLI 完成任务。
不要调用 MCP tool，不要使用 archive/ 里的旧脚本，不要写一次性 Python 脚本绕过 CLI，不要修改 ref/ 下参考工程。

先运行：
python <skill-root>\scripts\cst_runtime_cli.py doctor
python <skill-root>\scripts\cst_runtime_cli.py usage-guide
python <skill-root>\scripts\cst_runtime_cli.py list-tools
python <skill-root>\scripts\cst_runtime_cli.py list-pipelines
python <skill-root>\scripts\cst_runtime_cli.py describe-pipeline --pipeline self-learn-cli

每个不熟悉的工具先运行 describe-tool 和 args-template。
每条不熟悉的管道先运行 describe-pipeline 和 pipeline-template。
复杂参数一律先用 args-template 生成 args JSON 文件，编辑后用 --args-file 调用。
路径必须写到具体 .cst 文件；改参数字段必须是 name 和 value。
每次调用后解析 stdout JSON；只有 status=="success" 才继续。
失败时停止当前链路，用 record-stage / update-status 写明 blocked 或 needs_validation。
```

## 常用管道链

所有管道定义和模板生成均通过 CLI 自身查询：

```powershell
python <skill-root>\scripts\cst_runtime_cli.py list-pipelines
python <skill-root>\scripts\cst_runtime_cli.py describe-pipeline --pipeline <name>
python <skill-root>\scripts\cst_runtime_cli.py pipeline-template --pipeline <name> --output "$run\stages\pipeline_plan.json"
```

关键管道：
1. **self-learn-cli**：新 agent 入场自学，不启动 CST。
2. **args-file-tool-call**：复杂参数先生成 args 文件再调用。
3. **project-unlock-check**：检查 `.lok` 锁文件。
4. **cst-session-management-gate**：完整 CST session 生命周期验证。
5. **latest-s11-preview**：读取最新 S11 并生成 HTML 预览。
6. **async-simulation-refresh-results**：异步仿真 → 关闭 modeler → 刷新 results → 读 S11。
7. **s11-json-comparison**：JSON 格式 S11 对比页生成。
8. **s11-farfield-dashboard**：S11 + 远场合一的 dashboard。
9. **farfield-realized-gain-preview**：fresh-session 远场导出/读取/预览。
10. **project-result-preview**：通过 cst.results 导出并渲染预览。

管道停止规则：
- 每一步都解析 stdout JSON，`status!="success"` 立即停止，除非下一步是明确恢复动作。
- 任何会触发 CST session、保存、关闭、导出、清理进程的链路，都必须遵守 `AGENTS.md` 的 Level 1 红线。

## 自包含工作区自举

```powershell
python <skill-root>\scripts\cst_runtime_cli.py doctor --workspace <empty>
python <skill-root>\scripts\cst_runtime_cli.py init-workspace --workspace <empty>
python <skill-root>\scripts\cst_runtime_cli.py init-task --workspace <empty> --task-id task_001_demo --source-project C:\path\model.cst --goal demo
```

## 进程管理前置 gate

CLI 命令统一为：`cst-session-inspect` / `cst-session-open` / `cst-session-reattach` / `cst-session-close` / `cst-session-quit`

完整 gate 顺序见 `describe-pipeline --pipeline cst-session-management-gate`。

硬性停止条件：
- `cst-session-close` 未成功或锁文件未清空时，不执行非 dry-run 的 `cst-session-quit`。
- 存在多个 open projects 时，不做写操作或关闭操作。
- `Access is denied` 残留只能记录；必须带 PID、进程名、错误文本和锁文件状态。

## 结果与远场红线

- 读取结果后禁止保存，以免造成项目报错。
- 远场导出必须放在流程最后；导出后必须 `close(save=False)`。
- S11 原始数据是复数字典，不是 dB 值。
- 远场增益证据只允许使用 `Realized Gain`、`Gain` 或 `Directivity`。`Abs(E)` 不能写成 dBi 增益。
- modeler session 与 results session 是两个独立 session，禁止混用。
- 仿真完成后先关闭 modeler 项目释放工程，再由 results 侧 `close + reopen` 刷新 session。
- 关闭 project 的正确做法：`save=True` 时先 `project.save()`，再调用 `project.close()`。
- 强杀白名单固定为：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`。`Access is denied` 残留只能记录，禁止声称已杀掉。

## 错误处理

- `workspace_not_initialized`：先 `init-workspace`。
- `source_project_missing`：`source_project` 路径不存在。
- `production_dependency_missing`：缺少 CST Python 库依赖。
- `invalid_json_args`：改用 `--args-file`。
- `ambiguous_open_projects`：关闭无关 CST 工程后重试。
- `project_not_open`：先 `cst-session-open`。
- `lock_not_released`：确认项目已关闭，等待或清理。
- `no_cst_session`：results 读取不阻塞，modeler 写操作需先 open。

## 历史说明

`mcp/` 目录曾是早期 MCP 工具链实现，已不再作为正式执行依赖。`skills/cst-runtime-cli-optimization/` 是此 Skill 的前身。

## 最终验收清单

- [ ] `status.json` 状态正确（validated / blocked / needs_validation）。
- [ ] 所有输出文件（S11 JSON/HTML、远场 TXT/HTML、grid JSON）已落盘。
- [ ] 工程已关闭且无 `.lok` 锁文件。
- [ ] 清理 CST 进程结果已记录；Access denied 残留没有写成已杀掉。
- [ ] `logs/tool_calls.jsonl` 和 `stages/` 能追溯每一步。
- [ ] 只使用了 Skill + CLI，没有调用 MCP 或旧脚本。
