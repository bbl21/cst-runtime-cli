# 项目现状

> 本文档维护 CST_MCP 当前阶段事实、已验证成果、主要边界和下一步工程主线。  
> 本文档不是规则源；规则与红线以 `AGENTS.md` 为准，阶段计划以 `docs/project-goals-and-plan.md` 和 `docs/current-priority-checklist.md` 为准。

## 1. 当前定位

CST_MCP 当前是一个面向 LLM 主导、人工监督的 CST 参数化优化执行系统。项目重点不是替代 CST GUI，也不是全自动生成 3D 模型，而是把已有参数化 CST 模型的仿真、结果读取、导出、对比、记录和复现流程收口到一条稳定主链。

当前正式生产基准仍是 MCP + Skill 链路；`cst_runtime/` 是共享 runtime/CLI 能力层，用于降低低上下文 agent 和批处理场景的调用难度，但不作为第二条独立生产链。`prototype_optimizer/` 已退出默认主线，不再作为项目事实来源或默认迁移包依赖。

## 2. 当前阶段状态

- P0 基础目标已经标记为 `validated`。
- 正式生产链已经完成阶段 A/B/C/D 收口：入口定义、主链整合、四类系统协同、低上下文验证和 fresh-session 远场验证均已有记录。
- P1 优化指导功能原型尚未启动；当前不应把优化指导、全自动建模或大规模 UI 重构并入默认主线。
- 当前任务选择仍应优先服务稳定生产链、低上下文可复现执行、结果读取一致性和标准 run 产物完整落盘。

## 3. 已验证能力

### 3.1 标准任务与 run 结构

当前标准任务目录为：

```text
tasks/task_xxx_slug/runs/run_xxx/
```

标准 run 结构为：

```text
run_xxx/{projects,exports,logs,stages,analysis}
```

关键约束已经固化：

- 参考工程只读，必须创建独立工作副本。
- `projects/` 放当前 run 的工程副本。
- `exports/` 放 S 参数、远场、HTML 预览等外部结果。
- `logs/`、`stages/`、`analysis/` 分别承载审计日志、阶段输出和分析结论。
- 每个 run 使用 `summary.md`、`status.json`、`config.json` 记录摘要、状态和配置。

### 3.2 低上下文 CLI 验证

验证记录：`docs/validations/2026-04-23-trae-ref0-cli-low-context-validation.md`

已验证事实：

- Trae 仅凭 Skill 和 `cst_runtime` CLI 完成 ref_0 S11 工作流。
- 验证任务：`tasks/task_009_ref0_cli_low_context_validation`
- 验证 run：`run_001`
- run 状态：`validated`
- 工作流覆盖：创建 run、打开工作副本、校验工程身份、读取参数、修改参数、启动真实仿真、等待完成、读取 results、导出 S11 JSON、生成 S11 HTML 对比页。
- 指标记录中，`run2` 最小 S11 为 `-63.59137947801863 dB`，最佳频点为 `10.47599983215332 GHz`。

该验证说明：低上下文 agent 可以按 Skill + CLI 工具完成 ref_0 S11 闭环，不依赖当前对话记忆。

### 3.3 fresh-session 远场验证

验证记录：`docs/validations/2026-04-23-ref0-fresh-session-farfield-validation.md`

已验证事实：

- 验证任务：`tasks/task_010_ref0_fresh_session_farfield_validation`
- 验证 run：`run_001`
- run 状态：`validated`
- 参考模型：`ref/ref_model/ref_0/ref_0.cst`
- 远场名称：`farfield (f=10) [1]`
- 频率：`10.0 GHz`
- 读取量：`Realized Gain`
- 单位：`dBi`
- 网格：full sphere，theta `0..180 deg`，phi `0..355 deg`，步进 `5 deg`
- 样本数：`2664`
- 峰值 realized gain：`14.144726099856493 dBi`
- boresight realized gain：`14.144726099856493 dBi`

本次验证使用真实 `Realized Gain` dBi 数据，TXT 表头为 `Abs(Realized Gain)[dBi]`，没有使用 `Abs(E)` 作为增益证据。

### 3.4 runtime/CLI 能力

当前 `cst_runtime/` 已具备低上下文 agent 使用所需的基础能力：

- `doctor`
- `usage-guide`
- `list-tools`
- `describe-tool`
- `args-template`
- `list-pipelines`
- `describe-pipeline`
- `pipeline-template`
- 结构化 JSON 错误出口
- 显式参数优先于 stdin 的参数合并规则
- `--args-file` / `--args-json` / `--args-stdin`
- `wait-simulation`
- S11 JSON 导出与 HTML 对比
- 远场导出、读取、解析和 HTML 预览相关能力

默认低上下文学习顺序为：

```text
doctor -> usage-guide -> list-tools -> list-pipelines -> describe-pipeline -> describe-tool -> args-template
```

## 4. 当前工程边界

### 4.1 正式主线

当前主线仍是把 CST 参数化优化流程保持为稳定、可迁移、可审计、可低上下文复现的执行底座。

优先事项包括：

- 保持 MCP + Skill 正式生产链稳定。
- 保持 `cst_runtime/` 作为共享能力层，而不是第二条生产链。
- 保持标准 `tasks/` / `runs/` 产物完整落盘。
- 保持 results fresh-session 读取流程，避免旧 run、旧缓存和错误 session。
- 保持真实 gain/dBi 证据链，禁止把 `Abs(E)` 当成绝对增益。

### 4.2 当前不做

当前不默认推进：

- 全自动 3D 建模。
- 通用 CST GUI 替代。
- 多器件类型全覆盖。
- 大规模 UI 重构。
- 围绕 `prototype_optimizer` 增加新功能。
- 将临时脚本或旧 `tools/` 路径重新提升为生产入口。
- 在 P1 明确启动前推进优化指导功能原型。

## 5. 当前优化任务事实

### 5.1 ref_0

ref_0 是当前稳定参考蓝本之一：

- 路径：`ref/ref_model/ref_0/`
- S 参数频段：`2-18 GHz`
- 远场关注点：`10 GHz`
- 已完成低上下文 S11 闭环验证。
- 已完成 10 GHz Realized Gain fresh-session 远场验证。

### 5.2 ref_2

ref_2 当前主要用于多频 realized-gain flatness 优化探索。

任务：`tasks/task_008_ref2_multifreq_realgain_optimization`

baseline run：`run_001`

- 状态：`baseline_exported`
- 目标：建立 ref_2 port1 在 4/8/13/18 GHz 的 realized-gain flatness baseline。
- baseline 最差 flatness：`18.423 dB`

当前较好候选：`run_009`

- worst_flatness_db：`14.107`
- average_flatness_db：`10.237`
- worst_target_flatness_8_13_18_db：`14.107`
- average_target_flatness_8_13_18_db：`12.154`
- worst_boresight_gain_delta_dbi vs baseline：`-2.307`
- worst_s11_db：`-8.341`
- 记录说明：高频平坦度改善伴随低频代价，尤其 4 GHz boresight gain 下滑；18 GHz 峰值继续偏离 boresight。

该任务目前更适合作为后续正式优化闭环的候选基础，不应直接当作已完成的最终优化交付。

## 6. 已知风险与注意事项

- 早期部分 13 GHz 平坦度探索使用过 `Abs(E)` 场强代理量；这些结果不能作为 dBi 增益证据。
- 远场正式证据必须优先使用 `Realized Gain`、`Gain` 或 `Directivity`。
- 5 deg full-sphere 网格适合链路验证；若任务需要精细方向图指标，应按指标需求选择更合适角分辨率或角窗导出。
- results 读取必须注意 modeler/results session 分离，不能假设仿真后 results 侧立刻看到最新 run。
- 仿真、导出、关闭、清理流程必须继续遵守 `AGENTS.md` 中关于保存、关闭、锁文件和 CST 残留进程的规则。

## 7. 下一步工程主线建议

当前不应四面出击。下一步建议只围绕一个方向推进：

**把 ref_2 多频 realized-gain flatness 优化整理成一个正式、可复现、约束清晰的工程优化闭环。**

建议先固定：

- 任务对象：ref_2 port1。
- 频点：4/8/13/18 GHz。
- 主指标：theta <= 15 deg 范围内 realized-gain flatness。
- 约束：S11 阈值、boresight realized gain 下降阈值、仿真预算。
- 证据链：每轮必须读取当前 run 的 S11 JSON 与 Realized Gain dBi 网格。
- 产物：每轮均落入独立 `run_xxx`，不得覆盖已有 run。

第一步不是继续扩大工具，而是把该优化任务的输入、指标、约束、停止条件和验收标准写清楚，然后再启动下一轮正式 run。

## 8. 维护规则

- 当 P0/P1 状态、正式主线、参考蓝本、关键验证结果或当前工程边界发生变化时，应更新本文档。
- 若新增内容属于规则或红线，应写入 `AGENTS.md`；本文档只做状态维护。
- 若新增内容属于执行流程，应写入对应 Skill；本文档只保留状态摘要和入口指引。
- 若新增内容属于一次性 run 细节，应优先写入该 run 的 `summary.md`、`status.json`、`stages/` 或 `analysis/`，本文档只摘录跨任务有用的事实。
