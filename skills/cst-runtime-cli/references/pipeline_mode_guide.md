# Pipeline Mode Guide

This guide records the pipeline-mode vocabulary that came out of the MCP to
CLI migration. The old `mcp_cli_tool_inventory.json` ledger is retired; current
tool metadata is discovered from the CLI itself with `list-tools` and
`describe-tool`.

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
- MCP retention fields belonged to the migration-period ledger and are no
  longer part of current runtime governance.
- A CLI replacement is now governed through the live CLI registry, Skill
  guidance, pipeline recipes, and validation records.
