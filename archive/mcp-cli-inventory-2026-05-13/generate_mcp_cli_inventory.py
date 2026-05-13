"""Generate MCP/CLI migration inventory for the CST runtime skill.

This script is intentionally read-only against MCP/runtime source files. It
builds a first-pass migration ledger for Phase 1 of
docs/runtime/mcp-cli-skill-migration-plan.md.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = Path(__file__).resolve().parent
DEFAULT_REFERENCES_DIR = SKILL_ROOT / "references"


def find_workspace_root(explicit_workspace: str = "") -> Path:
    if explicit_workspace:
        return Path(explicit_workspace).expanduser().resolve()
    env_workspace = os.environ.get("CST_MCP_WORKSPACE", "").strip()
    if env_workspace:
        return Path(env_workspace).expanduser().resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cst_mcp_runtime" / "workspace.json").exists():
            return candidate
        if (candidate / "mcp" / "advanced_mcp.py").exists():
            return candidate
    return current


REPO_ROOT = find_workspace_root()
MCP_SOURCES = (
    REPO_ROOT / "mcp" / "advanced_mcp.py",
    REPO_ROOT / "mcp" / "cst_results_mcp.py",
)

SPECIAL_REPLACEMENTS = {
    "prepare_new_run": "prepare-run",
    "record_run_stage": "record-stage",
    "update_run_status": "update-status",
    "quit_cst": "cleanup-cst-processes",
    "get_project_context_info": "open-results-project",
    "export_farfield": "export-farfield-fresh-session",
    "plot_project_result": "plot-project-result",
    "list_entities": "list-entities",
    "list_subprojects": "list-subprojects",
    "load_subproject": "open-results-project",
    "reset_to_root_project": "open-results-project",
}

DISABLED_OR_RETIRED = {
    "export_s_parameter": {
        "cli_status": "disabled_with_replacement",
        "replacement": "get-1d-result -> generate-s11-comparison",
        "known_issue": "Production S11 CSV/export_s_parameter path is forbidden by AGENTS.md; use JSON result chain.",
    },
}

VALIDATION_OVERRIDES = {
    "generate_s11_farfield_dashboard": {
        "validation_status": "mock_or_parse",
        "notes_suffix": "File-only CLI migration is covered by tests/test_cli_contract.py; real CST workflow remains separate.",
    },
    "generate-s11-farfield-dashboard": {
        "validation_status": "mock_or_parse",
        "notes_suffix": "File-only CLI migration is covered by tests/test_cli_contract.py; real CST workflow remains separate.",
    },
    "define_brick": {"validation_status": "implemented_validated"},
    "define_cylinder": {"validation_status": "implemented_validated"},
    "define_cone": {"validation_status": "implemented_validated"},
    "create_component": {"validation_status": "implemented_validated"},
    "delete_entity": {"validation_status": "implemented_validated"},
    "boolean_subtract": {"validation_status": "implemented_validated"},
    "boolean_add": {"validation_status": "implemented_validated"},
    "define_frequency_range": {"validation_status": "implemented_validated"},
    "change_solver_type": {"validation_status": "implemented_validated"},
    "define-brick": {"validation_status": "implemented_validated"},
    "define-cylinder": {"validation_status": "implemented_validated"},
    "define-cone": {"validation_status": "implemented_validated"},
    "create-component": {"validation_status": "implemented_validated"},
    "delete-entity": {"validation_status": "implemented_validated"},
    "boolean-subtract": {"validation_status": "implemented_validated"},
    "boolean-add": {"validation_status": "implemented_validated"},
    "boolean_intersect": {"validation_status": "implemented_validated"},
    "boolean_insert": {"validation_status": "implemented_validated"},
    "boolean-intersect": {"validation_status": "implemented_validated"},
    "boolean-insert": {"validation_status": "implemented_validated"},
    "define_frequency_range": {"validation_status": "implemented_validated"},
    "change_frequency_range": {"validation_status": "implemented_validated"},
    "change-frequency-range": {"validation_status": "implemented_validated"},
    "define_rectangle": {"validation_status": "implemented_validated"},
    "define-rectangle": {"validation_status": "implemented_validated"},
    "define_background": {"validation_status": "implemented_validated"},
    "define_boundary": {"validation_status": "implemented_validated"},
    "define_solver": {"validation_status": "implemented_validated"},
    "change_solver_type": {"validation_status": "implemented_validated"},
    "change-solver-type": {"validation_status": "implemented_validated"},
    "define_mesh": {"validation_status": "implemented_validated"},
    "define_port": {"validation_status": "implemented_validated"},
    "define-port": {"validation_status": "implemented_validated"},
    "rename_entity": {"validation_status": "implemented_validated"},
    "rename-entity": {"validation_status": "implemented_validated"},
    "set_entity_color": {"validation_status": "implemented_validated"},
    "set-entity-color": {"validation_status": "implemented_validated"},
    "define-frequency-range": {"validation_status": "implemented_validated"},
    "define-background": {"validation_status": "implemented_validated"},
    "define-boundary": {"validation_status": "implemented_validated"},
    "define-solver": {"validation_status": "implemented_validated"},
    "define-mesh": {"validation_status": "implemented_validated"},
    "define-monitor": {"validation_status": "needs_validation", "notes_suffix": "CST 2026 VBA .SetName incompatible; needs VBA fix."},
    "change_material": {"validation_status": "implemented_validated"},
    "change-material": {"validation_status": "implemented_validated"},
    "define_units": {"validation_status": "implemented_validated"},
    "set_farfield_monitor": {"validation_status": "implemented_validated"},
    "show_bounding_box": {"validation_status": "implemented_validated"},
    "define-units": {"validation_status": "implemented_validated"},
    "set-farfield-monitor": {"validation_status": "implemented_validated"},
    "show-bounding-box": {"validation_status": "implemented_validated"},
    "create-blank-project": {"validation_status": "implemented_validated"},
}

RISK_OVERRIDES = {
    "init_cst_project": "write",
    "export_e_field_data": "session",
    "export_surface_current_data": "session",
    "export_voltage_data": "session",
}

CLASSIFICATION_NOTES = {
    "init_cst_project": "Creates and saves a new CST project and mutates MCP global state; it is not a read-only pipe source.",
    "export_e_field_data": "Uses the implicit active project plus add_to_history/SelectTreeItem, so it needs an explicit project_path/results design before CLI migration.",
    "export_surface_current_data": "Uses the implicit active project plus add_to_history/SelectTreeItem, so it needs an explicit project_path/results design before CLI migration.",
    "export_voltage_data": "Uses the implicit active project plus add_to_history/SelectTreeItem, so it needs an explicit project_path/results design before CLI migration.",
}

MCP_ONLY_PREFERRED = {
    "pause_simulation",
    "resume_simulation",
    "stop_simulation",
    "add_to_history",
    "init_cst_project",
    "export_e_field_data",
    "export_surface_current_data",
    "export_voltage_data",
    "plot_project_result",
    "generate_s11_farfield_dashboard",
}

RESOURCE_OR_CONTEXT_TOOLS = {
    "get_project_context_info",
    "list_subprojects",
    "load_subproject",
    "reset_to_root_project",
}

SESSION_NAMES = {
    "open_project",
    "close_project",
    "save_project",
    "quit_cst",
    "start_simulation",
    "start_simulation_async",
    "is_simulation_running",
    "pause_simulation",
    "resume_simulation",
    "stop_simulation",
}

READ_PREFIXES = (
    "get_",
    "list_",
    "inspect_",
    "calculate_",
    "read_",
)

WRITE_PREFIXES = (
    "prepare_",
    "record_",
    "update_",
    "generate_",
    "plot_",
    "export_",
)

MODELER_WRITE_PREFIXES = (
    "define_",
    "create_",
    "set_",
    "change_",
    "delete_",
    "boolean_",
    "transform_",
    "rename_",
    "parameter_",
    "activate_",
    "pick_",
    "show_",
)


def _is_mcp_tool_decorator(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "tool"
        and isinstance(func.value, ast.Name)
        and func.value.id == "mcp"
    )


def _doc_summary(node: ast.FunctionDef) -> str:
    doc = ast.get_docstring(node) or ""
    if not doc:
        return ""
    return " ".join(doc.strip().split())[:220]


def discover_mcp_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for source in MCP_SOURCES:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any(_is_mcp_tool_decorator(item) for item in node.decorator_list):
                continue
            tools.append(
                {
                    "name": node.name,
                    "source": str(source.relative_to(REPO_ROOT)).replace("\\", "/"),
                    "line": node.lineno,
                    "category": _category_from_source_and_name(source.name, node.name),
                    "doc_summary": _doc_summary(node),
                }
            )
    return sorted(tools, key=lambda item: (item["source"], item["line"], item["name"]))


def discover_cli_tools() -> dict[str, dict[str, Any]]:
    sys.path.insert(0, str(SCRIPTS_ROOT))
    from cst_runtime.cli import TOOLS  # type: ignore

    return {name: dict(record) for name, record in sorted(TOOLS.items())}


def _category_from_source_and_name(source_name: str, name: str) -> str:
    if source_name == "cst_results_mcp.py":
        if "farfield" in name or "gain" in name:
            return "farfield"
        return "results"
    if name in {"prepare_new_run", "get_run_context"}:
        return "run"
    if name in {"record_run_stage", "update_run_status"}:
        return "audit"
    if name == "quit_cst":
        return "process_cleanup"
    if name in SESSION_NAMES:
        return "modeler"
    if name.startswith(READ_PREFIXES):
        return "modeler-read"
    return "modeler"


def _snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


def _replacement_for(name: str, cli_tools: dict[str, dict[str, Any]]) -> str:
    special = SPECIAL_REPLACEMENTS.get(name)
    if special and special in cli_tools:
        return special
    kebab = _snake_to_kebab(name)
    if kebab in cli_tools:
        return kebab
    return ""


def _risk_for(name: str, category: str, source: str, cli_record: dict[str, Any] | None) -> str:
    if name in RISK_OVERRIDES:
        return RISK_OVERRIDES[name]
    if cli_record:
        return str(cli_record.get("risk", ""))
    if name in SESSION_NAMES:
        return "session"
    if name.startswith(WRITE_PREFIXES):
        return "filesystem-write"
    if source.endswith("advanced_mcp.py") and (
        name.startswith(MODELER_WRITE_PREFIXES) or name in {"add_to_history"}
    ):
        return "write"
    if "farfield" in name:
        return "long-running"
    return "read"


def _pipeline_mode_for(name: str, risk: str, source: str, replacement: str) -> str:
    if name in DISABLED_OR_RETIRED:
        return "blocked_existing_issue"
    if risk in {"read"}:
        return "pipe_source"
    if risk == "filesystem-write":
        return "pipe_sink"
    if risk == "long-running":
        return "not_pipeable_session"
    if risk == "process-control":
        return "not_pipeable_destructive"
    if risk == "session":
        return "not_pipeable_session"
    if risk == "write":
        return "not_pipeable_destructive"
    if source.endswith("advanced_mcp.py") and not replacement:
        return "not_pipeable_session"
    return "pipe_optional"


def _mcp_retention_for(name: str, source: str, replacement: str, risk: str) -> str:
    if name in DISABLED_OR_RETIRED:
        return "retire"
    if name in RESOURCE_OR_CONTEXT_TOOLS:
        return "resource_preferred"
    if name in MCP_ONLY_PREFERRED:
        return "mcp_preferred"
    if replacement:
        if risk in {"long-running", "session", "write", "process-control"}:
            return "mcp_preferred"
        return "adapter_only"
    if source.endswith("advanced_mcp.py") and risk == "write":
        return "mcp_preferred"
    return "not_decided"


def build_inventory() -> dict[str, Any]:
    mcp_tools = discover_mcp_tools()
    cli_tools = discover_cli_tools()
    cli_by_name = set(cli_tools)
    covered_cli_tools: set[str] = set()
    records: list[dict[str, Any]] = []

    for tool in mcp_tools:
        name = str(tool["name"])
        replacement = _replacement_for(name, cli_tools)
        if replacement:
            covered_cli_tools.add(replacement)
        cli_record = cli_tools.get(replacement) if replacement else None
        risk = _risk_for(name, str(tool["category"]), str(tool["source"]), cli_record)
        disabled = DISABLED_OR_RETIRED.get(name, {})
        cli_status = disabled.get(
            "cli_status",
            "implemented_needs_validation" if replacement else "not_migrated_needs_design",
        )
        pipeline_mode = _pipeline_mode_for(name, risk, str(tool["source"]), replacement)
        record = {
            "name": name,
            "source": tool["source"],
            "line": tool["line"],
            "category": tool["category"],
            "risk": risk,
            "cli_status": cli_status,
            "pipeline_mode": pipeline_mode,
            "mcp_retention": _mcp_retention_for(name, str(tool["source"]), replacement, risk),
            "validation_status": VALIDATION_OVERRIDES.get(name, {}).get("validation_status", "static_inventory_only"),
            "known_issue": disabled.get("known_issue", ""),
            "replacement": disabled.get("replacement", replacement),
            "notes": " ".join(
                item
                for item in [
                    str(tool.get("doc_summary", "")),
                    CLASSIFICATION_NOTES.get(name, ""),
                    VALIDATION_OVERRIDES.get(name, {}).get("notes_suffix", ""),
                ]
                if item
            ),
        }
        records.append(record)

    for name in sorted(cli_by_name - covered_cli_tools):
        cli_record = cli_tools[name]
        risk = str(cli_record.get("risk", ""))
        records.append(
            {
                "name": name,
                "source": "scripts/cst_runtime/cli.py",
                "line": None,
                "category": cli_record.get("category", ""),
                "risk": risk,
                "cli_status": "implemented_needs_validation",
                "pipeline_mode": _pipeline_mode_for(name, risk, "scripts/cst_runtime/cli.py", name),
                "mcp_retention": "cli_native",
                "validation_status": VALIDATION_OVERRIDES.get(name, {}).get("validation_status", "static_inventory_only"),
                "known_issue": "",
                "replacement": "",
                "notes": " ".join(
                    item
                    for item in [
                        str(cli_record.get("description", "")),
                        VALIDATION_OVERRIDES.get(name, {}).get("notes_suffix", ""),
                    ]
                    if item
                ),
            }
        )

    summary = {
        "total_records": len(records),
        "mcp_tool_count": len(mcp_tools),
        "cli_tool_count": len(cli_tools),
        "implemented_or_replaced": sum(1 for item in records if item["cli_status"].startswith("implemented")),
        "not_migrated_needs_design": sum(1 for item in records if item["cli_status"] == "not_migrated_needs_design"),
        "disabled_or_blocked": sum(
            1
            for item in records
            if item["cli_status"] in {"disabled_with_replacement", "blocked_existing_issue"}
            or item["pipeline_mode"] == "blocked_existing_issue"
        ),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "skills/cst-runtime-cli-optimization/scripts/generate_mcp_cli_inventory.py",
        "status": "phase1_static_inventory",
        "scope": "MCP tool decorators plus current cst_runtime CLI tool registry.",
        "summary": summary,
        "records": sorted(records, key=lambda item: (str(item["source"]), item["name"])),
    }


def write_markdown(inventory: dict[str, Any], output_path: Path) -> None:
    records = list(inventory["records"])
    summary = inventory["summary"]
    not_pipeable = [item for item in records if str(item["pipeline_mode"]).startswith("not_pipeable")]
    blocked = [
        item
        for item in records
        if item["cli_status"] in {"blocked_existing_issue", "disabled_with_replacement"}
        or item["pipeline_mode"] == "blocked_existing_issue"
    ]
    not_migrated = [item for item in records if item["cli_status"] == "not_migrated_needs_design"]

    lines = [
        "# MCP/CLI Migration Status",
        "",
        f"Generated at: `{inventory['generated_at']}`",
        "",
        "This file is generated from the Phase 1 inventory script. It is a static",
        "ledger only; it does not prove CST execution or production validation.",
        "",
        "## Summary",
        "",
        f"- Total records: `{summary['total_records']}`",
        f"- MCP tools discovered: `{summary['mcp_tool_count']}`",
        f"- CLI tools discovered: `{summary['cli_tool_count']}`",
        f"- Implemented or mapped to CLI: `{summary['implemented_or_replaced']}`",
        f"- Not migrated and needs design: `{summary['not_migrated_needs_design']}`",
        f"- Disabled or blocked: `{summary['disabled_or_blocked']}`",
        "",
        "## Not Pipeable Tools",
        "",
    ]
    for item in not_pipeable:
        lines.append(
            f"- `{item['name']}`: `{item['pipeline_mode']}`, risk `{item['risk']}`, "
            f"retention `{item['mcp_retention']}`"
        )
    lines.extend(["", "## Disabled Or Blocked", ""])
    for item in blocked:
        lines.append(
            f"- `{item['name']}`: `{item['cli_status']}`, replacement `{item['replacement']}`, "
            f"reason `{item['known_issue'] or item['pipeline_mode']}`"
        )
    lines.extend(["", "## Not Migrated Needs Design", ""])
    for item in not_migrated:
        lines.append(
            f"- `{item['name']}` from `{item['source']}`: risk `{item['risk']}`, "
            f"pipeline `{item['pipeline_mode']}`, MCP retention `{item['mcp_retention']}`"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pipeline_mode_guide(output_path: Path) -> None:
    output_path.write_text(
        """# Pipeline Mode Guide

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
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CST MCP/CLI migration inventory.")
    parser.add_argument("--output-dir", default=str(DEFAULT_REFERENCES_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    inventory = build_inventory()
    inventory_path = output_dir / "mcp_cli_tool_inventory.json"
    status_path = output_dir / "mcp_cli_migration_status.md"
    guide_path = output_dir / "pipeline_mode_guide.md"

    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(inventory, status_path)
    write_pipeline_mode_guide(guide_path)

    print(json.dumps({"status": "success", "outputs": [str(inventory_path), str(status_path), str(guide_path)]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
