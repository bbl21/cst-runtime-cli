---
name: cst-runtime-optimization
description: 当用户要求使用 CLI/runtime 执行 CST 参数优化循环、S11 指标迭代、多轮仿真对比时调用此 Skill。本 Skill 依赖 cst-runtime-cli 提供基础设施，不携带 runtime scripts，所有 CLI 调用走 base skill 的 scripts/cst_runtime_cli.py。
---

# CST Runtime 优化 Skill

## 定位

本 Skill 专注 CST 参数优化闭环，依赖 `cst-runtime-cli` 提供底层基础设施。

- 不携带 `scripts/` 或 `cst_runtime/` 源码；所有 CLI 调用走 base skill。
- 负责定义优化迭代流程、早停判断、参数策略、数据导出和报告生成。
- 所有生产任务使用标准 `tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}` 结构。

## 依赖声明

本 Skill 不实现 CST 操作，以下工具全部由 `cst-runtime-cli` 提供。调用时 `<skill-root>` 指向 base skill 目录。

| 职责 | CLI 工具 |
|---|---|
| run 创建 | `prepare-run`、`get-run-context` |
| 审计 | `record-stage`、`update-status` |
| 进程/session | `cst-session-open`、`cst-session-close`、`cleanup-cst-processes` |
| 参数 | `list-parameters`、`change-parameter` |
| 仿真 | `start-simulation-async`、`wait-simulation` |
| 结果导出 | **`export-run-results`**（统一导出 S11+2D+远场） |
| 结果展示 | **`generate-report`**（生成综合报告） |

## 触发条件

使用本 Skill：
- 参数优化循环、S11 指标迭代、多轮仿真对比
- 需要实现"仿真 → 读结果 → 解析指标 → 判断是否达目标"的自动化循环
- 需要定义早停条件（target S11 阈值、轮数上限）

不使用本 Skill：
- 单次仿真或结果读取（用 `cst-runtime-cli`）
- 纯几何建模、材料、边界定义

## 文件名约定

导出文件统一放到 `exports/`，固定命名：

```
exports/
  s11_run{N}.json              ← {N}=CST run_id，无时间戳
  farfield_{freq}ghz_run{N}.txt ← 远场粗精度（默认 2° 步进）
  result_2d_*.json
  report.html                  ← generate-report 输出
```

## 优化迭代模式

### 模式 A：同项目多 run_id

适合仅调参数、不改变几何结构。参数变更在同一个 `.cst` 中累积多个 CST run_id。

```
prepare-run(run_00N) → cst-session-open
  → change-parameter → save-project
  → start-simulation-async → wait-simulation → cst-session-close
  → export-run-results
```

- 每轮 S11 按 `s11_run{N}.json` 保存所有 run_id
- 远场每轮覆盖写（粗精度，2° 步进）

> **模式 A 远场红线**：同 `.cst` 工程内每轮新仿真会覆盖旧的远场结果。必须在每轮仿真后立即导出远场（`export-run-results` 或 `export-farfield-fresh-session`），以带 `run{N}` 的文件名落盘。不导出则永久丢失，无法在最终报告中展示所有轮的 3D 远场对比。

### 模式 B：每次新建项目

适合改变几何实体或需要完全独立数据。每轮独立 `run_00N` 目录。

```
prepare-run(run_00N) → cst-session-open
  → change-parameter / define-brick / boolean-...
  → save-project
  → start-simulation-async → wait-simulation → cst-session-close
  → export-run-results
```

### 结果展示

随时调用，传入 data_dir 即可：

```
generate-report --data_dir <run 或 task 目录>
```

自动读取 `exports/` 下所有约定文件，渲染 S11 曲线、3D 远场、2D 热力图、操作审计追踪。

## 自动化优化循环红线

> **早停判断** 是本 Skill 区别于照单执行的关键红线。其他通用红线（session 分离、S11 复数处理、远场增益证据约束等）见 `cst-runtime-cli` SKILL.md。

- 每轮执行流程必须包含早停判断：`仿真 → 读结果 → 解析指标 → 判断是否达目标 → 达则 break，不达则继续`
- "执行"和"评估"不得拆分为两个独立阶段；目标指标必须在每轮循环体内部实时解析和判断
- 若未实现早停导致超过目标后继续执行额外轮次，任务输出必须明确标记为 `overrun`

## 优化闭环流程

### 1. 创建 run

```
prepare-run → get-run-context
```

后续所有路径使用返回的 `working_project`、`exports_dir`、`logs_dir`。

### 2. 打开工程

```
cst-session-open → verify-project-identity → list-parameters
```

若返回 `ambiguous_open_projects`，必须先关闭无关 CST 工程。

### 3. 修改参数

```
change-parameter --name <p> --value <v>
list-parameters  ← 确认参数生效
```

`change-parameter` 字段固定为 `name` 和 `value`。

### 4. 仿真

```
start-simulation-async → wait-simulation
```

优先使用异步仿真，同步 `start-simulation` 更容易超时。

### 5. 导出结果

```
cst-session-close --save false
export-run-results --project_path <.cst>
```

- 先关 modeler（释放工程锁），再导出
- 远场导出会使 CST 处于错误状态，导出后必须 `close(save=False)`（不保存则工程文件不受影响，可再次打开）
- `export-run-results` 自动导出 S11、2D、远场到 `exports/`
- 文件固定命名：`s11_run{N}.json`、`farfield_{freq}ghz_run{N}.txt`

### 6. 生成报告

```
generate-report --data_dir <run_dir>
```

输出 `exports/report.html`。

### 7. 阶段记录

每轮记录参数变更、run_id、指标、文件输出、异常和耗时。

```
record-stage --stage "iteration" --status "completed"
update-status --status "validated"
```

### 8. 进程清理

```
cleanup-cst-processes
```

强杀白名单：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`。Access is denied 残留只能记录，禁止声称已杀掉。

## 引用

以下通用规则详见 `cst-runtime-cli` SKILL.md：
- **CLI 调用原则** — 入口模式、JSON 契约、args-template 优先、project_path 约束
- **错误处理** — `workspace_not_initialized`、`source_project_missing`、`ambiguous_open_projects`、`lock_not_released`、`Access is denied`
- **进程管理前置 gate** — `cst-session-management-gate` 管道、硬性停止条件
- **结果与远场红线** — S11 复数处理、modeler/results session 分离、仿真后关闭顺序、`close(save=False)` 规则

## 最终验收清单

- [ ] 优化循环每轮均实现早停判断
- [ ] `exports/` 下有 `s11_run{N}.json`
- [ ] `status.json` 状态正确
- [ ] 工程已关闭且无 `.lok` 锁文件
- [ ] 清理 CST 进程结果已记录
- [ ] `logs/tool_calls.jsonl` 和 `stages/` 可追溯
- [ ] 只使用了 Skill + CLI，没有调用旧脚本
