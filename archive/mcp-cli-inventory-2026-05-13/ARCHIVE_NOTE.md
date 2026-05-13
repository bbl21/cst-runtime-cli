# MCP/CLI Inventory Archive

## 用途
此目录包含 MCP→CLI 迁移清点的台账文件。MCP 已正式退场（见 `AGENTS.md`），台账不再参与主工作流。

## 内容
- `generate_mcp_cli_inventory.py` — 台账生成脚本
- `mcp_cli_tool_inventory.json` — Phase 1 工具清点（113 条记录）
- `mcp_cli_migration_status.md` — 可读迁移状态摘要

## 归档日期
2026-05-13

## 归档原因
MCP 已正式退场，不再作为正式生产链。CLI/Skill-only 是当前唯一的正式生产入口。台账已完成其过渡使命。

## 未迁移功能说明
归档时有 3 个 MCP 功能无直接 CLI 对应：
1. `pause_simulation` — 2026-05-13 已追加为 `pause-simulation`
2. `resume_simulation` — 2026-05-13 已追加为 `resume-simulation`
3. `define_material_from_mtd` — 2026-05-13 已追加为 `define-material-from-mtd`

其余 10 个"未迁移"工具已被更好的 CLI 无状态设计覆盖，无需追加。
