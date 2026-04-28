---
marp: true
theme: default
paginate: true
size: 16:9
---

# CST_MCP 本周工作汇报

## 从 MCP-only 执行链到 CLI-first runtime 底座

**核心结论：**  
本周基础目标 P0 已完成并验证。真正的变化不是多了几个命令，而是系统底层从“依赖 MCP 工具实现和熟悉上下文”转向“共享 runtime + CLI 主调用界面 + MCP 兼容 adapter”的架构。

<!--
讲述重点：
不要从“我做了很多功能”开场，而是从架构变化开场。
本周的主要价值是底层执行能力可迁移、可审计、可被低上下文 agent 调用。
-->

---

# 本周之前的问题

## MCP-only 链路能跑，但不够适合作为长期底座

- 生产能力主要沉在 `mcp/*.py` 和熟悉的 MCP 调用链里
- 其他 agent 需要知道大量上下文，才能正确调用工具
- GUI 可见 tool call 便于人工确认，但不适合批处理和低上下文迁移
- 临时脚本、旧 `tools/` 入口、`prototype_optimizer` 容易形成旁路生产链
- 结果读取、导出、状态落盘分散时，难以审计、复现和扩展

**核心矛盾：**  
生产能力还没有从 MCP adapter 中抽出稳定核心层，而低上下文执行要求同一能力能被非 MCP 入口可靠调用。

<!--
这一页要讲“为什么必须重构”，不是否定 MCP。
MCP 在前期是有效生产链，但如果目标是可迁移、非特定 agent 依赖，就需要更底层的 runtime。
-->

---

# 本周的架构判断

## CLI 不是第二条生产链，而是 runtime 的主要调用界面

```text
正式任务入口保持不变

tasks/task_xxx_slug/
  -> runs/run_xxx/{projects,exports,logs,stages,analysis}
  -> Skill / agent 判断层
  -> cst_runtime/ 共享能力层
       -> CLI adapter: python -m cst_runtime
       -> MCP adapter: 稳定生产链与兼容层
```

**边界：**

- `tasks/task_xxx_slug/` 仍是正式任务入口
- `cst_runtime/` 承载共享执行能力
- CLI 面向人和 agent，提供可发现、可脚本化、机器可解析的接口
- MCP 暂时保留为稳定生产链和兼容 adapter，成熟后逐步退场

<!--
这里要特别强调：不是“抛弃 MCP”，而是“把业务能力从 MCP 适配层下沉到 runtime”。
这能避免同时存在两条业务规则不同的链路。
-->

---

# 为什么 CLI 更适合做 agent 底座

## CLI 的优势不是命令行本身，而是接口契约更适合自动化

| 维度 | MCP-only 侧重点 | CLI-first runtime 侧重点 |
| --- | --- | --- |
| 调用方式 | 工具会话 / GUI 可见 tool call | `python -m cst_runtime <tool>` |
| 上下文依赖 | 依赖会话、工具注册和熟悉流程 | 可通过 `doctor`、`usage-guide`、`describe-tool` 自发现 |
| 输入输出 | MCP 返回结构 | JSON 输入、JSON stdout、明确退出状态 |
| 批处理 | 不够自然 | 原生适合脚本、管道、CI、其他 agent |
| 审计 | 需要额外约束 | 每次生产调用写入 `logs/`、`stages/`、`status.json` |
| 迁移 | 依赖 MCP server 配置 | 可从 CLI 自检开始降低环境不确定性 |

**一句话：**  
CLI 让能力从“某个工具会话里能用”变成“任何低上下文执行者可以发现、调用、检查和复现”。

---

# 本周落地的 CLI/runtime 能力

## 让其他 agent 不靠猜也能用

- `doctor`：检查运行环境与依赖状态
- `usage-guide`：给低上下文 agent 的入口说明
- `list-tools` / `describe-tool`：工具发现与参数说明
- `args-template`：生成参数模板，减少 PowerShell 手写 JSON 出错
- `--args-file` / `--args-json`：显式输入
- `--args-stdin`：需要管道合并时才读 stdin
- 结构化 JSON 错误：误用也返回可解析结果，而不是裸 argparse 文本
- `captured_stdout`：捕获工具内部 stdout，避免污染管道 JSON

**工程价值：**  
把“agent 会不会用”从经验问题变成接口契约问题。

<!--
这里可以现场展示一行命令：
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime args-template --tool open-project --output args.json
-->

---

# 原生管道协议

## CLI 支持工具串联，但保留 agent 判断点

```powershell
uv run python -m cst_runtime doctor
uv run python -m cst_runtime usage-guide
uv run python -m cst_runtime describe-tool --tool <tool>
uv run python -m cst_runtime args-template --tool <tool> --output args.json
uv run python -m cst_runtime <tool> --args-file args.json
```

管道合并规则：

```text
final_args = stdin_json + explicit_args
同名字段以显式参数为准
```

关键约束：

- 有 `--args-file` / `--args-json` 时默认不读 stdin，避免非 TTY 环境阻塞
- 只有显式 `--args-stdin` 才合并上游 JSON
- 每一步仍检查 `status`，不把长流程压成不可审计黑盒

<!--
这一页要突出“CLI-first 不等于一条脚本跑到底”。
系统仍然保留小粒度工具和 agent 判断点，这和项目规则一致。
-->

---

# 从 MCP 功能迁移到 runtime 的范围

## 本周迁移的是优化闭环运行能力，不是几何建模能力

已迁入或补齐：

- run 目录推断、项目身份、锁检查
- 参数读写、项目打开/关闭、仿真启动与轮询
- results run_id / 参数组合 / 1D 结果导出
- S11 JSON 导出与 HTML 对比
- farfield ASCII/TXT 解析与 HTML 预览
- fresh-session farfield 导出与 `Realized Gain[dBi]` 网格读取
- CST 进程清理证据与 `Access is denied` 非阻塞残留记录

明确不迁移：

- 几何建模、材料、边界、网格等建模类 MCP 工具
- 旧 `prototype_optimizer` 的 SQLite 状态系统和模拟 orchestrator
- 旧 `tools/` 旁路脚本作为默认入口

---

# 验证一：Trae 低上下文 CLI-only 闭环

## 证明其他 agent 能按 CLI/Skill 跑通流程

验证对象：

- `tasks/task_009_ref0_cli_low_context_validation/run_001`
- 状态：`validated`

验证流程：

1. 创建标准 run 工作区
2. 打开 `ref_0` 工作副本并校验工程身份
3. 读取参数，修改 `g = 24.5`
4. 启动真实仿真并轮询完成
5. 关闭工程并确认当前 run 无 `.lok`
6. 通过 results CLI 读取 S11，导出 JSON
7. 生成 `s11_comparison.html`

关键结果：

- `run2` 最小 S11：`-63.591 dB`
- 最佳频点：`10.476 GHz`

<!--
这一页最好配一张 s11_comparison.html 截图。
表达口径：这关闭了“第三方 coding agent 低上下文端到端验证”缺口。
-->

---

# 验证二：fresh-session 真实 CST 远场验证

## 证明远场不是只完成代码迁移，而是真实 CST 链路可用

验证对象：

- `tasks/task_010_ref0_fresh_session_farfield_validation/run_001`
- 状态：`validated`

验证配置：

- 参考模型：`ref_0`
- 频率：`10 GHz`
- farfield：`farfield (f=10) [1]`
- 数据源：`FarfieldCalculator`
- 数量：`Realized Gain`
- 单位：`dBi`
- 范围：full sphere
- 网格：theta `0..180 deg`，phi `0..355 deg`，步进 `5 deg`

关键结果：

- 样本数：`2664`
- 峰值 realized gain：`14.1447 dBi`
- boresight realized gain：`14.1447 dBi`
- TXT 表头：`Abs(Realized Gain)[dBi]`

<!--
这一页要强调没有用 Abs(E) 代理 dBi 增益。
这对技术可信度很重要。
-->

---

# 本周 P0 完成面

## 基础目标已完成并标记为 validated

| 阶段 | 结果 | 说明 |
| --- | --- | --- |
| A | 完成 | 正式入口与旁路冻结 |
| B | 完成 | 主生产链收口并通过 MCP 验证 |
| C | 完成 | MCP / Skill / 知识 / 计划系统职责打通 |
| D | 完成 | CLI-first 架构门控、低上下文验证、真实远场验证 |

本周完成的结构性变化：

- 正式入口回到 `tasks/task_xxx_slug/`
- 核心执行能力开始下沉到 `cst_runtime/`
- CLI 成为主要 agent 调用界面
- MCP 保留为稳定生产链和兼容 adapter
- 旧旁路脚本和旧原型边界被收口

---

# 这次重构的实际价值

## 从“能跑”推进到“能迁移、能审计、能被其他 agent 复现”

1. **降低对特定 agent 的依赖**  
   其他 agent 可以从 `doctor`、`usage-guide`、`describe-tool`、`args-template` 开始执行。

2. **降低对 GUI tool call 可见性的依赖**  
   自动化流程可以通过 JSON 返回、日志、阶段文件和状态文件审计。

3. **降低旁路流程污染**  
   旧 `tools/` 脚本归档，`prototype_optimizer` 退出默认主线。

4. **提高验证硬度**  
   不只验证代码存在，还验证真实仿真、真实 S11、真实 farfield `Realized Gain[dBi]`。

5. **为后续 P1 留出清晰接口**  
   优化指导可以调用稳定 CLI/runtime，而不是直接依赖聊天上下文或旧脚本。

---

# 需要保持克制的边界

## 当前不是宣称 MCP 已经完全退场

不能夸大的地方：

- MCP 仍是稳定生产链和兼容 adapter
- CLI/runtime 虽然已完成 P0 验证，但新模型、新指标、新远场任务仍需按任务重新验证
- 几何建模、材料、边界、网格类工具没有迁移
- P1 优化指导原型尚未启动

正确表述：

> 本周完成的是 CLI-first runtime 底座的 P0 验证。系统已经从 MCP-only 依赖中抽出了共享能力层，但 MCP 仍保留为稳定兼容路径，后续按能力覆盖和验证结果逐步退场。

---

# 下一步选择

## P0 后加固 or P1 优化指导原型

路线 A：先做 P0 后加固

- CST 连接诊断
- 锁文件检测
- `Access is denied` 清理证据
- 参数一致性与严格校验
- 更完整的端到端示例和故障排除说明

路线 B：进入 P1 优化指导原型

- 读取建模代码，识别天线结构和参数线索
- 主动询问缺失需求、约束和目标指标
- 围绕具体任务检索与研读论文
- 输出面向当前任务的结构化优化建议

建议：

> 先做一次门控复盘，再决定进入 P1 还是先补 P0 后加固。不要在未确认的情况下自动启动新主线。

---

# 汇报收束口径

## 建议最后这样总结

本周工作的核心不是“多做了一套 CLI 命令”，而是完成了一次底层执行架构的转向：

```text
MCP 工具实现中心
  -> 共享 cst_runtime 能力层
  -> CLI 作为主要 agent 调用界面
  -> MCP 作为稳定生产链和兼容 adapter
```

这个转向带来的直接收益是：

- 低上下文 agent 可以复现
- 调用过程可审计
- 标准 run 产物可追溯
- 远场和 S11 都经过真实 CST 验证
- 后续优化指导功能有更稳定的底座

**最终结论：P0 已完成，P1 是否启动需要单独门控确认。**

