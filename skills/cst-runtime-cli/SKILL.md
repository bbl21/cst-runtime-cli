---
name: cst-runtime-cli
description: CST Studio Suite 正式生产入口。覆盖 session 管理、几何建模、参数优化、仿真、S11/远场结果读取和审计落盘。当用户要求使用 CLI/runtime 执行 CST 操作时调用此 Skill。入口为 scripts/cst_runtime_cli.py。
---

# CST Runtime CLI Skill

## 定位

本 Skill 是 CST Runtime CLI 项目的当前正式生产链。

**两种入口模式**：
| 模式 | 命令 | 条件 |
|---|---|---|
| 引导 | `python <skill-root>\scripts\cst_runtime_cli.py` | 首次运行，无需包依赖 |
| 生产 | `uv run python -m cst_runtime` | `uv sync` 后，依赖已安装的 cst-runtime 包 |

- CLI/Skill-only 是正式生产链。
- 所有生产任务使用标准 `tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}` 结构。
- 参考工程一律视为只读蓝本，操作前必须先 `prepare-run` 创建工作副本。

## 第一次使用

从市场安装 Skill 后，coding agent 自动执行以下流程。首次初始化细节见 `references/setup_guide.md`。

```powershell
# 1. 一键全量自检 + 自动修复（含 uv sync + 最终验证）
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true

# 2. 发现工具和管道
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
```

如果 `health-check` 返回 `overall=blocked`，agent 必须停止并向用户展示 `user_instructions`。

**health-check --auto-fix 通过后，所有后续命令必须使用 `uv run` 模式**（`uv run python -m cst_runtime ...`），不可再走系统 Python，否则可能出现库冲突等不可预期结果。

> `health-check --auto-fix true` 可安全重复执行。首次运行完成全部初始化（`uv sync` + `doctor` 验证），后续 `.venv` 已存在时仍跑 `uv sync`（锁文件一致时毫秒级，同时验证 venv 健康），跳过 `doctor` 重检查。

## Skill 包结构

- `SKILL.md`：触发条件、调用原则、风险判断、验收格式。
- `scripts/cst_runtime_cli.py`：CLI 入口。
- `scripts/cst_runtime/`：所有工具实现包（session、modeler、project_ops、results、farfield、audit、workspace、cst_env 等）。
- `tests/`：无 CST 启动的 contract 测试。
- `references/`：首次初始化手册（setup_guide.md）、任务卡模板、管道指南、材料库。

维护要求：
- 修改 CLI/runtime contract 后，先更新仓库内 Skill 包，再运行 `tools\sync_agent_skills.ps1` 同步 agent 生效副本。
- 无 CST 启动 contract 验证：`uv run python -m unittest discover -s skills\cst-runtime-cli\tests`。

## 触发条件

使用本 Skill 的情况：
- 用户明确说"走 CLI"、"runtime CLI"、"低上下文 CLI 验证"。
- 任务涉及 session 管理、建模、仿真、参数优化、结果读取、远场导出中的任一环节。
- 需要生成可审计的 CLI 调用链，落到 run 的 `logs/` 和 `stages/`。
- 首次在环境安装 Skill，需要自动诊断和配置。

不要使用本 Skill 的情况：（无）

## CLI 调用原则

- 入口分两种模式：引导模式用 `python <skill-root>\scripts\cst_runtime_cli.py`（仅首次 health-check），生产模式用 `uv run python -m cst_runtime`（health-check --auto-fix 通过后所有命令）。
- 简单发现命令可直接调用。
- 其他 agent 第一次使用时必须先跑 `health-check` + `doctor`；不要靠猜工具名或参数名。
- 低上下文 agent 不应自己发明管道；先跑 `list-pipelines`，再对目标链路跑 `describe-pipeline --pipeline <name>`。
- 发现类命令不要求工作区已初始化；生产命令需要 task 目录和源 CST 工程。
- 带路径或复杂参数的命令优先使用 `args-template` 生成 JSON，再用 `--args-file` 调用。
- 只有已经通过 `describe-tool` 确认支持直接参数时，才使用 CLI flags。
- 所有 `project_path`、`source_project`、`working_project` 都必须指向具体 `.cst` 文件。
- `change-parameter` 的参数名固定为 `name` 和 `value`。
- 每次调用必须检查 JSON 返回的 `status`；不得只看退出码。

## 低上下文 agent 契约

```text
你在 Windows 项目目录 <repo>。
只依靠本 Skill 和 CLI 完成任务。首次初始化用 python <skill-root>\scripts\cst_runtime_cli.py；
auto-fix 完成后所有后续命令切换为 uv run python -m cst_runtime。
不要使用 archive/ 里的旧脚本，不要写一次性 Python 脚本绕过 CLI，不要修改 ref/ 下参考工程。

首次使用先运行：
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true

再学习 CLI：
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline self-learn-cli

health-check --auto-fix 通过后所有后续命令使用 uv run python -m cst_runtime ...，不可再走系统 Python。

每个不熟悉的工具先运行 describe-tool 和 args-template。
每条不熟悉的管道先运行 describe-pipeline 和 pipeline-template。
复杂参数一律先用 args-template 生成 args JSON 文件，编辑后用 --args-file 调用。
路径必须写到具体 .cst 文件；改参数字段必须是 name 和 value。
每次调用后解析 stdout JSON；只有 status=="success" 才继续。
health-check 返回 overall=blocked 时停止，向用户展示 user_instructions。
失败时停止当前链路，用 record-stage / update-status 写明 blocked 或 needs_validation。
```

## 环境自检与修复

首次初始化上下游工具的细节见 `references/setup_guide.md`。

### 全量健康检查

```powershell
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix false    # 仅诊断
```

### 单项自检

```powershell
python <skill-root>\scripts\cst_runtime_cli.py doctor
python <skill-root>\scripts\cst_runtime_cli.py inspect-cst-environment
python <skill-root>\scripts\cst_runtime_cli.py cst-session-inspect
```

### CST Python 库自安装

```powershell
python <skill-root>\scripts\cst_runtime_cli.py install-cst-libraries --dry-run true    # 扫描不修改
python <skill-root>\scripts\cst_runtime_cli.py install-cst-libraries                    # 自动检测并配置
python <skill-root>\scripts\cst_runtime_cli.py install-cst-libraries --cst-path "D:\CST\AMD64\python_cst_libraries"
```

## 常用管道链

所有管道定义和模板生成均通过 CLI 自身查询：

```powershell
uv run python -m cst_runtime list-pipelines
uv run python -m cst_runtime describe-pipeline --pipeline <name>
uv run python -m cst_runtime pipeline-template --pipeline <name> --output "$run\stages\pipeline_plan.json"
```

关键管道：
1. **first-run**：首次环境设置，health-check + 工具发现。
2. **self-learn-cli**：新 agent 入场自学，不启动 CST。
3. **args-file-tool-call**：复杂参数先生成 args 文件再调用。
4. **project-unlock-check**：检查 `.lok` 锁文件。
5. **cst-session-management-gate**：完整 CST session 生命周期验证。

管道停止规则：
- 每一步都解析 stdout JSON，`status!="success"` 立即停止，除非下一步是明确恢复动作。
- `health-check` 返回 `overall=blocked` 时，必须先解决 `remaining_issues`。
- 任何会触发 CST session、保存、关闭、导出、清理进程的链路，都必须遵守本文件的红线。

## 核心结果工具

| 工具 | 用途 |
|------|------|
| `export-run-results` | 仿真后统一导出 S11、2D 数据、远场到 `exports/` |
| `generate-report` | 生成综合报告（S11 曲线、3D 远场、2D 热力图、操作审计） |

**优化迭代流程请参阅 `cst-runtime-optimization` skill**，本 skill 只提供底层工具。

## 进程管理前置 gate

CLI 命令：`inspect-cst-environment` / `cst-session-inspect` / `cst-session-open` / `cst-session-reattach` / `cst-session-close` / `cst-session-quit` / `cleanup-cst-processes`

完整 gate 顺序见 `describe-pipeline --pipeline cst-session-management-gate`。

硬性停止条件：
- `cst-session-close` 未成功或锁文件未清空时，不执行非 dry-run 的 `cst-session-quit`。
- 存在多个 open projects 时，不做写操作或关闭操作。
- `Access is denied` 残留只能记录；必须带 PID、进程名、错误文本和锁文件状态。

## 结果与远场红线

- 读取结果后禁止保存，以免造成项目报错。
- 远场导出必须放在流程最后；导出后必须 `close(save=False)`。远场导出操作会使 CST 处于错误状态，若保存则下次打开工程将无法正常使用。
- 远场导出放在每轮最后可以免去额外开关 session 的开销——导出完非保存关闭即可，工程文件不受影响。
- S11 原始数据是复数字典，不是 dB 值。
- 远场增益证据只允许使用 `Realized Gain`、`Gain` 或 `Directivity`。`Abs(E)` 不能写成 dBi 增益。
- modeler session 与 results session 是两个独立 session，禁止混用。
- 仿真完成后先关闭 modeler 项目释放工程，再由 results 侧 `close + reopen` 刷新 session。
- 关闭 project 的正确做法：`save=True` 时先 `project.save()`，再调用 `project.close()`。
- 强杀白名单固定为：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`。`Access is denied` 残留只能记录，禁止声称已杀掉。

## 错误处理

- `workspace_not_initialized`：先 `init-workspace`。
- `source_project_missing`：`source_project` 路径不存在。
- `production_dependency_missing`：缺少 CST Python 库依赖，用 `install-cst-libraries` 自动配置。
- `cst_not_found`：未检测到 CST 安装；提供 `--cst-path` 或确认 CST 已安装。
- `pyproject_update_failed`：`pyproject.toml` 无法修改；检查文件权限或手动编辑。
- `overall=blocked`：`health-check` 返回阻塞状态；查看 `remaining_issues` 和 `user_instructions`。

## 历史说明

`skills/cst-runtime-cli-optimization/` 是此 Skill 的前身。

## 最终验收清单

- [ ] `health-check` 返回 `overall=pass`。
- [ ] `status.json` 状态正确（validated / blocked / needs_validation）。
- [ ] 所有输出文件（S11 JSON/HTML、远场 TXT/HTML、grid JSON）已落盘。
- [ ] 工程已关闭且无 `.lok` 锁文件。
- [ ] 清理 CST 进程结果已记录；Access denied 残留没有写成已杀掉。
- [ ] `logs/tool_calls.jsonl` 和 `stages/` 能追溯每一步。
- [ ] 只使用了 Skill + CLI，没有调用旧脚本。
