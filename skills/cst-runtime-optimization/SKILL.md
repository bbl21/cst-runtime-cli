---
name: cst-runtime-optimization
description: 当用户要求使用 CLI/runtime 执行 CST 参数优化循环、S11 指标迭代、多轮仿真对比时调用此 Skill。本 Skill 依赖 cst-runtime-cli 提供基础设施，不携带 runtime scripts，所有 CLI 调用走 base skill 的 uv run python -m cst_runtime 入口。
---

# CST Runtime 优化 Skill

## 定位

本 Skill 专注 CST 参数优化闭环，依赖 `cst-runtime-cli` 提供底层基础设施。

- 不携带 `scripts/` 或 `cst_runtime/` 源码；所有 CLI 调用走 base skill。
- 负责定义优化迭代流程、早停判断、参数策略、数据导出和报告生成。
- 所有生产任务使用标准 `tasks/task_xxx_slug/runs/run_xxx/{projects,exports,logs,stages,analysis}` 结构。

## 依赖声明

本 Skill 不实现 CST 操作，以下工具全部由 `cst-runtime-cli` 提供。所有 CLI 调用通过工作区的 `-m cst_runtime` 入口执行。

| 职责 | CLI 工具 |
|---|---|
| run 创建 | `prepare-run`、`get-run-context` |
| 审计 | `record-stage`、`update-status` |
| 进程/session | `cst-session-open`、`cst-session-close`、`cst-session-quit` |
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
  farfield/{freq}_port{port}_run{N}_{quantity}.json ← 每轮独立
  result_2d_*.json
  report.html                  ← generate-report 输出
```

## 优化迭代模式

### 模式 A：同项目多 run_id（推荐）

适合仅调参数、不改变几何结构。参数变更在同一个 `.cst` 中累积多个 CST run_id。

**两阶段策略：粗网格探针 → 全网格精确优化**

参数 >5 个时先做探针（`design-probes`），用粗网格（`define-mesh` 降低 `steps_per_wave`）跑完折因实验，筛选关键参数 + 检测交互效应，数据注入优化器后开始精确仿真。

**管道工具模式（推荐）：**
```
┌─ 每轮迭代 ──────────────────────────────────────────────────────┐
│ prepare-experiment  ← 修改参数（支持 names+values 批量改参）      │
│   → run-experiment  ← 仿真 + 自动导出 S11 + 远场（每轮独立文件）     │
│   → 解析 s11_run{N}.json → 早停判断                             │
│   → 达标 break / 未达标继续下一轮                                │
└─────────────────────────────────────────────────────────────────┘
```

> `prepare-experiment` 和 `run-experiment` 是**自包含管道**，各自管理完整的 session 生命周期。不要在它们前面手动调用 `cst-session-open`。
>
> 管道由原子工具编排而成（见 `describe-pipeline`），如需在标准流程中插入自定义步骤（如改参后验证实体），可回退到原子工具。

**原子工具模式（需要自定义步骤时）：**
```
┌─ 每轮迭代 ─────────────────────────────────────────┐
│ cst-session-open                                    │
│   → change-parameter → save-project                 │
│   → start-simulation-async → wait-simulation        │
│   → cst-session-close --save false                  │
│   → export-run-results                              │
│   → 早停判断 → 达标 break / 未达标继续下一轮              │
└────────────────────────────────────────────────────┘
```

- 每轮 S11 按 `s11_run{N}.json` 保存所有 run_id
- 远场按 `farfield_{freq}ghz_port{port}_run{N}_{quantity}.json` 保存所有轮数据

> **远场红线**：每轮新仿真会覆盖同名的旧远场结果。`export-run-results` 必须在每轮仿真后立即调用。不导出则永久丢失。

### 模式 B：每次新建项目

适合改变几何实体或需要完全独立数据。每轮独立 `run_00N` 目录。

```
prepare-run(run_00N) → prepare-experiment
  → run-experiment
```

### 结果展示

```powershell
# 先用 args-template 生成参数，再调用
uv run python -m cst_runtime args-template --tool generate-report
# 编辑模板中的 data_dir、output_html、modules 字段
uv run python -m cst_runtime generate-report --args-file <模板.json>
```

`modules` 默认 `s11,farfield3d,timeline`，可选 `metrics,optimization`。

`generate-report` 自动读取 `exports/` 下的全部 `s11_run*.json` 和 `farfield/*.json`，渲染 S11 曲线、3D 远场、参数变更记录和操作审计。

**3D 远场仪表板**：使用 WebGL Canvas 渲染，支持鼠标拖拽旋转、滚轮缩放、自动旋转。页面自包含（无 CDN 依赖），可作为独立 HTML 文件离线查看。

## 自动化优化循环红线

> **早停判断** 是本 Skill 区别于照单执行的关键红线。其他通用红线（session 分离、S11 复数处理、远场增益证据约束等）见 `cst-runtime-cli` SKILL.md。

- 每轮执行流程必须包含早停判断：`仿真 → 读结果 → 解析指标 → 判断是否达目标 → 达则 break，不达则继续`
- "执行"和"评估"不得拆分为两个独立阶段；目标指标必须在每轮循环体内部实时解析和判断
- 若未实现早停导致超过目标后继续执行额外轮次，任务输出必须明确标记为 `overrun`
- 参数发现：使用 `inspect-project`（而非 `list-parameters`）一次性获取全部参数名、值、中文描述。避免逐一 `describe-tool` 查每个参数。

### 已知问题与恢复

| 问题 | 原因 | 恢复方式 |
|------|------|---------|
| 端口非均匀填充 | 修改 `g`(脊间距) 导致端口区域出现多种材料 | `cst-session-close --save false` 丢弃改参，恢复原值 |
| 部分仿真未重跑 | CST 检测到网格未改变时可能返回缓存结果 | `run-experiment` 内置 run_id 预检对比，输出 `warning` 字段 |
| 远场导后保存 | 远场导出使 CST 进入错误状态 | `close(save=False)` 自动处理；**不要额外调用 save** |

## 优化闭环流程

### 1. 创建 run
```
prepare-run → get-run-context
```
后续所有路径使用返回的 `working_project`、`exports_dir`、`logs_dir`。

### 2. 了解工程
```
inspect-project ← 自包含管道，自动开/关 session
```
返回全部参数及其值、全部几何实体。**这是了解工程参数的唯一步骤**，无需再用 `list-parameters`。

### 3. 探针阶段：粗网格筛参数（可选但推荐）

参数 >5 个时，用折因实验主动设计方案筛选重要参数，避免优化器在无关参数上浪费轮数。

探针每个点都是一次 CST 仿真。建议先降低网格密度加速，趋势正确但快 3-5x：

```powershell
# 降低网格密度 → 复制为 _coarse.cst
uv run python -m cst_runtime cst-session-open --project-path <run>\projects\working.cst
uv run python -m cst_runtime define-mesh --project-path <run>\projects\working.cst `
  --steps-per-wave-near 3 --steps-per-wave-far 3 --steps-per-box-near 3 --steps-per-box-far 1
uv run python -m cst_runtime set-mesh-minimum-step-number --project-path <run>\projects\working.cst --num-steps 3
uv run python -m cst_runtime save-project --project-path <run>\projects\working.cst
uv run python -m cst_runtime cst-session-close --project-path <run>\projects\working.cst

# 探针设计 + 执行
uv run python -m cst_runtime design-probes --args-file <...>
# 遍历每个探针: prepare-experiment → run-experiment

# 分析主效应 + 交互 → 确定正式优化的参数集
uv run python -m cst_runtime analyze-probes --args-file <...>

# 探针数据注入优化器，TPE 从首轮就有信息量
uv run python -m cst_runtime study-add-trials --args-file <...>
```

筛选出的参数子集后，用回原始工程（全网格）进入正式优化迭代。

### 4. 迭代循环（每轮重复执行 4a-4d）

> 以下为一轮的完整步骤。重复多轮直到早停条件满足。

推荐使用管道工具，每轮仅需两步：

#### 4a. 改参
```
prepare-experiment [--names [R,g] --values [0.16,23]]  ← 支持批量
```
- 自动完成：open → 改参（循环逐一执行）→ list-parameters 确认 → save → close(kill DE)
- 每轮可改一个或多个参数

#### 4b. 仿真+导出
```
run-experiment
```
- 自动完成：open → start-solver → poll(10s) → close → open(results) → 导出 S11+远场 → close
- S11: `s11_run{N}.json`（每轮递增，不会覆盖）
- 远场: `farfield_{freq}ghz_port{port}_run{N}_{quantity}.json`（每轮独立文件，不会覆盖）

#### 4c. 早停判断
- 解析 `exports/s11_run{N}.json`：`20*log10(hypot(real, imag))` 转 dB
- 判断是否达目标 → 达则 **break**，不达则回到 4a 继续下一轮
- 若超过目标后继续执行额外轮次，任务输出必须标记 `overrun`

#### 4d. 进程清理
```
cst-session-quit
```
- run-experiment 结束后可能残留 orphan DE，每轮末尾清理一次。

### 5. 生成报告
```
generate-report --data_dir <run_dir>
```
输出 `exports/report.html`，自动读取所有 `s11_run*.json`、`farfield_*.txt`。

### 6. 阶段记录
```
record-stage --stage "iteration" --status "completed"
update-status --status "validated"
```

### 7. 进程清理
```
cst-session-quit
```
强杀白名单固定，Access is denied 残留只能记录。

## 引用

以下通用规则详见 `cst-runtime-cli` SKILL.md：
- **CLI 调用原则** — 入口模式、JSON 契约、args-template 优先（默认写到 `.cst_runtime/tmp/`）、project_path 约束
- **管道工具自包含性** — `prepare-experiment`/`run-experiment`/`inspect-project` 各自管理 session，无需前置 `cst-session-open`
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
