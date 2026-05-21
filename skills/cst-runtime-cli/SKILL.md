---
name: cst-runtime-cli
description: CST Studio Suite 正式生产入口。覆盖 session 管理、几何建模、参数优化、仿真、S11/远场结果读取和审计落盘。当用户要求使用 CLI/runtime 执行 CST 操作时调用此 Skill。
---

# CST Runtime CLI Skill

## 核心流程参考（agent 快速入口）

从零开始完成 CST 优化任务的标准三步流程：

### 准备：部署引导（一次性）

新 agent 首次接手工作区按部署引导章节完成部署。后续直接从 ① 开始。

### ① 创建工程（从零开始）

无源 .cst 文件时，先用 `create-blank-project` 建空白工程，再用建模工具搭建结构。标准流程：

```powershell
prepare-run             # 创建 task/run 目录结构
# 建空白工程
uv run python -m cst_runtime create-blank-project --project-path <run>\projects\working.cst
# 建模（按需）
uv run python -m cst_runtime define-brick --args-file <args>
uv run python -m cst_runtime define-port --args-file <args>
uv run python -m cst_runtime set-farfield-monitor --args-file <args>
```

有源 .cst 时直接跳到 ②。

### ② 了解工程（一次）
```powershell
# inspect-project 返回：全部参数名/值/描述 + 全部几何实体 + 远场监视器
uv run python -m cst_runtime inspect-project --project-path <run>\projects\working.cst
```
输出中有 `parameters_count`、`entities_count`、`farfield_monitors_count`，据此决定优化哪些参数、需要导出哪些远场。

### ③ 优化循环（每轮两步）
```powershell
# 改参（支持批量）
uv run python -m cst_runtime prepare-experiment --args-file <args>
# 仿真 + 自动导出 S11 + 远场
uv run python -m cst_runtime run-experiment --args-file <args>
# 解析 exports/s11_run{N}.json → 早停判断
```
- `prepare-experiment` 和 `run-experiment` 是自包含管道，各自管理 session 生命周期
- 产物：`s11_run{N}.json`（每轮递增）+ `farfield/{freq}_port{port}_run{N}_{quantity}.json`（每轮独立）

### ④ 报告 + 清理
```powershell
uv run python -m cst_runtime generate-report --args-file <args>
uv run python -m cst_runtime cst-session-quit
```

> 此流程覆盖 90% 的标准调优任务。如需建模、改边界、设端口等操作，在上述步骤之间插入原子工具即可，管道自管理的 session 不受影响。

## 部署引导（一次性）

`cst_runtime` 是 skill 自带的包（`scripts/cst_runtime/`），首次使用需部署到工作区。

```
1. agent 准备 python + uv → 缺则下载静默装
2. agent Read skill/scripts/bootstrap.py → Write 为 bootstrap.py
3. uv run python bootstrap.py --skill-path <skill-root>\scripts
4. 输出 status=ready → 删除 bootstrap.py
5. uv run python -m cst_runtime init-workspace --workspace <path>
```

`bootstrap.py` 只做两件事：
- 复制 `cst_runtime/` + `references/` → `.cst_runtime/`
- `uv sync` → 将 `cst-runtime` 作为 local dependency 安装到 `.venv`

**后续 `init-workspace` 自动完成：** 创建 task/refs/docs 目录 + 扫描 CST 路径并注册到 `pyproject.toml`。不再需要单独 `install-cst-libraries` 步骤。

### 权限回退

复制失败（PermissionError）输出 `status=need_fallback`：
- agent Read skill 下 `cst_runtime/` 全部 .py → Write 到 `.cst_runtime/cst_runtime/`
- 重跑 `uv run python bootstrap.py`（不带 --skill-path，跳过 copy）

### 生产入口

```
uv run python -m cst_runtime <tool> [args]
```

`cst-runtime` 以 `[tool.uv.sources]` local dependency 方式安装到 `.venv`，无需路径式入口。

- 所有生产任务使用标准 `tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}` 结构。
- 参考工程一律视为只读蓝本，操作前必须先 `prepare-run` 创建工作副本。

## 重新部署

如果后续遇到 `ImportError`，说明 `.cst_runtime/` 中的包可能过期。重新运行 `bootstrap.py --skill-path <skill-root>\scripts` 即可重新部署最新模块。

> 为什么隔离：系统 Python 可能有冲突版本的 CST 库或没有 CST 库。`uv run` 使用工作目录下隔离的 `.venv`，其中只有 `pyproject.toml` 声明的精确依赖，与系统环境完全无关。

## Skill 包结构

- `SKILL.md`：触发条件、调用原则、风险判断、验收格式。
- `scripts/bootstrap.py`：部署引导脚本。
- `scripts/cst_runtime/`：所有工具实现包（session、modeler、project_ops、results、farfield、audit、workspace、cst_env 等）。
- `tests/`：无 CST 启动的 contract 测试。
- `references/`：首次初始化手册（setup_guide.md）、任务卡模板、管道指南、材料库。

维护要求：
- 修改 CLI/runtime contract 后，先更新仓库内 Skill 包，再同步到 agent 安装目录（`Copy-Item ...\.config\opencode\skills\...`）。
- 无 CST 启动 contract 验证：`uv run python -m unittest discover -s skills\cst-runtime-cli\tests`。

## 触发条件

使用本 Skill 的情况：
- 用户明确说"走 CLI"、"runtime CLI"、"低上下文 CLI 验证"。
- 任务涉及 session 管理、建模、仿真、参数优化、结果读取、远场导出中的任一环节。
- 需要生成可审计的 CLI 调用链，落到 run 的 `logs/` 和 `stages/`。
- 首次在环境安装 Skill，需要自动诊断和配置。

不要使用本 Skill 的情况：
- 纯咨询类问题（如"什么是 S11"、"CST 能做什么"），无需 CLI 执行。
- 非 CST 电磁仿真任务。
- 需要手动交互式建模而非 CLI 编排的场景。

## CLI 调用原则

- 入口统一为 `uv run python -m cst_runtime`。首次部署使用 `bootstrap.py`（见部署引导章节），部署完成后全部命令走统一入口。
- **禁止读取 `cst_runtime/` 下的 Python 源码文件**——工具的参数、行为、用法全部通过 `describe-tool` CLI 命令自描述获取。读源码得到的信息可能过时或不完整。
- **禁止将 `cst_runtime/` 模块目录复制到工作区或测试区**——那是 skill 内部模块，工作区只需 `.venv` 和 `pyproject.toml`。所有命令走 skill 入口。
- 简单发现命令可直接调用。
- 其他 agent 第一次使用时必须先跑 `health-check`；不要靠猜工具名或参数名。
- 低上下文 agent 不应自己发明管道；先跑 `list-pipelines`，再对目标链路跑 `describe-pipeline --pipeline <name>`。
- 发现类命令不要求工作区已初始化；生产命令需要 task 目录和源 CST 工程。
- 带路径或复杂参数的命令优先使用 `args-template` 生成 JSON，再用 `--args-file` 调用。
- `args-template` 不带 `--output` 时自动写到 `.cst_runtime/tmp/args_{tool}_{timestamp}.json`，不污染工作区根目录。
- `--args-file` 加载后自动存档副本到 run 的 `stages/args_{tool}_{filename}.json`，纳入审计体系；若源文件在 `.cst_runtime/tmp/` 则自动清理。
- 只有已经通过 `describe-tool` 确认支持直接参数时，才使用 CLI flags（注意：直接参数模式已经修复，对所有工具有效）。
- **数组/对象参数必须走 `--args-file` 方式。** 直接参数模式只暴露标量字段（字符串、数字、布尔值）。如 `prepare-experiment` 的 `names`/`values` 是 JSON 数组，不在直接参数列表中，必须用 `args-template` 生成模板后编辑 `names` 和 `values` 字段。
- 所有 `project_path`、`source_project`、`working_project` 都必须指向具体 `.cst` 文件。
- `change-parameter` 的参数名固定为 `name` 和 `value`。
- 每次调用必须检查 JSON 返回的 `status`；不得只看退出码。

## 环境自检与修复

首次初始化上下游工具的细节见 `references/setup_guide.md`。

### 全量健康检查

```powershell
uv run python -m cst_runtime health-check --auto-fix true
uv run python -m cst_runtime health-check --auto-fix false    # 仅诊断
```

### 单项自检

```powershell
uv run python -m cst_runtime health-check --auto-fix false
uv run python -m cst_runtime cst-session-inspect
```

### CST Python 库自安装

`init-workspace` 会自动扫描并注册 CST 路径到 `pyproject.toml`，通常无需手动安装。

手动覆盖或指定非标准路径时使用：

```powershell
uv run python -m cst_runtime install-cst-libraries --dry-run true    # 扫描不修改
uv run python -m cst_runtime install-cst-libraries                    # 自动检测并配置
uv run python -m cst_runtime install-cst-libraries --cst-path "D:\CST\AMD64\python_cst_libraries"
```

## 管道工具与原子工具的关系

管道是**原子工具的有序编排**，不是黑盒。每个管道内部调用若干原子工具完成工作流，agent 可随时查看管道定义，选择使用管道（便捷）或降级到原子工具（灵活）。

```
管道工具（便捷）         原子工具（灵活编排）
─────────────────        ─────────────────────────
inspect-project           cst-session-open → list-parameters → list-entities → cst-session-close
prepare-experiment        cst-session-open → change-parameter → list-parameters → save-project → cst-session-close
run-experiment            cst-session-open → start-simulation-async → wait-simulation → cst-session-close → open-results-project → export-run-results → cst-session-close
```

**原则：管道覆盖 80% 标准路径，原子工具覆盖 20% 非标场景。** agent 可在管道之间插入自定义步骤，或完全退回到原子工具。

查看管道展开步骤：
```powershell
uv run python -m cst_runtime describe-pipeline --pipeline prepare-experiment
```

### 自包含性

每个管道**自管理 session 生命周期**——自行创建 DE、打开/关闭工程：

- `prepare-experiment`: open → 改参(可批量) → 确认 → save → close(kill DE)
- `run-experiment`: open → start_solver → poll → close → open(results) → 导出 → close
- `inspect-project`: open → 读参数+实体 → close

**不要在管道工具前手动调用 `cst-session-open`**——管道内部会创建独立 DE 并自行清理。手动 open 会导致 session 冲突或 DE 泄漏。

`list-open-projects` 和 `get-run-context` 需要 CST Design Environment 正在运行。无 DE 时必然返回 error，不是工具问题。

## 管道参考表

所有管道定义通过 `describe-pipeline --pipeline <name>` 查询，以下是 9 条管道的概览：

| 管道 | 原子工具展开 | 用途 |
|------|------------|------|
| **inspect-project** | `cst-session-open` → `list-parameters` → `list-entities` → `inspect-farfield-monitors` → `cst-session-close` | 了解工程（参数+实体+远场） |
| **prepare-experiment** | `cst-session-open` → `change-parameter` → `list-parameters` → `save-project` → `cst-session-close` | 改参→保存 |
| **run-experiment** | `cst-session-open` → `start-simulation-async` → `wait-simulation` → `cst-session-close` → `export-run-results` | 仿真→导出 |

| **async-simulation-refresh-results** | `start-simulation-async` → `wait-simulation` → `cst-session-close` → `list-run-ids` → `get-1d-result` | 异步仿真→读结果 |
| **project-unlock-check** | `infer-run-dir` → `wait-project-unlocked` | 检查锁文件 |
| **cst-session-management-gate** | 6 步完整 session 生命周期验证 | session 管理 |
| **args-file-tool-call** | `describe-tool` → `args-template` → `<tool>` | 复杂参数调用 |
| **first-run** | `health-check` → `help` → `list-tools` → `list-pipelines` | 首次环境设置 |
| **self-learn-cli** | `health-check` → `help` → `list-tools` → `list-pipelines` → `describe-pipeline` → `describe-tool` → `args-template` | agent 入场自学 |

用法：

```powershell
# 查看管道展开步骤
uv run python -m cst_runtime describe-pipeline --pipeline prepare-experiment

# 生成管道执行计划文件
uv run python -m cst_runtime pipeline-template --pipeline run-experiment --output stages\pipeline_plan.json
```

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

CLI 命令：`cst-session-inspect` / `cst-session-open` / `cst-session-reattach` / `cst-session-close` / `cst-session-quit`

完整 gate 顺序见 `describe-pipeline --pipeline cst-session-management-gate`。

硬性停止条件：
- `cst-session-close` 或 `close_project` 未成功时，不执行后续操作。
- `close_project()` 默认 `kill_processes=True`，自动杀死该 project 的 DE 进程并清理孤悬 DE。如需保留 DE（罕见），传 `kill_processes=False`。
- 存在多个 open projects 时，不做写操作或关闭操作。
- `Access is denied` 残留只能记录；必须带 PID、进程名、错误文本和锁文件状态。

## 结果与远场红线

- 远场导出必须放在流程最后；导出后 `close_project(project_path, save=False)` 自动清理 DE 进程。远场导出操作会使 CST 处于错误状态，若保存则下次打开工程将无法正常使用。
- 远场导出放在每轮最后可以免去额外开关 session 的开销——`close_project(save=False)` 自动清理，工程文件不受影响。
- S11 原始数据是复数字典，不是 dB 值。
- 远场增益证据只允许使用 `Realized Gain`、`Gain` 或 `Directivity`。`Abs(E)` 不能写成 dBi 增益。
- modeler session 与 results session 是两个独立 session，禁止混用。
- 仿真完成后调用 `close_project()`（默认 `kill_processes=True`）释放工程并清理 DE 进程。下次 `open_project()` 自动获得干净 DE。
- 关闭 project 的正确做法：`save=True` 时先 `project.save()`，再调用 `close_project()`。远场导出后 `close_project(save=False)`。

## 错误处理

- `workspace_not_initialized`：先 `init-workspace`。
- `source_project_missing`：`source_project` 路径不存在。
- `production_dependency_missing`：缺少 CST Python 库依赖。先确认 CST 已安装，再用 `install-cst-libraries` 手动配置。
- `cst_not_found`：未检测到 CST 安装；提供 `--cst-path` 或确认 CST 已安装。
- `pyproject_update_failed`：`pyproject.toml` 无法修改；检查文件权限或手动编辑。
- `overall=blocked`：`health-check` 返回阻塞状态；查看 `remaining_issues` 和 `user_instructions`。

## 历史说明

`skills/cst-runtime-optimization/`（仅 SKILL.md，无代码）是此 Skill 的优化闭环配套 skill，本 skill 只提供底层工具。

## 最终验收清单

- [ ] `health-check` 返回 `overall=pass`。
- [ ] `status.json` 状态正确（validated / blocked / needs_validation）。
- [ ] 所有输出文件（S11 JSON/HTML、远场 TXT/HTML、grid JSON）已落盘。
- [ ] 工程已关闭且无 `.lok` 锁文件（`close_project` 自动清理 DE 进程，无需额外 `cleanup-cst-processes`）。
- [ ] 清理 CST 进程结果已记录；Access denied 残留没有写成已杀掉（有残留属于非阻塞，记录即可）。
- [ ] `logs/tool_calls.jsonl` 和 `stages/` 能追溯每一步。
- [ ] 只使用了 Skill + CLI，没有调用旧脚本。
