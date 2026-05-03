# 项目结构说明

> 本文档提供详细结构说明，不是规则源。  
> 规则和红线以 `AGENTS.md` 为准；执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 顶层目录
- `mcp/`：MCP 服务源码，包含 modeler 与 results
- `cst_runtime/`：共享运行层，承载 run workspace、项目身份辅助、优化闭环运行工具、results/远场读取、审计落盘和包内 CLI adapter
- `prototype_optimizer/`：旧 Streamlit/SQLite 原型外围，当前为归档候选；不再是重点项目，也不是正式生产入口
- `tasks/`：正式任务与 run 产物
- `ref/`、`ref_model/`：参考蓝本与模型资料
- `skills/`：仓库内正式维护的 Skill
- `.codex/`：项目内 Codex 生效副本
- `docs/`：背景说明、经验、计划和历史记录
- `tools/`：项目脚本与辅助工具
- `backup/`：备份目录
- `tmp/`：临时脚本、临时测试和一次性产物
- `dist/`：迁移包输出目录，默认由 `tools/build_portable_bundle.ps1` 生成

## 标准任务目录
推荐结构：

```text
tasks/
  task_xxx_slug/
    task.json
    notes.md
    runs/
      run_xxx/
        config.json
        status.json
        summary.md
        projects/
        exports/
        logs/
        stages/
        analysis/
```

说明：
- `projects/` 放工程副本及其同名目录
- `exports/` 放外部导出物和 HTML 预览
- `logs/` 放日志和报错记录
- `stages/` 放阶段状态与阶段元数据
- `analysis/` 放分析结论与中间结果

## 关键源码位置
- `mcp/advanced_mcp.py`：建模与仿真执行相关 MCP
- `mcp/cst_results_mcp.py`：结果读取、导出和可视化相关 MCP
- `cst_runtime/`：共享 runtime；CLI 入口为 `python -m cst_runtime`，当前已包含 `run_workspace.py`、`project_identity.py`、`audit.py`、`modeler.py`、`results.py`、`farfield.py`、`process_cleanup.py`
- `skills/cst-simulation-optimization/SKILL.md`：正式流程 Skill
- `skills/cst-runtime-cli-optimization/SKILL.md`：CLI/runtime 并行迁移流程 Skill；不替代当前 MCP 稳定链
- `tasks/task_xxx_slug/task.json`：当前正式任务入口的任务上下文
- `prototype_optimizer/app.py`：旧 Streamlit 原型 UI 入口，冻结为 legacy/归档候选，不是当前正式生产入口

## 当前正式生产入口

- 正式任务入口：`tasks/task_xxx_slug/`
- 正式执行起点：`cst-modeler.prepare_new_run(task_path=...)`
- 正式执行主链：`skills/cst-simulation-optimization/SKILL.md` 约束下的 GUI 可见 MCP tool call
- 旁路与冻结范围：见 [`workflow/formal-entry-and-bypass-audit.md`](formal-entry-and-bypass-audit.md)
- 主链收口与状态落盘：见 [`architecture/phase-b-main-chain-consolidation.md`](../architecture/phase-b-main-chain-consolidation.md)
- 系统集成与一键迁移：见 [`architecture/phase-c-system-integration-and-portable-mode.md`](../architecture/phase-c-system-integration-and-portable-mode.md)
- CLI-first 剪枝、runtime 和 adapter 边界：见 [`architecture/cli-architecture-decision.md`](../architecture/cli-architecture-decision.md)
- 第一版 runtime CLI 入口：`python -m cst_runtime list-tools`；复杂入参优先用 `python -m cst_runtime args-template --tool <tool>` 生成模板

## 常用脚本
- `tools/kill_cst.ps1`：按 CST 强杀白名单结束 CST 进程
- `tools/close_cst_by_name.ps1`：按项目名关闭 CST 窗口
- `tools/cleanup_cst.ps1`：清理现场
- `tools/call_mcp_tool.py`：MCP 协议验收与排障 client
- `tools/call_local_mcp_tool.py`：开发期本地直调辅助，不能作为最终验收依据
- `tools/build_portable_bundle.ps1`：生成一键迁移 zip 包
- `tools/install_mcp_one_click.ps1`：目标机 MCP 傻瓜安装入口，完成初始化、配置、启动和验证
- `tools/setup_portable_workspace.ps1`：目标机初始化依赖与 CST Python 库路径
- `tools/verify_portable_install.ps1`：目标机迁移结果校验
- 新 runtime CLI 不放在 `tools/`；入口为 `python -m cst_runtime`
- 旧旁路/调试脚本已移出 `tools/`，归档到 `archive/tools-legacy-20260421/`

## 常用本地命令
```bash
.venv\Scripts\activate
uv run mcp/advanced_mcp.py
uv run mcp/cst_results_mcp.py
uv run python -m cst_runtime list-tools
uv run python -m cst_runtime args-template --tool change-parameter
# 旧 UI 仅作 legacy 参考，不再作为默认入口：
# uv run streamlit run prototype_optimizer/app.py
powershell -ExecutionPolicy Bypass -File tools/kill_cst.ps1
powershell -ExecutionPolicy Bypass -File tools/build_portable_bundle.ps1
powershell -ExecutionPolicy Bypass -File tools/install_mcp_one_click.ps1
```
