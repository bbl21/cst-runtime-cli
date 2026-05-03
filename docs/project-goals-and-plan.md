# 项目目标与计划

> 本文档维护 CST_MCP 的项目定位、阶段目标和当前主攻方向。  
> 它不是规则源；全局规则与红线以 `AGENTS.md` 为准，执行流程以对应 Skill 为准。  
> 2026-05-02 清洗前长版已归档到 [`archive/project-goals-and-plan-pre-cleanup-2026-05-02.md`](./archive/project-goals-and-plan-pre-cleanup-2026-05-02.md)。

## 1. 项目定位

CST_MCP 当前定位为：

**一个面向 LLM 主导、人工监督的 CST 参数化优化执行系统。**

当前重点不是替代 CST GUI，也不是全自动生成 3D 模型，而是把已有参数化 CST 工程的仿真、结果读取、导出、对比、状态审计和复现流程收口为一条稳定主链。

长期方向是逐步形成“需求理解 -> 参数化工程准备 -> 仿真优化 -> 结果展示 -> 经验回收”的工程闭环；当前阶段只承诺做好参数化 CST 模型上的稳定执行底座。

## 2. 核心分工

### 2.1 LLM + Skill

LLM + Skill 负责需要判断的部分：

- 优化目标理解与拆解。
- 参数探索方向选择。
- 异常现象分析。
- 结果解释。
- 是否继续、回退、重试或询问用户的决策。
- 经验总结与知识分流。

### 2.2 程序 / MCP / runtime

程序、MCP 和 `cst_runtime/` 负责稳定重复部分：

- run 创建与状态落盘。
- 项目身份校验。
- 参数读写。
- 仿真启动与等待。
- results 刷新。
- S11 / 远场结果读取。
- 指标计算、导出、对比和预览。
- 结构化错误返回。

### 2.3 当前链路边界

- MCP + Skill 仍是正式生产基准。
- `cst_runtime/` 是共享 runtime/CLI 能力层，不是第二条独立生产链。
- `prototype_optimizer/` 不再作为主线或默认迁移包依赖。
- 参考工程只读，所有实验必须落在标准 `tasks/.../runs/...` 工作副本中。

## 3. 阶段状态

### 3.1 P0 基础底座

状态：`validated`

P0 已完成：

- 唯一正式入口与旁路冻结。
- 主生产链收口。
- MCP、Skill、知识系统、计划系统职责划分。
- CLI-first runtime 能力层门控。
- 低上下文 agent 端到端验证。
- ref_0 10 GHz fresh-session 真实 CST 远场 Realized Gain dBi 验证。

当前状态摘要见 [`core/project-current-status.md`](./core/project-current-status.md)。

### 3.2 下一阶段候选主线

状态：`not_started`

下一阶段候选主线是：

**把 ref_2 多频 realized-gain flatness 优化整理成正式、可复现、约束清晰的工程优化闭环。**

进入正式 run 前必须先完成任务定义：

- 固定任务对象、频点、指标和约束。
- 固定 baseline 和候选对比口径。
- 固定 S11 与 Realized Gain dBi 证据链。
- 固定仿真预算和停止条件。
- 固定 run 产物和验收标准。

当前优先清单见 [`current-priority-checklist.md`](./current-priority-checklist.md)。

## 4. 当前主攻方向

当前阶段只集中解决一件事：

**让已有 CST 参数化优化流程保持稳定、可迁移、可审计、可低上下文复现，并在此基础上推进 ref_2 正式优化闭环。**

当前优先：

- 保持正式生产链稳定。
- 保持标准 run 产物完整。
- 保持 results fresh-session 读取一致性。
- 保持真实 gain/dBi 证据链。
- 把 ref_2 优化任务的指标、约束和停止条件写清楚。

当前暂缓：

- 全自动 3D 建模。
- 通用 CST GUI 替代。
- 多器件类型全覆盖。
- 大规模 UI 重构。
- 未定义清楚任务边界的参数扫描扩张。

## 5. 中期目标

中期目标是让系统能够稳定承担多个真实 CST 参数化优化任务，而不是只完成一次演示。

验收标准：

- 正式执行链稳定统一，没有多条并行旧链路。
- 关键能力具备明确输入、输出、错误处理和状态管理。
- 能连续完成多轮真实优化任务，并保留完整审计产物。
- 结果读取使用真实指标链路，避免旧缓存、旧 run 和错误单位污染。
- 新经验能正确分流到规则、Skill、状态文档、专题文档或 run 记录。

## 6. 长期方向

长期方向是从单一参数化模型优化，逐步扩展为更完整的电磁仿真工程闭环。

长期边界：

- 不承诺当前阶段实现全自动 3D 建模。
- 不做通用 CST GUI 替代品。
- 不做覆盖所有仿真对象和全部工作流的大平台。
- 不为了扩展功能而破坏当前执行底座的可维护性。

## 7. 维护规则

- 当当前主攻方向改变时，必须同步更新本文档和 [`current-priority-checklist.md`](./current-priority-checklist.md)。
- 当项目状态、已验证能力或下一步工程主线改变时，必须同步更新 [`core/project-current-status.md`](./core/project-current-status.md)。
- 已完成的阶段过程不应继续堆在本文档；应转入验证记录、handoff、archive 或 run 产物。
- 若内容属于规则或红线，应写入 `AGENTS.md`；若内容属于执行步骤，应写入对应 Skill。
