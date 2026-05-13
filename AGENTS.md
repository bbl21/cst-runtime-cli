# CST_MCP 项目规则

## 项目概览
- **名称**: CST MCP Project
- **技术栈**: Python 3.13+ / Streamlit / SQLite / MCP / CST Studio Suite 2026
- **包管理**: uv
- **CST 版本**: CST Studio Suite 2026
- **MCP 版本**: >=1.25.0

## 沟通偏好
- 中文交流，直接高效
- 一次只做一件事，禁止四面出击
- 生产流程优先走 CLI / Skill 链路
- 本项目检索文件或内容时可以使用 `rg` / `ripgrep`；若 `rg` 不可用、输出异常或权限受限，再回退到 PowerShell 原生命令，例如 `Get-ChildItem`、`Select-String`、`Get-Content`
- 需求没说清楚时，先多问几句把目标、边界、输入输出和验收标准问清楚，再开始动手
- 当用户在对话中明确提出原则性要求、知识治理要求或“以后应如何做”的约束时，默认视为规则候选；若其适用范围是当前项目全局，应触发写入规则，而不是只留在聊天记录里

## 规则来源
- 项目规则唯一来源：仓库根目录下的 `AGENTS.md`
- 本文件发生改动后，后续任务一律按最新内容同步执行

## 规则分层与修改原则（2026-04-14）

### 规则分层
- Level 1：系统约束。涉及 CST 项目锁、COM session、结果一致性、远场导出安全的规则，必须强制执行，禁止绕过
- Level 2：实现约定。涉及目录结构、命名、导出格式、日志格式的规则，默认遵守；如需变更，必须在任务说明中显式声明
- Level 3：经验规则。涉及当前版本已知坑、临时 workaround、接口兼容性说明，必须注明适用范围与失效条件

### 修改前置条件
- 每次只允许处理一个明确问题，禁止在同一次改动中顺手重构无关模块
- 修改前必须先定位具体函数、调用链和影响范围；禁止未阅读源码就直接下手改
- 若问题涉及 session、保存、关闭、导出、文件复制，必须先检查是否违反本文件中的 Level 1 规则
- 修改 `mcp/*.py` 前必须先按既有备份规则完成备份，再开始编辑

### 实现原则
- 修复必须优先解决根因，再处理表象；禁止仅靠补丁式绕过掩盖状态问题
- modeler 与 results 必须视为两个独立 session，禁止混用对象、状态或缓存假设
- 任何会影响结果读取的新实现，必须显式定义何时 `save`、何时 `close`、何时 `reopen`、何时失效缓存
- 禁止依赖隐式全局状态完成关键流程；关键上下文必须显式传递或集中封装
- 若某个操作会触发大量请求、读取大量数据或明显消耗大量 token，必须先判断是否真的必要，并优先选择更小范围、更灵活、更节省额度的替代方式
- 禁止新增旁路生产链路；生产流程必须继续遵守既定 CLI / Skill 链路
- 工具封装粒度必须按职责划分：稳定、固定、长流程的机械部分可以封装为阶段级工具或编排命令；需要 agent 根据返回信息判断、选择、重试或询问用户的环节，必须保留小粒度工具接口，并返回足够结构化事实供 agent 决策
- 禁止保留不可达死代码；已禁用工具若保留函数，函数体只能直接返回 error 与替代方案
- 新增或修改导出能力时，必须明确输出目录、文件格式、覆盖策略和失败状态

### 验证与收尾
- 每次修改后必须至少验证：接口返回结构、错误分支、资源释放、与既有规则不冲突
- 若修改涉及 results 读取，必须验证刷新后可读到最新落盘结果，且旧缓存不会误用
- 若修改涉及导出，必须验证导出文件确实写入当前 run 目录或规则定义的回退目录
- 若修改涉及关闭/退出，必须验证项目关闭后无残留锁文件或 CST 相关进程异常占用
- 若 CST 进程在项目已正常关闭、无残留锁文件且用户明确确认不会影响当前任务时仍因权限拒绝无法强杀，可标记为非阻塞残留；必须记录 PID、进程名和 `Access is denied` 原因，禁止声称已成功杀进程
- 注释只写“为什么这样做”，不重复代码字面意思
- 临时 workaround 必须附带原因、适用版本和后续移除条件
- 新规则若只是当前问题专用，不得直接提升为全局规则；先标记为经验规则，验证稳定后再升级
- 若验证不充分，任务状态必须明确标记为 `blocked` 或 `needs_validation`，禁止伪装为已完成

### 隐私与远端发布
- 涉及个人信息、个人本机绝对路径、用户名、私有任务数据、未脱敏工程路径或本地环境细节的内容，禁止推送到远端仓库或公开发布
- `docs/` 在本项目中可作为本地规则、计划和经验承接路径使用，但默认不随普通代码改动提交或推送；即使文件已被 git 跟踪，也必须把 docs diff 单独列出并经用户明确同意后才可 staged / commit / push
- 只有涉及项目实际运作的业务记录、验证记录、优化记录、经验沉淀或用户明确要求的公开说明时，`docs/` 内容才允许进入提交/推送范围
- 执行 `git push`、创建 PR、生成对外发布包或整理公开文档前，必须检查 staged diff / 发布内容中是否包含个人信息；发现后必须先脱敏或移出发布范围
- 允许保留在本地调试、任务审计或私有 run 记录中的个人路径，不得直接复制到 README、公开文档、提交信息或远端工件

## 知识分层与自我进化（2026-04-14）

### 目标与计划管理（2026-04-15）
- 项目目标与阶段计划的工作文档统一维护在 `docs/project-goals-and-plan.md`
- `docs/project-goals-and-plan.md` 不是规则源，但它是当前项目目标、阶段计划、主攻方向和维护节奏的默认依据；执行任务时必须先对齐其中的当前阶段目标与当前阶段主攻方向
- 当用户明确更新近期目标、中期目标、长期愿景、当前主攻方向或维护节奏时，若该变更适用于整个项目，必须同步更新 `docs/project-goals-and-plan.md`，禁止只留在聊天记录里
- 若当前任务与 `docs/project-goals-and-plan.md` 的近期目标或当前阶段主攻方向不一致，必须先指出偏离点；未经用户明确确认，不得把高不确定扩展方向插入当前主线
- 长期愿景不得直接支配近期开发；近期任务必须优先服务近期目标，并且不得破坏中期的平台化方向
- 若用户请求明显发散，或任务更像长期探索而非当前阶段交付，必须主动提醒当前阶段边界、插队成本和对近期目标的影响
- 每次完成近期关键任务后，必须检查 `docs/project-goals-and-plan.md` 中的状态、验收标准、主要风险和当前不做事项是否仍然有效；若已失效，应及时更新
- 新想法默认先判断属于：近期主线、后续计划、观察项、或拒绝进入当前主线；未完成分类前，不得直接并入开发
- 近期计划若发生偏移，必须显式记录是“目标变更”还是“执行偏移”；禁止用临时插队掩盖目标失焦

### 文档边界
- `AGENTS.md` 只写规则、约束、禁令、分层标准、修改前置条件；不写建模经验、不写完整流程手册、不写历史排障长文
- 当前维护的执行 Skill 负责执行流程、调用顺序、任务闭环、失败恢复；不重复全局规则正文
- `docs/` 负责背景解释、建模经验、方案比较、设计说明、历史记录；允许细节丰富，但不冒充全局规则
- 仓库根目录 `MEMORY.md` 只记录稳定事实、长期共识、已确认决策；不记录一次性任务日志和临时排障过程
- `AGENTS.md` 不再维护 `opencode`、`trae` 或其他非当前主工作流工具的路径、命令和同步说明；OpenCode 跨项目分工见用户级 `%USERPROFILE%\.codex\docs\opencode-worker-division.md`，本项目接线覆盖见 `docs/runtime/opencode-worker-division.md`，Skill 分发见 `docs/runtime/agent-skill-distribution.md`

### 知识查阅规则（2026-04-17）
- 知识分层不只规定“存在哪里”，也必须规定“先去哪里查”；任务开始时必须先判断当前问题属于：规则约束、阶段目标、执行流程、稳定事实、专题经验中的哪一类，再决定查阅入口
- 默认查阅顺序固定为：`AGENTS.md` -> `docs/project-goals-and-plan.md` -> `docs/current-priority-checklist.md` -> 对应 `SKILL.md` -> `MEMORY.md` -> `docs/topic-index.md` -> 相关 `docs/` 专题文档；禁止一上来全仓盲搜
- 若任务涉及红线、约束、目录规范、关闭/保存/导出/session 等原则问题，必须先查 `AGENTS.md`
- 若任务涉及当前该不该做、是否偏离主线、是否属于插队、验收标准是什么，必须先查 `docs/project-goals-and-plan.md` 与 `docs/current-priority-checklist.md`
- 若任务涉及执行步骤、MCP 调用顺序、失败恢复、任务闭环，必须先查对应 `SKILL.md`
- 若任务涉及默认蓝本、稳定路径、长期共识、已确认决策，必须查 `MEMORY.md`
- 若任务涉及背景说明、历史方案、经验比较、专题设计细节，才进入 `docs/` 做定向查阅；若 docs 入口不明确，先看 `docs/topic-index.md`；`docs/` 默认不是规则源，也不能覆盖 `AGENTS.md`
- 查阅时必须优先做小范围定向定位；只有在入口不明确时，才允许扩大检索范围，禁止为找一句规则而通读无关长文

### 知识命中与冲突处理
- 命中标准不是“看到相关词”就算，而是必须找到对当前任务直接适用的规则、事实、流程或计划约束；找不到直接约束时，必须继续下钻或补调查
- 发生冲突时，优先级固定为：`AGENTS.md` > `docs/project-goals-and-plan.md` / `docs/current-priority-checklist.md` > `SKILL.md` > `MEMORY.md` > 其他 `docs/`
- `MEMORY.md` 只提供已确认事实和长期共识；若其与源码、当前目录现实或用户最新明确要求冲突，必须先核实，再决定是更新 memory 还是按最新事实执行
- `docs/` 中的经验、历史记录和方案说明只能作为解释与参考，不能直接提升为强制规则；需要升级时，仍按 `docs/` -> `MEMORY.md` / `AGENTS.md` 的路径走
- 若按既定入口未查到答案，必须明确标记“当前知识库未命中”，然后选择：继续读源码/实物事实、补查对应专题文档、或直接向用户澄清；禁止把猜测伪装成项目知识

### Memory 维护规则
- 只有经验证的长期共识才能写入 `MEMORY.md`
- 每条 memory 应尽量短，偏事实或决策，不写操作步骤
- 写入前先判断是否已被 `AGENTS.md` 或 `docs/` 覆盖，避免重复
- 若某条 memory 后续被升级为规则，则在 `MEMORY.md` 中压缩为一句引用或直接删除

### 规则升级路径
- 新发现默认先进入任务输出或 `docs/`
- 经两次以上独立任务复用且稳定后，可升级到 `MEMORY.md`
- 若进一步证明其违反会导致系统错误、流程污染、结果失真，才升级到 `AGENTS.md`
- 若其本质是执行方法、流程顺序或工具调用链，则进入 `SKILL.md` 而不是 `AGENTS.md`
- 做知识回收时，只保留对正确执行有直接帮助的稳定原则；禁止混入测试过程里暴露出的次要信息、临时变量或枝节

### Subagent 组织原则
- OpenCode / 外部 worker 的跨项目默认分工、任务卡原则和回收要求属于用户级规则，见 `%USERPROFILE%\.codex\docs\opencode-worker-division.md`
- 本项目只维护 CST_MCP 特有的 worker 接线与红线，见 `docs/runtime/opencode-worker-division.md`
- worker 未经任务卡明确授权，不得执行 CST/MCP/runtime 生产动作、修改 `mcp/*.py`、创建正式 run、修改 ref 工程、升级规则或改变项目主线
- worker 输出只能作为待验收事实或候选草稿；Codex 主 agent 必须回收摘要、检查产物、核对项目红线后，才能纳入结论
- 只有任务可明确拆分、子任务边界清晰、并行确有收益时，才考虑 subagent
- 主 agent 负责定义目标、分配边界、回收结果、整合输出和最终验收
- subagent 只负责其边界内的探索、实现或验证，禁止自创全局规则
- subagent 产出的经验不能直接写入 `AGENTS.md`；必须由主 agent 验证后，再决定进入 `docs/`、`MEMORY.md` 或 `SKILL.md`
- 若当前平台没有稳定 subagent 能力，这些规则仍作为未来协作原则保留，不影响当前执行

### 任务收尾知识回收
- 每次任务完成后，必须判断是否发现了新的长期红线
- 每次任务完成后，必须判断是否形成了新的稳定执行流程
- 每次任务完成后，必须判断是否产生了新的建模/调试经验
- 每次任务完成后，必须判断是否确认了新的跨任务共识
- 只要答案为“是”，就应将知识分流到 `AGENTS.md`、`SKILL.md`、`docs/`、`MEMORY.md` 之一，而不是留在聊天记录里

## 强制规则

### 项目/进程管理
- 任务完成后必须关闭项目并杀 CST 进程：`close_project` -> 杀 CST 进程
- CST 强杀只允许作用于白名单进程名：`cstd`、`CST DESIGN ENVIRONMENT_AMD64`、`CSTDCMainController_AMD64`、`CSTDCSolverServer_AMD64`；禁止用宽泛模式误杀无关进程
- 若 CST 进程无法强杀且返回权限拒绝，先确认工程已 `close(save=False)` 或按流程关闭、当前 run 目录无锁文件；在用户明确确认可暂不处理时，允许继续收尾，但任务输出必须说明这些进程未被清理
- 复制 CST 项目前必须先关闭项目，否则文件会被锁定
- 复制 CST 工程时必须完整复制 `.cst` 文件和同名目录，缺一不可

### 工程副本与 run 目录
- 参考工程一律视为只读蓝本，禁止直接在 `ref/`、`ref_model/`、`prototype_optimizer/data/workspaces/*/projects/source/` 下修改
- 每次任务必须先创建独立工作副本，再在副本上建模、仿真、导出结果
- run 目录统一使用：`tasks/task_xxx_slug/runs/run_xxx/`
- 标准 run 结构统一使用：`run_xxx/{projects,exports,logs,stages,analysis}`
- `projects/` 只放当前 run 的工程副本与其同名目录，例如 `working.cst` 与 `working/`
- `exports/` 只放导出的 S 参数、远场、场分布、截图、HTML 预览等外部结果文件，不存放源工程副本
- `logs/` 只放流程日志、诊断输出、报错记录
- `stages/` 只放阶段状态文件与阶段性元数据
- `analysis/` 只放分析结论、计算中间产物、对比表和结构化摘要
- `summary.md` 用于记录本次 run 的结果摘要；`status.json` 用于记录当前状态；`config.json` 用于记录输入参数与运行配置
- 若需要基于已有 run 派生新尝试，必须创建新的 `run_xxx`，不要覆盖旧 run 的工程和导出结果
- runtime/CLI 生成的 HTML 预览应优先写入当前 run 的 `exports/`；仅在无法识别 run 上下文时回退到项目根 `plot_previews/`

### 自动化优化循环红线（2026-05-04）
- 自动优化循环每轮执行流程必须包含早停判断：`仿真 → 读结果 → 解析指标 → 判断是否达目标 → 达则 break，不达则继续`
- "执行"和"评估"不得拆分为两个独立阶段；目标指标必须在每轮循环体内部实时解析和判断
- 自动化脚本或管道定义的停止条件（target S11 ≤ -40 dB、轮数上限、或用户指定阈值）必须在执行循环代码中显式实现，不得仅写在 config.json 或文档中
- 若未实现早停导致超过目标后继续执行额外轮次，任务输出必须明确标记为 `overrun` 并说明浪费了多少轮

### 结果与导出红线
- 读取结果后禁止保存，以免造成项目报错
- 远场导出必须放在流程最后；导出后必须 `close(save=False)`，禁止保存
- 远场结果应先定位真实 farfield 名称，再通过受支持的导出链路导出 ASCII/TXT，由外部程序解析
- `export_farfield_ascii_selecttree` 不应注册为可用 MCP tool；如保留函数，也必须直接返回 error 并提示改用 `export_farfield`
- S11 原始数据是复数字典 `{'real': ..., 'imag': ...}`，不是 dB 值；必须先 `math.hypot(real, imag)`，再做 `20*log10()`
- 远场 ASCII/TXT 若表头是 `Abs(E)[V/m]`，其 `20*log10(Abs(E))` 结果不得标记为 `dBi` 峰值增益；这只能作为场强幅度代理或相对方向图分析量
- 若任务约束使用“峰值增益 dBi”，必须走真实 gain/dBi 结果读取链路或以 CST 图上/结果树中的 gain 读数为准；禁止拿 `Abs(E)` 代理量冒充绝对增益

### Session 与结果一致性
- modeler session 与 results session 是两个独立 session，禁止混用对象和缓存假设
- 仿真结果先存在 modeler 内存，不会自动传递到 results
- 当前参数优化任务已验证：仿真完成后结果会自动保存，但 results 侧不一定立刻看到最新 `run_id`
- 当前稳定读取流程是：results 侧使用 `allow_interactive=True`；仿真结束后先关闭 modeler 项目 `close_project(save=False)` 释放工程，再由 results 侧执行 `close + reopen` 刷新 session，并以 `list_run_ids` 返回的最新 `run_id` 为准
- 禁止把 `save_project()` 当作结果可读的默认前置条件；若后续发现某类工程不满足上述自动保存行为，必须在对应任务记录中明确标注适用范围
- 关闭 project 的正确做法是：`save=True` 时先 `project.save()`，再调用无参 `project.close()`；禁止向 `project.close()` 传 `SaveChanges` 等 kwargs

### CLI/runtime 源码与工具管理
- 当前正式执行实现位于 `skills/cst-runtime-cli/scripts/cst_runtime/` 与 `skills/cst-runtime-cli/scripts/cst_runtime_cli.py`
- 新功能默认只进入 Skill 内 CLI/runtime；`mcp/*.py` 不再作为正式生产实现入口
- 发现旧 MCP 工具失效后，不再把修复它作为默认方向；应优先在 CLI/runtime 中提供替代入口，并记录遗留原因与替代路径
- 开发或修改 CLI/runtime 时，开发期可按文件路径加载模块、直接调用函数或运行 `cst_runtime_cli.py` 做快速定位，但这些只能作为调试辅助，不能作为交付验收依据
- CLI/runtime 的最终交付验收标准必须是真实 CLI 调用成功：通过 `python <skill-root>\scripts\cst_runtime_cli.py` 发现命令、生成参数模板、执行目标命令，并验证功能结果落盘或返回结构正确
- 生产流程必须继续走正式 CLI / Skill 链路。交互式调试、开发验收、用户明确要求可见时，可以保留 GUI 可见执行；自动化生产或批处理流程不要求暴露每一步 GUI 操作，但必须把关键调用摘要、输入参数、输出路径、状态、错误和必要的 `flow_log` 写入当前 run 的 `logs/`、`stages/` 或 `status.json`，确保可审计、可复现、可追责
- 仓库内需要项目依赖的 Python 调试、验证、一次性调用，默认使用 `uv run python ...`；禁止直接依赖系统 `python`，除非确认该命令只用标准库且不触发项目依赖
- `get_1d_result(..., export_path=...)` 的导出格式仅允许 `.json`
- 禁止在生产流程中使用或依赖 S11 CSV 导出/CSV 对比
- 生成 S11 对比页必须优先调用 CLI/runtime 的 `generate-s11-comparison`
- 历史 S11 对比脚本已归档到 `archive/tools-legacy-20260421/generate_s11_comparison.py`，不作为生产流程默认入口
- 生产链路固定为：`get-1d-result(export_path=.json)` -> `generate-s11-comparison(file_paths=[...json...])`
- 不满足上述链路时，任务状态应标记为 `blocked` 并在日志中说明原因

### Skill 维护
- 当前维护的执行 Skill 为 `skills/cst-runtime-cli/SKILL.md`
- `skills/cst-simulation-optimization/` 流程已过时并移入备份；不得作为当前生产流程入口或 agent 生效副本继续分发
- 仓库内 `skills/` 是 Skill 唯一维护源；修改正式 Skill 时，必须先修改仓库内版本
- 需要刷新各 agent 的本地生效副本时，使用 `tools/sync_agent_skills.ps1` 从仓库 `skills/` 分发；具体目标目录说明放入 `docs/`，不写入本规则文件
- 不要只修改 `.codex`、`.opencode`、`.trae` 等 agent 生效副本而不回写仓库版本
