# MCP/CLI/Skill 迁移计划

> 本文按 `docs/reference/agent_skill_development_rules.md`、`docs/reference/cli_development_rules.md`、`docs/reference/mcp_tool_development_rules.md` 的通用开发标准制定。  
> 本文不是项目规则源，也不替代具体工具实现。它用于指导后续 MCP 工具向 CLI/Skill 结构迁移时如何分类、验收和记录。

## 1. 结论

迁移目标应从“所有 MCP 工具强行改成可管道 CLI 命令”调整为：

**全量纳管、分类迁移、显式标记管道适配性、保留必要 MCP 能力、问题工具只登记不修复。**

核心判断：

- CLI 是稳定本地接口，应满足显式输入、非交互、机器可读输出、稳定字段、稳定 exit code、stdout/stderr 分离、可诊断错误、危险操作 dry-run 或确认机制。
- Skill 是指导层，不是执行层；`SKILL.md` 只写流程、判断、验收和失败处理，工具实现放入 `scripts/`，长清单和台账放入 `references/`。
- MCP 仍适合协议化能力，包括模型可发现工具、资源上下文、权限控制、进度、取消、长任务、GUI/host 可见调试和需要 client 参与确认的能力。
- 管道适配不是所有工具的硬要求；每个工具必须标记 `pipeline_mode`，不适合管道的工具应显式说明原因。
- 原 MCP 工具本来有问题、无法通过实测的，不在迁移任务中顺手修复，只记录为 `blocked_existing_issue`。

## 2. 目标结构

推荐 Skill 包结构：

```text
skills/cst-runtime-cli-optimization/
  SKILL.md
  scripts/
    cst_runtime_cli.py
    cst_runtime/
      cli.py
      modeler.py
      results.py
      farfield.py
      ...
  references/
    mcp_cli_tool_inventory.json
    mcp_cli_migration_status.md
    pipeline_mode_guide.md
  tests/
    test_cli_contract.py
    cases/
```

职责边界：

- `SKILL.md`：触发条件、推荐流程、风险判断、验收口径、失败报告格式。
- `scripts/`：确定性 CLI 实现和辅助脚本。
- `references/`：工具清单、迁移状态、长说明、问题记录。
- `tests/`：CLI contract、golden output、错误分支、低上下文调用测试。
- MCP server：保留为协议 adapter、Resource/Prompt/Tool 暴露层、进度/取消/权限/GUI 可见调试入口。

## 3. 工具分类与状态字段

每个 MCP/CLI 工具进入统一台账，至少包含：

```json
{
  "name": "tool-name",
  "source": "mcp/advanced_mcp.py",
  "category": "modeler",
  "risk": "write",
  "cli_status": "implemented_needs_validation",
  "pipeline_mode": "not_pipeable_destructive",
  "mcp_retention": "adapter_only",
  "validation_status": "not_run",
  "known_issue": "",
  "replacement": "",
  "notes": ""
}
```

`cli_status` 取值：

- `implemented_validated`：CLI 已实现且通过对应验收。
- `implemented_needs_validation`：CLI 已实现，但尚未实测。
- `not_migrated`：尚未迁移。
- `not_migrated_needs_design`：迁移前需要重新设计输入、session、权限或输出。
- `disabled_with_replacement`：不应继续作为可用入口，只返回结构化 error 和替代方案。
- `blocked_existing_issue`：原 MCP 工具已有问题，暂不修复，只记录证据。

`pipeline_mode` 取值：

- `pipe_source`：适合作为管道起点，输出结构化 JSON。
- `pipe_transform`：适合消费 stdin JSON 并输出新 JSON。
- `pipe_sink`：适合作为管道终点，通常会落盘或生成产物。
- `pipe_optional`：可管道，也可独立调用。
- `not_pipeable_session`：依赖 live session、GUI 状态、锁或长生命周期上下文，不适合作为普通管道节点。
- `not_pipeable_interactive`：需要人工观察、选择或确认。
- `not_pipeable_destructive`：危险写操作，不应从上游 JSON 直接执行，必须显式参数和确认。
- `not_pipeable_large_output`：输出过大，应返回文件路径或 resource link，而不是直接进入 stdout 管道。
- `blocked_existing_issue`：原工具问题导致无法判断或无法验收。

`mcp_retention` 取值：

- `adapter_only`：MCP 只包装 CLI/core 能力。
- `mcp_preferred`：短期更适合保留 MCP 调用面。
- `resource_preferred`：更适合作为 MCP Resource，而不是 CLI tool。
- `prompt_or_skill_preferred`：更适合作为 Prompt 或 Skill 流程，不应做成执行工具。
- `retire`：应退场或只保留禁用提示。

## 4. CLI 合格标准

每个 CLI 命令至少满足：

- 支持 `--help`；整体 CLI 支持 `--version` 或等价 version 命令。
- 关键输入显式传入，或来自清晰、可解释的配置来源。
- 支持非交互执行；交互 prompt 只能作为辅助。
- 涉及状态、结果、查询、导出、诊断时支持稳定 JSON 输出。
- stdout 只输出主要结果；日志、进度、warning、debug 信息不得污染 JSON。
- 错误可诊断，机器模式下错误也应结构化。
- exit code 稳定并文档化。
- 写入、删除、发布、远端修改、模型结构修改等危险操作应支持 `--dry-run` 或显式确认。
- JSON 字段名稳定；破坏性变更必须进入版本升级或迁移说明。

当前已有 `list-tools`、`describe-tool`、`args-template` 的工具，可以保留这种 agent-friendly 发现机制；但它不能替代标准 `--help`、版本、exit code、非交互和 dry-run 要求。

## 5. MCP 保留条件

满足以下条件之一时，不应为了“全量 CLI 化”强行移除 MCP 面：

- 工具主要用于模型自动发现和选择，且需要清晰 schema/description。
- 工具是长任务，需要 progress notification、cancellation、timeout 或 host 侧任务管理。
- 工具涉及权限、确认、鉴权、scope、用户授权或高风险副作用。
- 输出是大文件、大日志、图像或资源上下文，更适合作为 MCP Resource 或 resource link。
- 能力本质是用户选择的工作流模板，更适合作为 MCP Prompt 或 Skill。
- 工具需要 GUI/host 可见调试，或需要用户在客户端观察执行过程。
- CLI 只能提供本地批处理入口，而 MCP 能提供更好的审计、协议兼容或 agent host 集成。

保留 MCP 不等于保留双重业务实现。优先形态是：

```text
Skill 决策层
  -> CLI/scripts 执行动作
  -> MCP adapter 暴露协议化调用、资源、进度、取消和 host 可见能力
```

## 6. 管道适配原则

不是所有工具都应做成管道节点。判断标准：

- 读查询、inspect、list、parse、plot plan、derive 类工具通常适合 `pipe_source` 或 `pipe_transform`。
- export、generate、write-summary 类工具通常适合 `pipe_sink`。
- 启动仿真、打开/关闭工程、修改模型、boolean、mesh、solver、port、monitor 等有 session 或写副作用的工具，默认不标为管道友好。
- 这类工具即使支持 `--args-stdin`，也只能作为参数补充方式；仍必须要求显式 `project_path`、确认、审计和错误记录。
- 大结果不要直接管道传递；应输出文件路径、摘要和校验信息。
- 管道链路必须在每一步检查 JSON `status`；任一步失败时停止，除非下一步是明确恢复动作。

## 7. 问题工具记录策略

迁移过程中发现原 MCP 工具本来就有问题时，不进入修复范围。只做登记：

```json
{
  "cli_status": "blocked_existing_issue",
  "validation_status": "failed",
  "source_mcp_tool": "tool-name",
  "attempted_cli_command": "...",
  "failure_output": "...",
  "evidence_path": "logs/or/stages/path",
  "reason": "原工具无法完成实测，不在本轮迁移中修复",
  "recommended_next_action": "另开修复任务",
  "do_not_claim_validated": true
}
```

记录要求：

- 不把失败工具标为 `implemented_validated`。
- 不在迁移任务中顺手修复历史 bug。
- 不隐藏失败；必须保留可复查的错误输出、参数和环境摘要。
- 如已有替代入口，标记 `disabled_with_replacement` 并说明替代工具。

## 8. 实施阶段

### Phase 1：清点与标准化

- 生成 MCP tool inventory。
- 生成现有 CLI tool inventory。
- 建立统一状态字段：`cli_status`、`pipeline_mode`、`mcp_retention`、`validation_status`。
- 对每个工具先分类，不立即改实现。

完成信号：

- 有完整台账。
- 每个工具都有迁移状态、管道适配状态和 MCP 保留判断。

### Phase 2：CLI contract 补齐

- 补齐 `--help`、version、exit code 文档。
- 明确默认 JSON 模式，或增加 `--json` / `--format json`。
- 补齐 stdout/stderr 分离测试。
- 为写操作设计 `--dry-run` 或显式确认策略。

完成信号：

- CLI contract 测试通过。
- 低上下文 agent 能通过 `usage-guide -> list-tools -> describe-tool -> args-template` 调用。

### Phase 3：Skill 结构归位

- 将 CLI 实现放入 Skill `scripts/`。
- 将工具台账和长说明放入 Skill `references/`。
- `SKILL.md` 只保留核心流程和判断。
- 增加 Skill/CLI 测试入口。

完成信号：

- 低上下文 agent 不依赖游离目录即可找到入口。
- `SKILL.md` 不因工具数量增长而臃肿。

### Phase 4：分类迁移

优先迁移：

- read-only 查询类。
- 结果解析、inspect、plot、dashboard 类。
- 低风险 export 和文件产物生成类。

谨慎迁移：

- session 生命周期工具。
- CST 工程写操作。
- 建模、mesh、solver、port、monitor 类工具。

暂不修复：

- 原工具实测失败。
- 语义不清。
- 依赖隐式 GUI/session 状态且无法稳定重连。
- 已被替代或应禁用的旧入口。

完成信号：

- 每一批迁移都有状态更新、测试记录和失败登记。

### Phase 5：分层验收

验收分层：

- `static_contract`：help/version/list/describe/template/JSON schema。
- `dry_run`：危险操作预览不产生副作用。
- `mock_or_parse`：纯解析和文件生成工具。
- `cst_smoke`：代表性 CST 实机测试。
- `workflow`：完整闭环验证。

完成信号：

- 每个工具至少有一个 validation_status。
- `blocked_existing_issue` 工具有证据，不被计入通过率。
- workflow 级验收独立记录，不替代单工具状态。

## 9. 当前执行状态（2026-05-03）

本计划已完成一次受控执行，记录见：
[`mcp-cli-skill-migration-execution-2026-05-03.md`](./mcp-cli-skill-migration-execution-2026-05-03.md)。

已完成：

1. Phase 1 静态台账生成与初始分类。
2. Phase 2 CLI contract 补齐：`--version`、help 示例、默认 JSON 输出说明、exit code 说明。
3. Phase 3 Skill 结构归位：`scripts/`、`references/`、`tests/` 已落入 `skills/cst-runtime-cli-optimization/`，并同步 `.codex` 生效副本。
4. Phase 4 首批低风险迁移：`generate_s11_farfield_dashboard` 已迁入 `cst_runtime`，CLI 入口为 `generate-s11-farfield-dashboard`。
5. Phase 5 分层验收：`static_contract` 与 `mock_or_parse` 已通过；`cst_smoke` 与 `workflow` 仍是独立待验证项。

补充执行结论：

- `modeler session` 与 `results 上下文` 可以由 CLI 管理，但必须显式传入 `project_path`，并保留身份校验、锁释放、刷新和错误落盘；这类工具默认不是普通管道节点。
- 已新增 `list-entities`、`list-subprojects`、`plot-project-result`，并将 `load_subproject` / `reset_to_root_project` 收敛为显式 `subproject_treepath` 参数语义。
- 当前台账显示 CLI tools 为 `37`，已实现或有替代映射为 `42`，`not_migrated_needs_design` 为 `58`。

当前台账入口：

- `skills/cst-runtime-cli-optimization/references/mcp_cli_tool_inventory.json`
- `skills/cst-runtime-cli-optimization/references/mcp_cli_migration_status.md`
- `skills/cst-runtime-cli-optimization/references/pipeline_mode_guide.md`

当前验证入口：

```powershell
uv run python skills\cst-runtime-cli-optimization\scripts\generate_mcp_cli_inventory.py
uv run python -m unittest discover -s skills\cst-runtime-cli-optimization\tests
```

## 10. 后续 gate

下一批迁移前必须先审阅台账，不允许直接扩大实现范围。

优先候选仍然只限：

1. read-only 查询。
2. 结果解析、inspect、plot、dashboard。
3. 低风险文件产物生成。

禁止把以下事项作为“顺手迁移”处理：

1. session 生命周期工具。
2. CST 工程写操作。
3. 建模、mesh、solver、port、monitor 类工具。
4. 原 MCP 工具本身已有问题的修复。
5. 需要 GUI/host 可见调试或用户确认的工具退场。

任何新迁移项必须至少给出一个 `validation_status`；真实 CST 实机或完整 workflow 验证必须单独记录，不能用文件级测试替代。
