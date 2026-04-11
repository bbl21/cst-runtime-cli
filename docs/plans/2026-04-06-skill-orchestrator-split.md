# Skill vs Orchestrator 职责重构计划

**日期**: 2026-04-06  
**状态**: 已更新

---

## 背景

经过架构对比和真实仿真测试，发现 Skill 与 prototype_optimizer 存在大量功能重叠：

| 功能 | Skill | prototype_optimizer | 决策 |
|------|-------|-------------------|------|
| 采样 | `scripts/sampler.py` | `core/sampler.py` | prototype_optimizer 复用 Skill |
| 评估 | `scripts/evaluator.py` | `core/evaluator.py` | prototype_optimizer 复用 Skill |
| 评分 | `scripts/scorer.py` | `core/scorer.py` | prototype_optimizer 复用 Skill |
| 仿真执行 | SKILL.md 流程 | `CSTAdapter` | **废弃 CSTAdapter** |

---

## 目标

清晰划分 Skill 和 prototype_optimizer 的边界：
- **Skill**：负责 LLM 执行仿真的流程和工具
- **prototype_optimizer**：负责人类用户的 UI、历史管理、报告

---

## 重构方案

### Skill 层（cst-antenna-optimizer）

**职责**：
- 定义优化工作流的流程文档（SKILL.md）
- 提供可拼装的工具函数
- 记录参数敏感度经验和异常处理

**目录结构**：
```
cst-antenna-optimizer/
├── SKILL.md                    # 流程文档（Human-readable）
└── scripts/
    ├── sampler.py              # 参数采样工具
    ├── evaluator.py            # 指标计算工具
    └── scorer.py               # 评分工具
```

**SKILL.md 应包含**：
1. 仿真流程（11 步，双 COM Session 注意事项）
2. 参数敏感度经验
3. 搜索策略建议（LLM 决策参考）
4. 边界条件和常见错误

**不包含**：
- `optimizer_loop.py`（废弃，脚本反而限制灵活性）

---

### prototype_optimizer 层

**职责**：
- Streamlit UI（人类用户交互）
- SQLite 历史管理
- HTML 报告生成
- RunWorkspace 目录结构

**应移除**：
- `core/evaluator.py` → 改为 import from Skill
- `core/scorer.py` → 改为 import from Skill
- `core/sampler.py` → 改为 import from Skill
- `adapters/cst_adapter.py` → **废弃**，仿真委托给 Skill

**保留**：
- `app.py`：Streamlit UI
- `storage/`：SQLite 持久化
- `core/run_workspace.py`：目录结构管理
- `core/report_generator.py`：报告生成

---

## 关键约束

- **蓝本只读**：所有修改必须复制到 workspace 再操作
- **进程管理**：仿真后必须关闭 CST，避免内存泄漏
- **远场导出时机**：必须放在流程最后，导出后不保存

---

## LLM 使用方式（无需运行脚本）

```
# 直接按 SKILL.md 流程执行：

1. 蓝本复制（shell 命令）
2. modeler.open_project()
3. results.open_project(allow_interactive=True)
4. 循环:
   - 采样参数
   - change_parameter()
   - start_simulation()
   - save_project()
   - results.refresh()
   - get_1d_result()
   - export_farfield()
5. 评分
6. quit_cst()
```

---

## 实施步骤

### Phase 1: 废弃 optimizer_loop.py
- [ ] 删除 `scripts/optimizer_loop.py` 或标注为参考实现

### Phase 2: Skill 文档完善
- [ ] 完善 SKILL.md 流程文档
- [ ] 添加参数敏感度经验
- [ ] 添加搜索策略建议

### Phase 3: prototype_optimizer 重构
- [ ] `core/evaluator.py` → import from Skill
- [ ] `core/scorer.py` → import from Skill
- [ ] `core/sampler.py` → import from Skill
- [ ] 删除 `adapters/cst_adapter.py`

### Phase 4: UI 改造
- [ ] 设计 Skill 执行层 IPC 机制
- [ ] Streamlit UI 启动任务后委托 Skill 执行

---

## 预期收益

- LLM 在优化探索时有更大自由度
- 消除功能重叠，减少维护成本
- prototype_optimizer 专注于 UI 和历史管理
