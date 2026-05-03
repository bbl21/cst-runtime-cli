# 阶段 B 主生产链收口记录

> 本文档是阶段 B 交付物，用于说明正式主链的实际节点、旁路降级结果和后续验收要求。  
> 它不是规则源；规则与红线仍以 `AGENTS.md` 为准，执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 一句话结论

阶段 B 的主链收口目标定义为：

**所有正式生产任务都从 `tasks/task_xxx_slug/` 出发，经 `cst-modeler.prepare_new_run(...)` 创建 run，再由 GUI 可见 MCP tool call 完成执行、结果读取、导出、对比和状态登记。**

## 正式主链节点

| 阶段 | 正式节点 | 责任归属 | 输出位置 |
| --- | --- | --- | --- |
| run 创建 | `cst-modeler.prepare_new_run(task_path=...)` | MCP modeler | `runs/run_xxx/{projects,exports,logs,stages,analysis}` |
| run 上下文读取 | `cst-modeler.get_run_context(task_path=..., run_id=...)` | MCP modeler | 返回 `working_project`、`exports_dir`、`logs_dir`、`analysis_dir` |
| 建模/参数/仿真 | `cst-modeler.open_project`、参数修改、`start_simulation_async`、`is_simulation_running`、`close_project(save=False)` | MCP modeler | 当前 run 的 `projects/working.cst` |
| results 刷新 | `cst-results.close_project` -> `cst-results.open_project(..., allow_interactive=true)` | MCP results | results session 最新上下文 |
| 结果读取 | `cst-results.list_run_ids`、`get_parameter_combination`、`get_1d_result(export_path=*.json)` | MCP results | 当前 run 的 `exports/*.json` |
| 远场/增益读取 | `export_farfield_fresh_session` 或 `read_realized_gain_grid_fresh_session` | MCP results | 当前 run 的 `exports/` 或 `analysis/` |
| S11 对比 | `cst-results.generate_s11_comparison(file_paths=[...json...])` | MCP results | 当前 run 的 `exports/*.html` |
| 阶段记录 | `cst-modeler.record_run_stage(...)` | MCP modeler | 当前 run 的 `stages/*.json` 与 `logs/production_chain.md` |
| 状态落盘 | `cst-modeler.update_run_status(...)` | MCP modeler | 当前 run 的 `status.json` |
| 收尾 | `cst-results.close_project` -> `cst-modeler.close_project(save=False)` -> `cst-modeler.quit_cst(project_path=...)` | MCP modeler/results | 无残留锁文件，必要时记录非阻塞残留 |

## 旁路处理结果

| 路径 | 阶段 B 判定 | 处理方式 |
| --- | --- | --- |
| `archive/tools-legacy-20260421/e2e_clean.py` | 已归档旧旁路 | 不再作为生产入口 |
| `archive/tools-legacy-20260421/e2e_final.py` | 已归档旧旁路 | 不再作为生产入口 |
| `archive/tools-legacy-20260421/diag_refresh.py` | 已归档调试辅助 | 不再承担默认 results 刷新职责 |
| `archive/tools-legacy-20260421/explore_results.py` | 已归档调试辅助 | 不再承担默认结果读取职责 |
| `archive/tools-legacy-20260421/plot_farfield.py` | 已归档调试辅助 | 不再承担默认远场展示职责 |
| `archive/tools-legacy-20260421/generate_s11_comparison.py` | 已归档历史兼容 | 生产对比只走 `cst-results.generate_s11_comparison(...)` 或 runtime `generate-s11-comparison` |
| `tools/call_local_mcp_tool.py` | 开发期定位 | 不能作为生产验收依据 |
| `prototype_optimizer/core/orchestrator.py` | 原型外围 | 不纳入本周正式主链 |
| `tmp/` | 非生产路径 | 只允许临时测试和排障，不允许作为默认输入或输出 |

## 已完成收口动作

- `mcp/advanced_mcp.py` 新增 `get_run_context(...)`，正式返回当前 run 的标准路径，避免后续步骤依赖对话记忆猜路径。
- `mcp/advanced_mcp.py` 新增 `record_run_stage(...)`，统一写入 `stages/` 和 `logs/production_chain.md`。
- `mcp/advanced_mcp.py` 新增 `update_run_status(...)`，统一更新 `status.json`、`best_result`、`output_files`、错误状态和完成时间。
- `skills/cst-simulation-optimization/SKILL.md` 已补入阶段 B 正式主链，明确状态落盘和 S11 对比不得再依赖历史脚本。
- 仓库内 Skill 已作为正式版本更新，并已同步到项目 `.codex` 副本与用户级 `.codex` 生效副本。

## MCP 验证结果

阶段 B 已完成真实 MCP 验收：

- `tools/list` 已确认 `get_run_context`、`record_run_stage`、`update_run_status` 注册在 `cst-modeler` MCP server 中。
- `tools/call get_run_context(...)` 已在 `tmp/phase_b_validation_task` 上返回标准 run 路径、配置和状态结构。
- `tools/call record_run_stage(...)` 已写入 `stages/phase_b_mcp_validation.json` 与 `logs/production_chain.md`。
- `tools/call update_run_status(...)` 已合并 `output_files`，并保持 `status.json` 既有字段可读。
- 验证过程中发现 `latest` 文件若带 UTF-8 BOM 会污染 `run_id`，已在 `mcp/advanced_mcp.py` 中用 `utf-8-sig` 读取并清理 BOM。

阶段 B 状态：`validated`。可以进入阶段 C：打通 MCP、Skill、知识系统、计划系统的职责协同。
