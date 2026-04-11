# CST Antenna Optimizer Skill 优化计划

**日期**: 2026-04-06  
**状态**: 待执行

---

## 背景：架构分层认识

经过实践验证，我们对优化工作的两类性质有了更清晰的认识：

| 工作类型 | 特征 | 适合方式 |
|---------|------|---------|
| **优化探索** | 灵活、需判断、可能偏离预期 | Skill 规定关键步骤 + LLM 自主决策 |
| **流程化执行** | 重复、可预期、步骤固定 | Orchestrator 自动化编排 |

### 核心原则

- **LLM 适合**：参数空间搜索策略、步长选择、敏感度判断、异常处理决策
- **Skill 适合**：规定关键检查点、边界条件、注意事项（蓝本只读、远场导出时机等）
- **Orchestrator 适合**：无聊的重复劳动（采样循环、结果入库、报告生成）

### 架构决策

```
┌─────────────────────────────────────────────────────────┐
│  Skill (cst-antenna-optimizer)                          │
│  - 规定关键步骤和边界                                    │
│  - LLM 按需调用工具、自主决策搜索策略                     │
│  - scripts/ 提供可拼装工具，非硬编码循环                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Orchestrator (prototype_optimizer)                    │
│  - 确定性的采样循环                                      │
│  - 结果入库和历史管理                                    │
│  - 报告生成                                              │
│  - 不封装搜索策略（那是 LLM 的活）                        │
└─────────────────────────────────────────────────────────┘
```

---

## Step 1: 修复 SKILL.md 工具名（文档修正）

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\SKILL.md`

| 当前文档 | 修正为 | 说明 |
|----------|--------|------|
| `cst_interface` | `cst-modeler` | MCP 建模服务工具前缀 |
| `cst_results_interface` | `cst-results` | MCP 结果服务工具前缀 |

**验证方法**: 文档工具名与 MCP 服务实际工具前缀一致

---

## Step 2: 修复 `sim_ok` 逻辑（轮询仿真状态）

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\scripts\optimizer_loop.py`

**问题位置**: `_run_single_sample_real` 函数，`start_simulation()` 后立即设置 `sim_ok=True`

**修复方案**:
- `start_simulation()` 启动仿真后，循环调用 `is_simulation_running()` 轮询
- 仿真真正结束时（`running=False`）才标记 `sim_ok=True`
- 添加超时机制（建议 600 秒）
- `sim_ok` 判断逻辑：只有当仿真状态变为"未运行"且 `start_simulation()` 初始返回成功时，才认为仿真成功

**验证方法**:
1. 手动执行单个样本仿真
2. 确认 `is_simulation_running()` 在仿真期间返回 `True`
3. 仿真结束后返回 `False`
4. `sim_ok` 以实际运行状态为准

---

## Step 3: `dry_run` 默认值改为 `False`

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\scripts\optimizer_loop.py`

**问题位置**: `SessionConfig` dataclass，L55

**修复**: `dry_run: bool = True` → `dry_run: bool = False`

**验证方法**: 导入模块检查 `SessionConfig.__dataclass_fields__['dry_run'].default` 返回 `False`

---

## Step 4: 移除未使用字段 `s11_run_id`

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\scripts\optimizer_loop.py`

**问题位置**: `SessionConfig` dataclass，`s11_run_id: int = 1` 定义但从未被使用

**修复**: 删除该字段定义及 `main()` 中对应的 `raw.get("s11_run_id", 1)` 解析

**验证方法**: 修改后代码仍正常运行，单样本流程完成

---

## Step 5: `close(save=False)` 显式调用

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\scripts\optimizer_loop.py`

**问题位置**: `_run_single_sample_real` 末尾，远场导出后未显式 `close(save=False)`

**修复**: 在 `finally` 块或导出后，显式调用 `advanced_mcp.close_project()` 不保存

**验证方法**: 导出后项目文件未被修改（对比导出前后时间戳或 hash）

---

## Step 6: 强化 SKILL.md 中的参数调优经验

**目标文件**: `C:\Users\z1376\.config\opencode\skills\cst-antenna-optimizer\SKILL.md`

**新增内容**:
- 四脊喇叭参数敏感度极高，大幅调整会导致模型失效
- 推荐步长：±1%~±2%以内
- 已知敏感参数：C1, C2, x1, z2
- 异常处理：Frequency range error、Port inhomogeneous mesh error 等

**验证方法**: SKILL.md 包含参数调优经验和异常处理指南

---

## 执行原则

- **每步修复后测试验证，再进行下一步**
- 如测试失败，立即回滚该修改
- 优先保证现有功能不被破坏

---

## 依赖关系

```
Step 1 (文档) ──┐
                ├── 无依赖，可任意顺序
Step 3 (dry_run 默认值) ──┤
                          ├── Step 4 可在任意位置
Step 5 (close) ─────────┘
```

---

## 待补充：Skill vs Orchestrator 职责重构（待规划）

详见 `plans/2026-04-06-skill-orchestrator-split.md`
