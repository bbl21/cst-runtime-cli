# 2026-04-20 工作收尾与明日计划

> 本文档用于当天收尾、知识回收和次日启动。它不是规则源；规则与红线以 `AGENTS.md` 为准，阶段目标以 `docs/project-goals-and-plan.md` 和 `docs/current-priority-checklist.md` 为准。

## 今日完成

### 1. 生产可见性规则调整

将“生产过程必须 GUI 可见 MCP tool call”的旧口径调整为分层规则：

- 交互式调试、开发验收、用户明确要求可见时，优先使用 GUI 可见 MCP tool call。
- 自动化生产或批处理允许内部调用工具，不要求暴露每一步内部调用。
- 所有自动化调用必须把关键调用摘要、输入参数、输出路径、状态、错误和必要返回写入当前 run 的 `logs/`、`stages/` 或 `status.json`。

已同步到：

- `AGENTS.md`
- `skills/cst-simulation-optimization/SKILL.md`
- `.codex/cst-simulation-optimization/SKILL.md`
- `C:/Users/z1376/.codex/skills/cst-simulation-optimization/SKILL.md`
- `docs/formal-entry-and-bypass-audit.md`
- `docs/phase-c-system-integration-and-portable-mode.md`

### 2. 工具粒度原则固化

明确当前工具分工：

- 固定、长流程、机械重复、输入输出稳定的部分，可以封装为阶段级工具或编排命令。
- 需要 agent 根据返回信息判断、选择、重试或询问用户的环节，必须保留小粒度工具。
- 阶段级封装不能变成黑盒；必须返回结构化事实、关键指标、错误分类和审计日志路径。

已同步到：

- `AGENTS.md`
- `docs/project-goals-and-plan.md`
- `docs/current-priority-checklist.md`
- `docs/phase-c-system-integration-and-portable-mode.md`
- `skills/cst-simulation-optimization/SKILL.md`
- `.codex/cst-simulation-optimization/SKILL.md`
- `C:/Users/z1376/.codex/skills/cst-simulation-optimization/SKILL.md`

### 3. CST CLI 原子工具 POC

新增：

- `tools/cst_cli.py`
- `docs/cst-cli-atomic-tools-poc.md`

验证内容：

- `list-tools` / `describe-tool` 工具发现可用。
- `prepare-run` 可创建标准临时 run 工作区。
- `open-project` 可按显式 `project_path` 打开临时工作副本。
- `assert-project-open` 可确认目标工程是唯一打开工程。
- `list-parameters` 可跨独立 CLI 进程读取 CST 参数。
- `change-parameter` 可跨独立 CLI 进程修改参数。
- 修改后再次 `list-parameters` 可读到 `R=0.102`。
- `close-project(save=false)` 可关闭工程。
- 调用记录写入 `logs/tool_calls.jsonl` 和 `stages/cli_*.json`。

验证结论：

- CLI 进程之间不能继承 Python 内存中的 CST `project` 对象。
- 但在单一打开工程条件下，独立 CLI 进程可以通过 CST API 重新附着当前活动项目。
- 生产级 CLI 必须显式传入 `project_path` 并校验项目身份；不能把 active project 当默认生产依据。
- 多 CST 工程并发管理尚未解决，当前 POC 在多工程打开时应拒绝写操作。

## 今日知识回收

### 已形成规则或准规则

- 生产自动化是 agentic automation，不是机械脚本；agent 必须读取工具返回并判断下一步。
- 工具调用可不暴露给最终用户，但必须审计落盘。
- 工具粒度由判断需求决定，而不是由底层 API 粒度决定。
- CLI 原子工具可以作为 Skill 轻量化安装方向，但必须保证 JSON 输入输出和项目身份校验。

这些内容已经分流到 `AGENTS.md`、Skill 和 `docs/`，暂不写入 `MEMORY.md`；等 CLI 方向经过更多任务复用后再考虑升级为长期共识。

### 已形成调试经验

- `close-project(save=false)` 后锁文件可能短暂残留，今天观察到约 3 秒后释放。
- `change_parameter` 使用 `project.modeler.add_to_history(...)` 会触发 `DeprecationWarning`，CLI 必须保证 stdout 只输出 JSON，不能让 warning 污染 agent 解析。
- `project_path -> run_dir` 推断应以 `working.cst` 的父目录是否为 `projects` 判断，不能按错误的 parents 层级推断。

## 剩余风险

| 风险 | 状态 | 明日处理方式 |
| --- | --- | --- |
| 阶段 D 低上下文验证未完成 | 阻塞 P0 完成 | 明日第一优先级执行 |
| CLI POC 只支持唯一打开工程 | 非阻塞，POC 限制 | 后续加 `inspect-project` / `verify-project-identity` |
| CLI 尚未覆盖仿真和 results | 观察项 | 不在阶段 D 前扩展 |
| portable bundle 经过新增 CLI 后未重新打包验证 | 非阻塞，但影响迁移验证 | 阶段 D 重新打包或明确使用当前 bundle 版本 |
| 当前仓库已有大量未提交变更 | 管理风险 | 明日先确认变更归属，再继续实现 |

## 明日主线

明天只做一件主事：

**完成阶段 D：低上下文验证与收尾门控。**

原因：

- 阶段 A/B/C 和 CLI POC 都已提供结构基础，但还没有证明“低上下文执行者/目标环境可以按文档启动正式流程”。
- 未完成阶段 D 前，不应继续扩大 CLI 工具范围，也不应进入优化指导原型。
- 阶段 D 的结果会决定 CLI 原子工具是进入下一阶段主线，还是只作为观察项保留。

## 明日执行计划

### 第一段：现场确认

1. 查看 `git status --short`，确认今日新增/修改文件。
2. 确认无 CST 进程和 `.lok` 锁文件残留。
3. 确认 `tools/cst_cli.py list-tools`、`verify_portable_install.ps1 -Json` 仍可用。

完成信号：

- 当前现场干净，无进程/锁阻塞。
- 能明确今天的 POC 只作为观察项，不替代阶段 D。

### 第二段：阶段 D 低上下文验证

1. 重新生成或选定迁移包。
2. 解压到新的低上下文验证目录。
3. 按迁移包文档执行最小安装/校验。
4. 从正式入口读取规则和 Skill，创建或识别标准 `tasks/task_xxx_slug/`。
5. 验证标准 run 目录、状态文件、日志、stages、analysis/exports 边界。
6. 记录所有阻塞项、非阻塞项和观察项。

交付物：

- `docs/phase-d-low-context-validation.md`

完成信号：

- 能明确判断 P0 是否 `validated`。
- 若不能通过，必须标记 `blocked` 或 `needs_validation`，不能伪装完成。

### 第三段：根据阶段 D 结果决定后续

若阶段 D 通过：

- 进入 CLI 原子工具方向的阶段 E 设计，但只先做项目身份层增强：
  - `inspect-project`
  - `verify-project-identity`
  - `wait-project-unlocked`

若阶段 D 未通过：

- 只修复阶段 D 暴露的阻塞项。
- 暂停扩展 CLI 和优化指导能力。

## 明日禁止事项

- 不扩展到远场/仿真 CLI，除非阶段 D 已通过且项目身份层无阻塞。
- 不把 `tools/cst_cli.py` 宣称为正式生产入口；它目前是 POC。
- 不新增第二条生产主链。
- 不进入论文研读或优化指导原型。

