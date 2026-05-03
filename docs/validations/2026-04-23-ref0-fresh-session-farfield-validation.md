# 2026-04-23 ref_0 fresh-session 远场验证记录

> 本文记录 `ref_0` 在 10 GHz 远场结果上的 `cst_runtime` fresh-session 实机验证。  
> 参考工程仍只读；验证产物落在独立 run 工作副本中。

## 结论

- 验证任务：`tasks/task_010_ref0_fresh_session_farfield_validation`
- 验证 run：`run_001`
- run 状态：`validated`
- 完成时间：`2026-04-23T17:34:54+08:00`
- 参考模型：`<repo>/ref/ref_model/ref_0/ref_0.cst`
- 工作副本：`<repo>/tasks/task_010_ref0_fresh_session_farfield_validation/runs/run_001/projects/working.cst`

本次关闭了 P0 剩余门控：fresh-session 真实 CST 远场导出与 Realized Gain dBi 读取均已成功。

## 验证内容

- 从 `ref_0` 只读蓝本创建独立工作副本。
- 确认工作副本结果目录存在 `Result/farfield (f=10)_1.ffm` 与 `Result/farfield (f=10)_1.fme`。
- 使用 `export-farfield-fresh-session` 在 fresh CST GUI session 中打开工作副本。
- 通过 `FarfieldCalculator` 导出 `farfield (f=10) [1]` 的 `Realized Gain` 标量网格。
- 使用 `read-realized-gain-grid-fresh-session` 另起 fresh session 读取真实 `Realized Gain` dBi 网格。
- 使用 `inspect-farfield-ascii` 验证 TXT 网格形状。
- 使用 `plot-farfield-multi` 生成 HTML 预览。
- 收尾时确认工程解锁、run 目录无 `.lok`，并记录 CST 残留进程的 `Access is denied`。

## 指标与网格

- 频率：`10.0 GHz`
- farfield 名称：`farfield (f=10) [1]`
- 数据源：`FarfieldCalculator`
- 数量：`Realized Gain`
- 单位：`dBi`
- 范围：full sphere
- theta：`0..180 deg`，步进 `5 deg`，`37` 点
- phi：`0..355 deg`，步进 `5 deg`，`72` 点
- 样本数：`2664`
- 峰值 realized gain：`14.144726099856493 dBi`
- 峰值方向：theta `0 deg`，phi `0 deg`
- boresight realized gain：`14.144726099856493 dBi`

## 输出产物

- `exports/farfield_10ghz_port1_realized_gain_fullsphere_5deg.txt`
- `exports/farfield_10ghz_port1_realized_gain_fullsphere_5deg.html`
- `analysis/realized_gain_grid_10ghz_port1_fullsphere_5deg.json`
- `stages/export_farfield_fresh_session_output.json`
- `stages/read_realized_gain_grid_fresh_session_output.json`
- `stages/inspect_farfield_ascii_output.json`
- `stages/cleanup_cst_processes_output.json`

TXT 表头为 `Abs(Realized Gain)[dBi]`，本次没有使用 `Abs(E)` 作为增益证据。

## 收尾残留

`cleanup-cst-processes` 按白名单执行。当前 run 锁文件为空，但以下进程返回 `Access is denied`，已记录为非阻塞残留：

- PID `33760`：`cstd`
- PID `7148`：`CSTDCMainController_AMD64`
- PID `7156`：`CSTDCSolverServer_AMD64`

这些进程没有被声明为已杀掉。

## 门控判断

P0 的两个阶段 D 验证缺口已经关闭：

- Trae 低上下文 ref_0 S11 CLI-only 闭环已完成。
- fresh-session 真实 CST 远场导出/读取验证已完成。

因此本轮基础目标可以标记为 `validated`。P1 不自动启动；下一步应先确认是否进入 P1，或先处理 Trae 反馈中的 P0 后加固项。
