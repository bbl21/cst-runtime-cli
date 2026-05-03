# 阶段 C 系统集成与一键迁移模式

> 本文档是阶段 C 交付物，用于把 MCP、Skill、知识系统、计划系统集成到同一条可迁移主链。  
> 它不是规则源；规则与红线仍以 `AGENTS.md` 为准，执行流程以 `skills/cst-simulation-optimization/SKILL.md` 为准。

## 一句话结论

当前“一键迁移模式”不是新的生产入口，而是把现有正式主链打包、初始化和校验：

**`tools/build_portable_bundle.ps1` 生成迁移包 -> `tools/install_mcp_one_click.ps1` 在目标机完成初始化、MCP 配置、服务启动和 tools/list 验证。**

正式生产入口仍然是：

**`tasks/task_xxx_slug/` -> `cst-modeler.prepare_new_run(task_path=...)` -> 正式 MCP tools / skills 主链。**

交互式调试、开发验收或用户明确要求可见时，优先使用 GUI 可见 MCP tool call；自动化生产流程允许由编排器内部调用 MCP，不要求暴露每一步内部 tool call，但必须在当前 run 的 `logs/`、`stages/` 或 `status.json` 中保留可审计记录。

## 四类系统职责

| 系统 | 当前职责 | 不负责什么 | 迁移模式中的落点 |
| --- | --- | --- | --- |
| MCP | 稳定工具能力、run 上下文、状态落盘、结果读取、导出和展示 | 不负责策略判断，不承担知识分层 | `mcp/`、`tools/start_*_mcp_http.ps1`、`tools/call_mcp_tool.py` |
| Skill | 正式流程、调用顺序、失败恢复、执行约束 | 不沉淀 Python 复用代码，不替代 MCP 工具 | `skills/cst-simulation-optimization/SKILL.md` 和 `.codex/` 生效副本 |
| 知识系统 | 规则、经验、长期共识、专题说明的分层入口 | 不直接覆盖 `AGENTS.md` 规则，不承担当次任务日志 | `AGENTS.md`、`MEMORY.md`、`docs/`、`docs/topic-index.md` |
| 计划系统 | 当前主线、阶段目标、门控条件和清单维护 | 不替代执行流程，不把长期愿景直接推入近期主线 | `docs/project-goals-and-plan.md`、`docs/current-priority-checklist.md` |

## 工具粒度原则

生产自动化仍然由 agent 做判断，不等于固定脚本机械执行。工具封装按以下原则划分：

- 固定、长流程、机械重复且输入输出稳定的部分，可以封装成阶段级工具或编排命令，例如初始化工作区、标准结果导出与状态落盘组合。
- 需要 agent 根据返回信息判断下一步的部分，必须保留小粒度工具，例如选择下一组参数、判断是否重试、判断结果是否可信、决定是否询问用户。
- 阶段级封装不能变成黑盒；它必须返回结构化状态、关键指标、输出文件、错误分类和审计日志路径。
- 小粒度工具不能绕开主链；它们的输出仍必须落到当前 run 的 `logs/`、`stages/`、`analysis/` 或 `status.json`。
- Skill 负责告诉 agent 什么时候调用阶段级封装，什么时候拆开调用小粒度工具。

## 一键迁移文件

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `tools/build_portable_bundle.ps1` | 从当前仓库生成 zip 迁移包 | 默认只打包系统底座；可选 `-IncludeRef`、`-IncludeTasks`、`-IncludePrototypeData` |
| `tools/install_mcp_one_click.ps1` | 一键安装 MCP 傻瓜入口 | 默认执行初始化、写 `.codex/config.toml`、启动 modeler/results HTTP MCP、执行 tools/list 验证 |
| `tools/setup_portable_workspace.ps1` | 在目标机设置 CST Python 库路径并执行依赖安装 | 支持 `-CstLibraryPath` 指向非默认 CST 安装路径 |
| `tools/verify_portable_install.ps1` | 验证迁移包是否包含正式主链必需文件，且 Python 代码可编译 | 可用 `-Json` 输出结构化结果 |
| `PORTABLE_MANIFEST.json` | 迁移包自动生成的清单 | 记录打包时间、源路径、包含选项和正式入口 |
| `PORTABLE_README.md` | 迁移包自动生成的快速入口说明 | 解压后可直接阅读 |

## 默认迁移边界

默认迁移包的历史版本包含：

- `mcp/`
- `skills/`
- `.codex/`
- `docs/`
- `tools/`
- `prototype_optimizer/`，但排除 `prototype_optimizer/data/`
- `AGENTS.md`
- `MEMORY.md`
- `README.md`
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `requirements.txt`

后续轻量 CLI-first 迁移包应调整为默认不包含 `prototype_optimizer/`；若确需保留旧 UI 原型，应通过显式 legacy/archive 选项加入，且不得带入 `prototype_optimizer/data/`。

默认迁移包不包含：

- `.git/`
- `.venv/`
- `tmp/`
- `dist/`
- `backup/`
- `plot_previews/`
- `tasks/`
- `ref/`
- `prototype_optimizer/data/`
- `*.lok`、`*.tmp`、Python 缓存文件

如果要迁移蓝本工程，显式使用 `-IncludeRef`。如果要迁移历史任务和 run 产物，显式使用 `-IncludeTasks`。这两个选项可能生成很大的包，也可能包含历史仿真数据；默认不启用。

## 目标机最小验证

目标机完成解压后，最小验证顺序为：

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_mcp_one_click.ps1
```

若 CST 2026 不在默认路径，传入：

```powershell
powershell -ExecutionPolicy Bypass -File tools/install_mcp_one_click.ps1 -CstLibraryPath "D:\Path\To\CST Studio Suite 2026\AMD64\python_cst_libraries"
```

如需只做结构校验、不安装依赖和启动服务，可分别使用：

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup_portable_workspace.ps1 -SkipDependencyInstall
powershell -ExecutionPolicy Bypass -File tools/verify_portable_install.ps1 -SkipPythonCompile
```

验证通过只说明系统底座和 MCP 服务可用；它不等于已经完成真实 CST 仿真任务。真实任务仍需按正式入口创建 `tasks/task_xxx_slug/` 并运行主链。

## 门控结论

阶段 C 当前完成标准：

- MCP、Skill、知识系统、计划系统职责已写清。
- 一键迁移不新增生产旁路，只服务现有正式主链。
- 已提供打包、初始化、校验三个脚本。
- 已提供 MCP 一键安装脚本，降低目标机配置成本。
- 默认迁移边界避免带入历史 run、临时文件和锁文件。

## 本地验证记录

已在本机完成以下验证：

- PowerShell 脚本解析通过：`build_portable_bundle.ps1`、`setup_portable_workspace.ps1`、`verify_portable_install.ps1`。
- `tools/build_portable_bundle.ps1 -BundleName cst_mcp_portable_validation` 已生成迁移包。
- zip 内容已检查，确认包含正式主链必要文件，并默认排除 `.venv/`、`tmp/`、`tasks/`、`ref/`、`*.bak`。
- 将 zip 解压到 `tmp/portable_verify_extract` 后，执行 `setup_portable_workspace.ps1 -SkipDependencyInstall` 通过结构校验。
- 在当前仓库执行 `verify_portable_install.ps1 -Json` 通过，包括 Python 编译检查。
- 执行 `install_mcp_one_click.ps1 -SkipDependencyInstall -ForceRestart` 后，modeler/results 两个 HTTP MCP 均通过 `tools/list` 验证，并写入 `.codex/config.toml`。

阶段 C 完成后，可以进入阶段 D：在低上下文条件下用迁移包验证正式入口是否可被新执行者理解和启动。
