# 2026-04-23 Trae ref_0 CLI 低上下文验证记录

> 本文记录 Trae 仅凭 Skill 和 `cst_runtime` CLI 完成 ref_0 S11 工作流验证的结果。  
> 规则仍以 `AGENTS.md` 为准；CLI/runtime 执行流程以 `skills/cst-runtime-cli-optimization/SKILL.md` 为准。

## 结论

- Trae 低上下文端到端验证已完成。
- 验证任务：`tasks/task_009_ref0_cli_low_context_validation`
- 验证 run：`run_001`
- run 状态：`validated`
- 完成时间：`2026-04-23T16:24:00+08:00`
- 参考模型只读路径：`<repo>/ref/ref_model/ref_0/ref_0.cst`
- 工作副本：`<repo>/tasks/task_009_ref0_cli_low_context_validation/runs/run_001/projects/working.cst`

## 验证内容

- 使用 `cst_runtime` CLI 创建标准 run 工作区。
- 打开工作副本并校验工程身份。
- 读取参数，确认 `g` 与 `thr` 存在。
- 将 `g` 调整为 `24.5`。
- 启动一次真实仿真并轮询完成。
- 关闭工程并确认当前 run 无 `.lok`。
- 通过 results CLI 读取 S11 run_id 与 1D 结果。
- 导出 S11 JSON 并生成 HTML 对比页。

## 输出产物

- `exports/result_1d_run0_20260423_151103.json`
- `exports/result_1d_run1_20260423_151040.json`
- `exports/result_1d_run2_20260423_161752.json`
- `exports/s11_comparison.html`

## 指标记录

- `run2` 最小 S11：`-63.59137947801863 dB`
- `run2` 最佳频点：`10.47599983215332 GHz`
- `run0` 最小 S11：`-70.18561298989317 dB`
- `run0` 最佳频点：`8.715999603271484 GHz`

## 阶段判断

本次验证关闭了“第三方 coding agent 低上下文端到端验证”缺口，说明 Trae 可以按 Skill 和 CLI 工具完成 ref_0 S11 闭环。

本文写成时，P0 尚有一个开放门控：`fresh-session` 真实 CST 远场导出/读取生产验证。该缺口已在后续 `ref_0` 10 GHz 验证中关闭，见 [`validations/2026-04-23-ref0-fresh-session-farfield-validation.md`](2026-04-23-ref0-fresh-session-farfield-validation.md)。

## 收尾残留

`cleanup-cst-processes` 按白名单执行并写入 `logs/tool_calls.jsonl`。当前 run 锁文件为空，但存在 `Access is denied` 非阻塞残留记录：

- PID `7148`：`CSTDCMainController_AMD64`
- PID `7156`：`CSTDCSolverServer_AMD64`
- 早期一次记录还包含 PID `33760`：`cstd`

这些进程没有被声明为已杀掉。

## 后续第一任务

后续进入门控复盘：确认是进入 `P1` 优化指导原型，还是先处理 Trae 反馈中的 P0 后加固项。
