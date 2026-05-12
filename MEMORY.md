# MEMORY

## 用途
- 本文件只记录经验证的长期事实、稳定共识和已确认决策
- 本文件不是任务日志，不记录一次性排障过程和临时操作步骤

## 稳定事实
- 当前主蓝本是 `<repo>/ref/ref_model/ref_0/`
- `ref_0` 是四脊喇叭天线蓝本，S 参数频段为 2-18 GHz，远场关注点为 10 GHz
- 当前维护的执行 Skill 是 `skills/cst-runtime-cli-optimization/SKILL.md`
- 旧 `skills/cst-simulation-optimization/` 流程已过时并移入备份，不再作为生产入口或 agent 生效副本维护
- 当前稳定生产链仍以 MCP + Skill 为基准；`cst_runtime/` 是正在验证的共享 runtime/CLI 能力层，不是第二条正式生产链
- 当前重点能力目录是 `<repo>/cst_runtime/`；`prototype_optimizer/` 不再作为主线和默认迁移包依赖
- 标准任务目录根路径是 `<repo>/tasks/task_xxx_slug/runs/run_xxx/`

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

## 新增共识（2026-04-16，2026-05-03 更新）
- 当前项目已可使用 `rg` / `ripgrep` 做文件与内容检索；若 `rg` 不可用、输出异常或权限受限，再回退到 `Select-String` 和 `Get-ChildItem`。
- `mcp/advanced_mcp.py` 等历史文件存在编码异常注释时，编辑应避开乱码注释做补丁锚点；优先用稳定的函数名、装饰器或返回语句定位。

## 新增共识（2026-04-17）
- 当前环境里，PowerShell here-string 直接写入中文 Markdown 容易出现乱码；写中文总结、计划或说明时，优先使用 `apply_patch`，或使用显式 UTF-8 的程序化写入。

## 新增共识（2026-04-21）
- `cst_runtime` CLI 给其他 agent 使用时，默认先跑 `doctor` 和 `usage-guide`；推荐 `--args-file`，只有显式传 `--args-stdin` 才读取管道输入。
- CLI 错误出口必须保持结构化 JSON；误用、缺参、非法 JSON 不应只输出 argparse 文本或阻塞等待 stdin。
- 旧 `tools/cst_cli.py` 和历史调试脚本已归档到 `archive/tools-legacy-20260421/`；默认调用入口回到 `python -m cst_runtime`、正式 MCP client/helper 和 Skill。
- 远场 runtime 迁移已包含解析、预览和 fresh-session 接口，但真实 CST fresh-session 导出/读取仍需单独验证；`Abs(E)` 仍不得当作 dBi 增益。
- 在 Trae/其他 coding agent 低上下文端到端验证完成前，P0 不能标记为 `validated`，也不进入优化指导功能原型。
