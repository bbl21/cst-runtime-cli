---
name: cst-simulation-optimization
description: 当任务需要对某个 CST 工程做参数优化，并围绕目标频点反复执行"复制蓝本→改参数→跑仿真→刷新结果→读取指标→记录日志"闭环，以改善 S11、VSWR、增益或方向图等指标时，调用此 Skill。
---

# CST 仿真优化 Skill

## 触发点

当用户出现以下意图时，应优先触发这个 Skill：

- 用户要求对某个 CST 工程做参数优化
- 用户要求改善 `S11`、`VSWR`、阻抗匹配、带宽、增益、方向图等指标
- 用户要求围绕某个频点或频段做仿真调参
- 用户要求批量测试参数组合并比较结果
- 用户要求把"复制蓝本→改参数→跑仿真→读结果→记录日志"串成闭环
- 用户要求在 `tasks/task_xxx/runs/run_xxx/` 结构下开展一次正式优化任务
- 用户已经给出了 `task.json`、`config.json` 或明确的 run 目录，希望直接开始执行

当任务满足以下条件时，也建议主动切换到这个 Skill：

- 需要反复运行 CST 仿真，而不是只读一次结果
- 需要记录卡点、基线值、运行摘要
- 需要把结果稳定落到 `summary.md`、`status.json`、`logs/`、`exports/`

以下情况不要优先触发本 Skill：

- 只是打开/保存/关闭工程，不涉及优化闭环
- 只是读取现有结果，不需要改参数和重跑仿真
- 只是做几何建模，不涉及结果评估

## 目标

这个 Skill 用于执行 CST 参数化优化任务的最小闭环。

当前已覆盖内容：
- 任务输入
- 执行流程
- 结果读取路径
- 日志与卡点记录规范
- 当前已验证可用的稳定链路
- 单参数扫描模板
- 小步长扰动策略
- session 污染预防
- save_project 不稳定的回退方案

后续再根据真实测试继续补充：
- 评分函数
- 不同目标的专用流程
- 更多异常分支处理

## 适用场景

- 目标是优化 `S11`、`VSWR`、`Z/Y Matrix` 或远场指标
- 参考工程必须先复制成工作副本再操作
- 需要通过 MCP tools 驱动完整仿真闭环
- 需要把测试结论、卡点和基线值落到 `run_xxx` 目录

## 不适用场景

- 只做几何建模，不跑仿真
- 只读已有结果，不做参数调整
- 直接修改 `ref/`、`ref_model/` 或其他蓝本目录

## 输入

执行前至少应明确以下信息：

- `task_id`
- `run_id`
- 蓝本工程路径 `source_project`
- 工作副本路径 `working_project`
- 优化目标，例如：`Improve S11 matching near 10 GHz`
- 频率范围，例如：`9-11 GHz`
- 目标指标，例如：`S11 at 10 GHz`
- 可调参数范围

推荐从以下文件读取上下文：
- `tasks/task_xxx/task.json`
- `tasks/task_xxx/runs/run_xxx/config.json`
- `tasks/task_xxx/runs/run_xxx/status.json`
- `tasks/task_xxx/notes.md`

## 输出

至少产出以下内容：

- 工作副本工程：`runs/run_xxx/projects/working.cst`
- 导出的结果文件：放入 `runs/run_xxx/exports/`
- 运行状态：写入 `runs/run_xxx/status.json`
- 运行摘要：写入 `runs/run_xxx/summary.md`
- 卡点与诊断：写入 `runs/run_xxx/logs/`

## 强制规则

### 1. 蓝本只读

- 禁止直接修改 `ref/`、`ref_model/`、`prototype_optimizer/data/workspaces/*/projects/source/`
- 每次任务必须先复制出工作副本
- 复制时必须完整复制 `.cst` 文件和同名目录

### 2. 目录规范

- run 目录统一使用：`tasks/task_xxx_slug/runs/run_xxx/`
- `projects/` 只放工程副本与其同名目录
- `exports/` 只放导出结果
- `logs/` 只放日志、报错、卡点记录
- `analysis/` 只放分析结论和中间结果
- `summary.md` 记录结论摘要
- `status.json` 记录当前状态

### 3. 仿真与进程管理

- 优先使用异步仿真链路，不默认使用同步 `start_simulation`
- 仿真结束后必须尝试 `save_project()`
- `save_project` 如果失败，不要慌：仿真结果实际可能已写入工程。此时 `quit_cst` 后重开工程验证 run_id 是否增长即可
- `results` 层在读新结果前必须关闭再重开
- 任务完成后必须关闭项目并退出本次相关的 CST 会话
- 不主动强杀与当前任务无关的 CST 进程

### 4. 远场导出

- 远场导出放在流程最后
- 导出前优先关闭 `results` 上下文，避免文件锁
- 导出后不要再保存工程，避免项目损坏

### 5. 优化循环中禁止 export_s_parameter（关键）

- **在参数扫描 / 优化迭代循环中，禁止调用 `export_s_parameter`**
- 原因：`export_s_parameter` 会改变当前激活的 run 上下文或写 history，导致后续 `get_1d_result` 读到旧 run 数据，表现为"参数改了但数据与上一轮完全一致"
- **正确做法**：整个优化循环只用 `list_run_ids` + `get_parameter_combination` + `get_1d_result(run_id=最新run_id)` 读取结果
- **基线导出**（如果需要）必须在**独立短会话**中完成：导出后立即关闭项目不保存，然后开全新会话继续优化
- 如果某个 run 已被 `export_s_parameter` 污染，应创建新的 clean run 重新开始

### 6. run 被污染后的恢复

- 如果发现结果数据与参数变化不对应（疑似 session 污染），不要继续在当前 run 上操作
- 应关闭当前项目 → 退出 CST → 从蓝本复制全新工作副本 → 创建新 run → 重新开始
- 在 `status.json` 中标记旧 run 为 `contaminated`，在 `logs/` 中记录原因

## 最小稳定工作流

这是当前项目中已验证可用的最小闭环。

### Phase 1：准备

1. 读取 task/run 配置
2. 检查当前任务相关的 CST 窗口是否已关闭
3. 从蓝本完整复制到工作副本
4. 更新 `status.json`，进入运行态

### Phase 2：打开工程

1. `cst-modeler.open_project(working.cst)`
2. `cst-results.open_project(working.cst, allow_interactive=true)`
3. 列参数、确认工程上下文

### Phase 3：应用参数

1. 修改一个或多个参数
2. 如有需要，修改频率范围
3. 记录本轮参数组合

### Phase 4：运行仿真

推荐流程：

1. `cst-modeler.start_simulation_async`
2. 轮询 `cst-modeler.is_simulation_running`
3. 等待直到返回 `running=false`
4. 调用 `cst-modeler.save_project`

说明：
- 当前工程实测中，同步 `start_simulation` 容易超时
- 异步 + 轮询更稳

save_project 失败的处理：
- 如果 `save_project` 返回报错，尝试 `quit_cst` 关闭 CST
- 重新 `open_project` 打开工作副本
- 通过 `list_run_ids` 检查 run_id 是否增长来确认结果是否已写入

### Phase 5：刷新结果

1. `cst-results.close_project`
2. `cst-results.open_project(..., allow_interactive=true)`
3. `cst-results.list_result_items`
4. `cst-results.list_run_ids`

说明：
- 不要假设仿真结果会自动出现在旧的 results session 中
- 必须刷新后再读取
- 始终用最新 run_id 读取结果，不要假设 run_id 编号

### Phase 6：读取指标 + 可视化

以 `S11` 为例：

1. `cst-results.list_run_ids` 获取最新 run_id
2. `cst-results.get_parameter_combination(run_id=最新)` 确认参数是否对应当前设置
3. 定位 tree path：`1D Results\S-Parameters\S1,1`
4. 调用 `cst-results.get_1d_result(treepath, run_id=最新)`
5. 在目标频点附近插值取 S11 值
6. **直接生成交互式预览**：`cst-results_plot_project_result(treepath, run_id=最新)`
   - 输出 HTML 路径自动写入 `mcp/plot_previews/project_result_{timestamp}.html`
   - 1D 结果自动生成曲线图，支持实部/虚部、幅值dB、相位切换
   - 2D 结果自动生成热图、等值线、中心切片和3D表面预览

**禁止在优化循环中调用 `export_s_parameter`**（见强制规则 5）

复数 `S11` 转 dB 的规则：

```python
import math

mag = math.hypot(real, imag)
s11_db = 20 * math.log10(max(mag, 1e-15))
```

### Phase 7：记录结果

至少记录：

- 本轮参数组合
- 目标频点指标值
- 是否出现新结果树项目
- 是否出现异常告警
- 运行耗时
- 是否存在卡点

### Phase 8：下一轮迭代

重复 Phase 3~7，每次修改参数后：

1. 确认参数已写入（`list_parameters` 或 `get_parameter_combination`）
2. 跑仿真
3. 刷新结果，用最新 run_id 读取
4. 与上一轮比较，记录趋势

### Phase 9：收尾

1. 关闭 `results` 项目
2. 调用 `cst-modeler_quit_cst` 关闭 CST 进程
3. 更新 `summary.md`
4. 更新 `status.json`（含 best_result）
5. 把卡点写入 `logs/`
6. 如需最终导出 S 参数或远场，开独立短会话完成

### Phase 10：结果展示（可选）

优化流程全部结束后，统一生成结果可视化。

#### 方式一：使用 generate_s11_comparison.py 脚本（推荐）

1. **准备数据文件**：
   对每个 run_id，执行：
   ```
   cst-results.get_1d_result(treepath="1D Results\\S-Parameters\\S1,1", run_id=N)
   ```
   将返回的 JSON（xdata, ydata, parameter_combination）保存为：
   - `runs/run_xxx/exports/s11_run1.json`
   - `runs/run_xxx/exports/s11_run2.json`
   - ...

2. **调用脚本**：
   ```bash
   python "C:\Users\z1376\Documents\CST_MCP\tools\generate_s11_comparison.py" "C:\path\to\exports"
   
   # 可选参数
   --prefix s11_run      # 文件前缀
   --params g,thr       # 显示的参数名
   --title "S11优化对比"
   ```

3. **输出**：`exports/interactive_comparison.html`

#### 方式二：使用 MCP 工具直接生成

```python
cst-results_plot_project_result(
    treepath="1D Results\\S-Parameters\\S1,1",
    run_id=最新run_id,
    page_title="S11 结果"
)
```
输出：`mcp/plot_previews/project_result_{timestamp}.html`

## 参数扫描策略

### 单参数扫描模板

适用于：不明确某参数对目标指标的影响方向和敏感度

1. 固定其他参数为蓝本值
2. 以较大步长（如 ±10% 或 ±1 单位）粗扫 3~5 个点
3. 找到改善方向后缩小步长细扫
4. 记录每个点的结果到 `logs/parameter_scan.md`

示例（ref_0.cst 的 `g` 参数）：
- 蓝本值 g=25 → S11 ≈ -28.69 dB
- g=24 → S11 ≈ -30.73 dB（改善 ~2 dB，方向正确）
- g=23 → S11 回退（过冲）
- 结论：g=24 是该参数的局部最优

### 组合参数微调

适用于：单参数已达局部最优，需要组合调整

1. 先固定最优单参数，对第二个参数做粗扫
2. 找到第二个参数的改善方向后，与第一个参数组合细调
3. 如果组合效果回退，退回上一个已知最优点

示例（ref_0.cst 的 `g` + `thr`）：
- g=24 固定，thr 从 12.5→11.5 → S11 从 ~-31 dB 改善到 -33.79 dB
- g=24, thr=11.5 为当前最佳组合

### 回退策略

- 如果新参数组合导致指标回退超过 2 dB，立即退回上一个已知最优点
- 不要在回退方向继续探索，除非有明确理由
- 回退后尝试其他参数或其他方向

## 当前已验证经验

基于 `task_001_ref_10ghz_match` 的 run_001~run_003 测试，当前已知：

### 1. 仿真链路

- 稳定链路：`start_simulation_async` → `is_simulation_running` 轮询 → `save_project` → `results.close/open`
- 初始看不到 `S11` 时，不一定是结果树 bug。更可能是仿真没有完整结束并落盘
- 即使 `projects/working/SP/` 目录为空，也不代表结果不可用。当前更可靠的验收方式是：结果树是否出现 `1D Results\S-Parameters\S1,1`

### 2. export_s_parameter session 污染（run_002 教训）

- 在参数扫描循环中调用 `export_s_parameter` 会导致后续结果复用旧 run
- 表现：参数改了但 `get_1d_result` 返回数据与上一轮完全一致
- 同时可能伴随 history 报错
- **解决方案**：优化循环中禁用 `export_s_parameter`，只用纯读取链路
- 基线导出在独立会话中完成，导出后立即关闭不保存
- run_002 因此被标记为已污染，run_003 从蓝本重新复制验证了清洁流程

### 3. save_project 不稳定（run_003 经验）

- `save_project` 有时会报错失败，但仿真结果实际已写入工程
- 此时不要重复 save，而是 `quit_cst` 后重开工程
- 通过 `list_run_ids` 检查 run_id 是否增长来确认结果是否存在
- 如果 run_id 已增长，说明结果可用

### 4. 参数敏感度（ref_0.cst）

- `g` 参数：从 25→24 有效（改善 ~2 dB），继续到 23 反而回退
- `thr` 参数：从 12.5→11.5 与 g=24 叠加后改善约 3 dB
- 当前最佳：`g=24, thr=11.5` → 10 GHz S11 ≈ -33.79 dB
- 基线值（蓝本原始参数）：10 GHz S11 ≈ -28.69 dB
- 注意：早期 run_001 记录的基线值 -32.82 dB 不可靠，可能受 session 状态影响

### 5. 风险项

- 端口模式退化告警
- 求解器因达到最大 pulse widths 而停止，而不是稳态完全满足

### 6. results session 管理

- `cst_results_mcp` 使用 `allow_interactive=True` 关联 GUI session
- 仿真结果存在于 modeler 内存，不自动传递给 results
- 正确流程：仿真后 `save_project()` → results 层 `close + reopen` 刷新

## 常见卡点

### 1. 看不到 S 参数结果

排查顺序：

1. 仿真是否真的完成
2. 是否执行了 `save_project()`
3. 是否刷新了 `results` 会话
4. 是否读取了正确的 `run_id`

### 2. 同步仿真超时

处理方式：

1. 改用异步仿真
2. 用轮询判断是否结束
3. 不要把超时直接等同于仿真失败

### 3. 工程复制失败或目录被锁

处理方式：

1. 先关闭当前任务相关的 CST 窗口
2. 再执行复制
3. 不随意清理其他未知会话

### 4. 结果树刷新后仍为空

处理方式：

1. 检查 `Model.log` / `output.txt`
2. 看求解器是否真正结束
3. 看是否有 `Creating parametric 1D results` 之类的完成迹象

### 5. 参数改了但结果没变（session 污染）

排查顺序：

1. 是否在优化循环中调用了 `export_s_parameter`
2. `get_parameter_combination(run_id)` 是否确认参数已更新
3. `list_run_ids` 是否显示新的 run_id
4. 是否需要刷新 results session

处理方式：

1. 停止当前 run，标记为污染
2. 从蓝本重新复制工作副本
3. 创建新 run，在清洁环境下重新开始

### 6. save_project 报错

处理方式：

1. 不要重复 save
2. 尝试 `quit_cst` 关闭 CST
3. 重新 `open_project` 打开工作副本
4. 通过 `list_run_ids` 确认 run_id 是否增长
5. 如果 run_id 增长，结果可用；继续下一轮

## 日志规范

默认使用中文记录。

允许保留英文的部分：
- MCP 工具名
- 结果树路径
- 报错原文
- 文件名和字段名

推荐日志文件：

- `summary.md`
  用于记录本轮结论、基线值、最佳结果、下一步建议

- `status.json`
  用于记录运行状态、最佳结果的参数和指标值

- `config.json`
  用于记录输入参数、工作流配置、目标指标

- `logs/baseline_test_blockers.md`
  用于记录测试卡点、排查过程、复测结果

- `logs/parameter_scan_*.md`
  用于记录参数扫描的逐点结果和趋势分析

- `logs/session_contamination.md`
  用于记录 session 污染的发现过程和恢复措施

## 当前骨架不负责的内容

以下内容后续再填充：

- 自动采样策略（网格搜索 / 贝叶斯优化等）
- 评分函数
- 多目标优化
- 自动生成最终报告
- 远场导出和方向图评分闭环

## 后续补强方向

后续可按测试结果逐步补充：

1. 结果评分和排序逻辑
2. 失败样本自动回退策略（当前为手动回退）
3. 远场导出和方向图评分闭环
4. 多频点联合优化模板
5. 自动参数敏感度分析

## 优化结果可视化

每次优化完成后，应生成交互式 S11 对比网页。

### 生成脚本

脚本位置：`C:\Users\z1376\Documents\CST_MCP\tools\generate_s11_comparison.py`

脚本功能：
1. 读取所有 run 的 S11 数据（通过 MCP 工具 `get_1d_result` 获取）
2. 生成交互式 HTML，包含：
   - 所有 run 的 S11 曲线对比图（频率 vs S11 dB）
   - 动态纵坐标（根据数据最小值自动调整）
   - 频点选择滑块，右侧显示 S11 随 run ID 变化的折线图

### 使用方法

1. 优化完成后，在 Python 中调用脚本：
```python
import subprocess
result = subprocess.run(
    ["python", "C:\\Users\\z1376\\Documents\\CST_MCP\\tools\\generate_s11_comparison.py"],
    capture_output=True, text=True
)
```

2. 或手动运行脚本：
```bash
python "C:\Users\z1376\Documents\CST_MCP\tools\generate_s11_comparison.py"
```

### 输出位置

生成的 HTML 保存在 `runs/run_xxx/exports/s11_interactive_comparison.html`

### 数据文件

脚本从 MCP tool output 目录读取数据：
- `tool_d7fd02ed5001WCWhsu3WOgxDdz` → run 1
- `tool_d7fd02eda001tBFidBN4BRHkcQ` → run 2
- ...

注意：如果优化 run 数量不同，需更新脚本中的 `files` 列表。

### 脚本代码

```python
# 完整代码见 C:\Users\z1376\Documents\CST_MCP\tools\generate_s11_comparison.py
# 主要逻辑：
# 1. 从 tool output 读取 JSON 数据（包含 xdata, ydata, parameter_combination）
# 2. 解析 ydata 中的复数数据（real, imag）
# 3. 生成 Plotly 交互式 HTML
```

## 规则增补（2026-04-13）

### S11 对比页面生成（生产流程）
- 优先使用 MCP 工具：`cst-results.generate_s11_comparison(...)`。
- 输入文件仅使用 `get_1d_result(..., export_path="*.json")` 产出的 JSON。
- 不再使用 CSV 作为 S11 对比输入；发现 CSV 输入应直接报错并中止本步。

### 脚本定位调整
- `tools/generate_s11_comparison.py` 仅用于本地调试/历史兼容。
- 正式任务编排、自动化流程、交付结果一律走 MCP 工具链。
