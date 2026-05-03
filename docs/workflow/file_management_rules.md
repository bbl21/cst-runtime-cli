# 文件管理与日志规则

## 目标

- 让每次任务都能定位到唯一目录
- 让每次运行都能回放：配置、过程、结果、错误分开存
- 让 CST 项目副本、导出文件、分析结果不再混放
- 让后续脚本和 Skill 可以稳定读取标准路径

## 适用范围

- 所有 CST 仿真任务
- 所有参数扫描、优化、导出、诊断任务
- 所有基于 MCP / Skill / 脚本的自动化运行

## 总规则

1. 蓝本项目只读，禁止直接改源项目。
2. 每次新任务必须创建独立任务目录，不得复用旧目录直接覆盖。
3. 每次运行必须创建独立 run 目录，不得把不同轮次输出混在一起。
4. `.cst` 文件、同名结果目录、导出文件、日志文件必须分目录存放。
5. 每次运行至少落 4 类文件：`config.json`、`status.json`、`summary.md`、日志文件。
6. 任务结束后必须记录最终结果，无论成功、失败、中断都要写状态。
7. 远场导出必须放在流程最后，导出后关闭项目且不保存。
8. 任务完成后必须关闭项目并清理 CST 进程。

## 标准目录结构

统一使用如下结构：

```text
CST_MCP/
├── tasks/
│   └── task_{编号}_{slug}/
│       ├── task.json
│       ├── notes.md
│       ├── runs/
│       │   └── run_{编号}/
│       │       ├── config.json
│       │       ├── status.json
│       │       ├── summary.md
│       │       ├── logs/
│       │       │   ├── orchestrator.log
│       │       │   ├── modeler.log
│       │       │   ├── results.log
│       │       │   └── error.log
│       │       ├── projects/
│       │       │   ├── working.cst
│       │       │   └── working/
│       │       ├── exports/
│       │       │   ├── sparams/
│       │       │   ├── farfield/
│       │       │   ├── efield/
│       │       │   └── current/
│       │       ├── analysis/
│       │       │   ├── metrics.json
│       │       │   ├── score.json
│       │       │   └── plots/
│       │       └── stages/
│       │           ├── 01_prepare.json
│       │           ├── 02_simulate.json
│       │           ├── 03_export.json
│       │           └── 04_score.json
│       └── latest -> runs/run_{当前编号}
├── tmp/
└── docs/
```

## 目录职责

### `tasks/`

- 所有正式任务统一放这里。
- 一个任务对应一个长期目录。
- 任务级说明、人工备注、全部运行历史都保存在这里。

### `task_{编号}_{slug}/`

- 编号使用三位或四位连续编号，例如 `task_031_ref_10ghz_match`。
- `slug` 只写简短英文或拼音，禁止空格。
- 任务目录一旦创建，不改名。

### `runs/run_{编号}/`

- 每次实际执行创建一个新的 run。
- 不管是手工测试、自动优化、结果导出，都是独立 run。
- 推荐从 `run_001` 开始递增。

### `projects/`

- 存放当前 run 使用的 CST 工作副本。
- 必须是完整副本：`.cst` 文件 + 同名目录。
- 命名固定为：`working.cst` 和 `working/`，避免脚本到处猜文件名。

### `exports/`

- 只放从 CST 导出的结果文件。
- 按类型分子目录，禁止混堆在同一层。
- 命名必须包含频点、端口、run 信息。

### `analysis/`

- 只放导出后的分析结果。
- 例如评分、目标函数、关键频点指标、可视化图。
- 禁止把原始导出和分析结果混在一起。

### `logs/`

- 只放文本日志。
- 不直接存二进制、不存大图、不存导出数据。

### `stages/`

- 每完成一个阶段写一个阶段状态文件。
- 用于后续断点恢复和失败定位。

## 必须存在的文件

### `task.json`

记录任务级固定信息，建议字段：

```json
{
  "task_id": "task_031_ref_10ghz_match",
  "title": "Improve matching around 10 GHz for ref project",
  "goal": "Reduce |S11| around 10 GHz",
  "source_project": "C:/path/to/source.cst",
  "created_at": "2026-04-09T10:00:00",
  "owner": "opencode"
}
```

### `config.json`

记录本次 run 的输入配置，至少包含：

- `task_id`
- `run_id`
- `source_project`
- `working_project`
- `parameter_ranges`
- `target_metrics`
- `frequency_range`
- `save_project_after_simulation`
- `allow_interactive`

### `status.json`

记录当前 run 的最终状态，必须存在。建议字段：

```json
{
  "task_id": "task_031_ref_10ghz_match",
  "run_id": "run_003",
  "status": "success",
  "stage": "score",
  "started_at": "2026-04-09T10:12:00",
  "finished_at": "2026-04-09T10:45:00",
  "best_result": {
    "s11_db_at_10ghz": -18.4,
    "parameter_set": {
      "L": 126.5,
      "Lf": 124.0
    }
  },
  "error": null
}
```

状态值统一使用：

- `pending`
- `running`
- `success`
- `failed`
- `cancelled`

### `summary.md`

面向人读的摘要，必须简短说明：

- 本次 run 目标
- 修改了哪些参数
- 最终结果如何
- 是否有错误
- 下一步建议

## 日志规则

### 日志分层

- `orchestrator.log`: 调度层日志
- `modeler.log`: 建模 / 仿真控制日志
- `results.log`: 结果读取 / 导出日志
- `error.log`: 仅记录异常摘要与堆栈

### 日志内容要求

每条日志至少包含：

- 时间戳
- 阶段名
- 动作
- 输入摘要
- 输出摘要
- 耗时
- 状态

推荐格式：

```text
2026-04-09T10:15:22 | simulate | start_solver | freq=9-11GHz | waiting | 0.0s | running
2026-04-09T10:18:41 | simulate | solver_done | run_id=12 | ok | 199.2s | success
2026-04-09T10:18:45 | export | read_s11 | treepath=S1,1 | 1001pts | 0.8s | success
```

### 错误日志要求

- 错误先写到 `error.log`
- 同时更新 `status.json`
- 不允许只在终端报错、不落文件

## 文件命名规则

### 导出文件

统一包含以下信息：

- 数据类型
- 频点或频段
- 端口或模式
- run id

示例：

- `s11_run_003.csv`
- `farfield_10.0ghz_run_003.txt`
- `efield_10.0ghz_run_003.csv`
- `surface_current_10.0ghz_run_003.csv`

### 图和报告文件

- `s11_preview_run_003.html`
- `farfield_preview_run_003.html`
- `report_run_003.json`
- `report_run_003.md`

## 蓝本复制规则

1. 复制前必须关闭 CST 项目。
2. 必须复制完整蓝本：`.cst` 文件和同名目录。
3. 蓝本永远只读，工作只在 `projects/working.cst` 上进行。
4. 不允许直接在 `test/`、`ref_model/`、`source/` 目录原地仿真。

## 阶段状态文件规则

每完成一阶段，写入一个 `stages/*.json` 文件。

建议阶段固定为：

1. `01_prepare.json`
2. `02_simulate.json`
3. `03_export.json`
4. `04_score.json`
5. `05_finalize.json`

每个阶段文件至少记录：

- `stage`
- `status`
- `started_at`
- `finished_at`
- `inputs`
- `outputs`
- `error`

## 清理规则

1. `tmp/` 只放临时测试，不放正式 run。
2. `tmp/` 中超过 30 天的目录定期删除。
3. 正式任务目录不手工删单个文件，优先保留完整 run。
4. 大型导出如无必要可删除，但必须保留 `summary.md`、`status.json`、`config.json`、`error.log`。

## 最小执行要求

如果暂时没有完整 orchestrator，手工执行也必须遵守以下最小集合：

1. 先创建 `task_xxx_slug/runs/run_xxx/`
2. 复制项目到 `projects/working.cst`
3. 写 `config.json`
4. 执行过程中写 `logs/*.log`
5. 结束后写 `status.json` 和 `summary.md`

## 对当前仓库的落地建议

当前仓库建议立即补齐以下目录：

```text
<repo>\tasks\
```

并从下一次正式优化任务开始，统一迁移到：

```text
tasks/task_XXX_slug/runs/run_YYY/
```

`test/` 目录只保留测试蓝本和最小实验文件，不再承载正式优化历史。
