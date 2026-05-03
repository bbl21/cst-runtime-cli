# CST 会话/进程管理测试计划

> 范围：在扩展 MCP/CLI 迁移测试前，先验证 CST 进程管理系统本身。
> 本文档是执行计划，不是项目规则来源。

## 原则

进程管理是前置关卡。在会话/进程管理器能够可靠处理以下情况之前，不要开始完整的迁移或工作流验证：

- 检查当前 CST 进程、锁文件、打开的项目和重连就绪状态；
- 显式打开 `working.cst`；
- 仅当预期项目是唯一打开的项目时才重连；
- 使用 `save=false` 关闭并验证锁释放；
- 仅退出/清理白名单内的 CST 进程；
- 记录 `Access is denied` 残留，包括 PID/名称和锁文件证据。

集中控制平面是 `cst_runtime/session_manager.py`。底层助手按职责拆分：

- `cst_runtime/modeler.py`：modeler 打开/关闭/读/写操作。
- `cst_runtime/project_identity.py`：显式 `project_path`、重连验证、打开项目列表、锁文件检查。
- `cst_runtime/process_cleanup.py`：白名单进程发现和清理。

## CLI 关卡

先使用这个流水线配方：

```powershell
uv run python -m cst_runtime describe-pipeline --pipeline cst-session-management-gate
```

预期生命周期命令：

```powershell
uv run python -m cst_runtime cst-session-inspect --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-open --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-reattach --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-close --project-path "$run\projects\working.cst" --save false --wait-unlock true
uv run python -m cst_runtime cst-session-quit --project-path "$run\projects\working.cst" --dry-run true
uv run python -m cst_runtime cst-session-quit --project-path "$run\projects\working.cst" --dry-run false
uv run python -m cst_runtime cst-session-inspect --project-path "$run\projects\working.cst"
```

除非关闭成功且锁文件已清除，否则在非试运行退出步骤之前停止。

## 自动化无 CST 启动检查

运行：

```powershell
uv run python -m unittest discover -s skills\cst-runtime-cli-optimization\tests
```

覆盖范围：

- `cst-session-*` 工具可通过 `describe-tool` 发现；
- 参数模板包含必需的生命周期字段；
- `cst-session-inspect` 在没有项目时返回结构化 JSON；
- `cst-session-quit --dry-run true` 不终止进程，并返回试运行清理记录；
- `cst-session-management-gate` 可通过 `describe-pipeline` 发现。

通过此层不验证真实的 CST COM 行为。

## 完整真机矩阵

使用一个一次性运行的工作副本。永远不要直接使用参考项目。

| 用例 | 准备 | 命令焦点 | 通过条件 |
| --- | --- | --- | --- |
| PM-01 干净检查 | 未故意打开任何 CST 项目 | `cst-session-inspect` | JSON 成功；就绪状态为 `clear` 或 `attention_required`；不在白名单外进行广泛进程扫描 |
| PM-02 打开显式项目 | 一次性 `working.cst` | `cst-session-open` | 状态成功；后续检查列出预期项目或重连就绪 |
| PM-03 重连预期项目 | 仅预期项目打开 | `cst-session-reattach` | 状态成功；打开项目列表恰好有预期的 `.cst` |
| PM-04 拒绝模糊重连 | 预期项目加无关 CST 项目打开 | `cst-session-reattach` | 状态错误；`error_type=ambiguous_open_projects`；不执行写入操作 |
| PM-05 关闭并解锁 | 预期项目打开 | `cst-session-close --save false --wait-unlock true` | 状态成功；锁文件清除；后续检查显示 `lock_count=0` |
| PM-06 试运行退出 | 关闭后 | `cst-session-quit --dry-run true` | 无进程被终止；清理状态为 `dry_run`；白名单已记录 |
| PM-07 真实退出 | 关闭和试运行后 | `cst-session-quit --dry-run false` | 白名单进程消失，或明确记录访问被拒绝残留 |
| PM-08 访问被拒绝残留 | Windows 拒绝 Stop-Process | `cst-session-quit --dry-run false` | 如果锁已清除，状态可能为成功，附带 `nonblocking_access_denied_residual`；保留 PID/名称/错误 |
| PM-09 锁仍存在 | 在伴生目录下创建或保留 `.lok` | `cst-session-close` / `cst-session-inspect` | 状态错误或就绪状态被阻止；不允许复制/重新打开 |
| PM-10 最终检查 | 清理后 | `cst-session-inspect` | lock_count 为 0；无不安全的打开项目状态残留；剩余进程已分类 |

## 证据

在当前运行中记录每个真机用例：

- 命令行；
- stdout JSON；
- `status`、`readiness`、`session_action`；
- 打开项目列表；
- 锁文件前后；
- 白名单进程前后；
- 任何 `Access is denied` PID/名称/错误。

如果任何用例未运行，将进程管理关卡标记为 `needs_validation`，而不是 `validated`。

## 2026-05-03 运行记录

运行：

```text
tasks/task_010_ref0_fresh_session_farfield_validation/runs/run_002
```

已验证：

- PM-01 在一次性 `working.cst` 副本上进行干净/初始检查。
- PM-02 打开显式项目。
- PM-03 重连预期项目作为唯一打开的项目。
- PM-05 使用 `save=false` 关闭并验证锁释放。
- PM-06 试运行退出。
- PM-07 真实仅白名单退出。
- PM-08 `Access is denied` 残留记录。
- PM-09 使用临时合成 `Model.lok` 然后移除的锁仍存在阻止行为。
- PM-10 最终检查。

证据在：

- `runs/run_002/logs/tool_calls.jsonl`
- `runs/run_002/stages/cli_*.json`
- `runs/run_002/status.json`

结果：

- `CST DESIGN ENVIRONMENT_AMD64` PID `51756` 被白名单清理终止。
- `CSTDCSolverServer_AMD64` PID `8584`、`CSTDCMainController_AMD64` PID `8644` 和 `cstd` PID `10228` 保留，附带 `Access is denied`。
- 关闭/清理后工作项目的 `lock_count=0`，无打开的 CST 项目残留。
- PM-04 模糊多项目重连未执行，因为故意打开第二个 CST 项目会使当前保护性重连语义下的自动关闭变得模糊。状态保持为 `needs_validation`，直到添加安全的模糊项目夹具。
