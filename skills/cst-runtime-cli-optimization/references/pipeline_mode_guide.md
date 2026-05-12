# Pipeline Mode Guide

This guide is the Phase 1 classification key for
`mcp_cli_tool_inventory.json`. It follows
`docs/runtime/mcp-cli-skill-migration-plan.md` and the reference CLI/MCP/Skill
development rules.

## Values

- `pipe_source`: read-only command that can start a JSON pipeline.
- `pipe_transform`: consumes JSON and emits JSON without durable side effects.
- `pipe_sink`: writes a file, report, preview, or audit artifact and should end
  or checkpoint a pipeline.
- `pipe_optional`: can be called standalone or in a pipeline with explicit
  status checks.
- `not_pipeable_session`: depends on CST GUI/session/lifecycle state.
- `not_pipeable_interactive`: needs human observation or confirmation.
- `not_pipeable_destructive`: write/process/destructive operation; stdin JSON
  may supplement args but must not silently trigger the action.
- `not_pipeable_large_output`: must return file paths or resource links instead
  of dumping large payloads to stdout.
- `blocked_existing_issue`: original tool is disabled, invalid, or cannot be
  classified until a separate fix task handles the known issue.

## Phase 1 Rules

- Static classification is not validation.
- CLI migration should not repair existing broken MCP behavior in the same task.
- MCP retention is allowed and expected for GUI-visible, long-running,
  permissioned, or protocol-native capabilities.
- A CLI replacement does not mean MCP production retirement.
