# MEMORY

## 用途
- 本文件只记录经验证的长期事实、稳定共识和已确认决策
- 本文件不是任务日志，不记录一次性排障过程和临时操作步骤

## 稳定事实
- 当前主蓝本是 `C:/Users/z1376/Documents/CST_MCP/ref/ref_model/ref_0/`
- `ref_0` 是四脊喇叭天线蓝本，S 参数频段为 2-18 GHz，远场关注点为 10 GHz
- 当前正式维护的执行 Skill 是 `skills/cst-simulation-optimization/SKILL.md`
- 项目内 Codex 生效副本位于 `.codex/cst-simulation-optimization/SKILL.md`
- 当前主流程是 MCP + Skill 驱动；Python 胶水层视为过渡期遗留
- 当前重点项目目录是 `C:/Users/z1376/Documents/CST_MCP/prototype_optimizer/`
- 标准任务目录根路径是 `C:/Users/z1376/Documents/CST_MCP/tasks/task_xxx_slug/runs/run_xxx/`

## 知识治理共识
- `AGENTS.md` 负责规则、红线、修改前置条件和知识分流标准
- `SKILL.md` 负责执行流程、MCP 调用链、失败恢复和任务闭环
- `docs/` 负责背景解释、建模经验、设计说明和历史记录
- 新知识默认先进入任务输出或 `docs/`，复用稳定后再升级到 `MEMORY.md` 或 `AGENTS.md`

## 已退出的治理范围
- `opencode`、`trae` 及其他非当前主工作流工具不再写入项目规则
- 历史兼容路线和旧工具说明如有保留，应写入 `docs/`，不再写入 `AGENTS.md`
## 新增共识（2026-04-15）
- 远场 GUI 直导出的稳定做法是 `fresh CST process + fresh open project + 单项导出 + close(save=False)`。

## 新增共识（2026-04-16）
- 当前 PowerShell 环境里 `rg` 不稳定且可能不可用；跨任务检索默认优先用 `Select-String` 和 `Get-ChildItem`，不要把 `rg` 当作可靠前提。
- `mcp/advanced_mcp.py` 等历史文件存在编码异常注释时，编辑应避开乱码注释做补丁锚点；优先用稳定的函数名、装饰器或返回语句定位。

## 新增共识（2026-04-17）
- 当前环境里，PowerShell here-string 直接写入中文 Markdown 容易出现乱码；写中文总结、计划或说明时，优先使用 `apply_patch`，或使用显式 UTF-8 的程序化写入。
