# 项目结构说明

> 本文档提供详细结构说明，不是规则源。  
> 规则和红线以 `AGENTS.md` 为准；执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 顶层目录
- `mcp/`：MCP 服务源码，包含 modeler 与 results
- `prototype_optimizer/`：当前重点项目，负责 UI、存储、历史展示等外围能力
- `tasks/`：正式任务与 run 产物
- `ref/`、`ref_model/`：参考蓝本与模型资料
- `skills/`：仓库内正式维护的 Skill
- `.codex/`：项目内 Codex 生效副本
- `docs/`：背景说明、经验、计划和历史记录
- `tools/`：项目脚本与辅助工具
- `backup/`：备份目录
- `tmp/`：临时脚本、临时测试和一次性产物

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
- `skills/cst-simulation-optimization/SKILL.md`：正式流程 Skill
- `prototype_optimizer/app.py`：Streamlit 入口

## 常用脚本
- `tools/kill_cst.ps1`：强制结束 CST 进程
- `tools/close_cst_by_name.ps1`：按项目名关闭 CST 窗口
- `tools/cleanup_cst.ps1`：清理现场
- `tools/plot_farfield.py`：远场绘图

## 常用本地命令
```bash
.venv\Scripts\activate
uv run mcp/advanced_mcp.py
uv run mcp/cst_results_mcp.py
uv run prototype_optimizer/app.py
powershell -ExecutionPolicy Bypass -File tools/kill_cst.ps1
```
