from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import platform
import queue
import shutil
import sys
import threading
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..core import audit, identity as project_identity, workspace, utils
from ..tools import build_tools, build_args_templates, build_direct_arg_specs
from ..tools.simulation import tool_run_experiment
from ..tools.audit import tool_record_stage, tool_update_status, tool_stage_evidence
from ..tools.workspace import tool_init_workspace, tool_init_task, tool_prepare_run, tool_get_run_context, tool_install_cst_libraries, tool_health_check
from ..tools.session import tool_cleanup_cst_processes, tool_create_blank_project, tool_cst_session_close, tool_cst_session_inspect, tool_cst_session_open, tool_cst_session_quit, tool_cst_session_reattach, tool_inspect_cst_environment, tool_save_project
from ..tools.farfield import tool_inspect_farfield_monitors, tool_export_farfield_grid, tool_export_farfield_cut, tool_calculate_farfield_neighborhood_flatness
from ..tools.results import tool_open_results_project, tool_list_subprojects, tool_get_version_info, tool_list_result_items, tool_list_run_ids, tool_get_parameter_combination, tool_get_1d_result, tool_get_2d_result, tool_export_run_results, tool_generate_report, tool_plot_exported_file, tool_plot_project_result
from ..tools.project import tool_inspect_project, tool_prepare_experiment, tool_list_materials, tool_list_parameters, tool_list_entities, tool_change_parameter, tool_define_parameters, tool_start_simulation, tool_start_simulation_async, tool_is_simulation_running, tool_wait_simulation, tool_stop_simulation, tool_pause_simulation, tool_resume_simulation, tool_set_solver_acceleration, tool_set_fdsolver_extrude_open_bc, tool_set_mesh_fpbavoid_nonreg_unite, tool_set_mesh_minimum_step_number, tool_list_open_projects, tool_verify_project_identity, tool_infer_run_dir, tool_wait_project_unlocked, tool_define_frequency_range, tool_change_frequency_range, tool_change_solver_type, tool_define_background, tool_define_boundary, tool_define_mesh, tool_define_solver, tool_define_port, tool_define_monitor
from ..tools.modeling import tool_define_material_from_mtd, tool_define_brick, tool_define_cylinder, tool_define_cone, tool_define_rectangle, tool_boolean_subtract, tool_boolean_add, tool_boolean_intersect, tool_boolean_insert, tool_delete_entity, tool_create_component, tool_change_material, tool_rename_entity, tool_set_entity_color, tool_define_units, tool_set_farfield_monitor, tool_set_efield_monitor, tool_set_field_monitor, tool_set_probe, tool_delete_probe, tool_delete_monitor, tool_set_background_with_space, tool_set_farfield_plot_cuts, tool_show_bounding_box, tool_activate_post_process, tool_create_mesh_group, tool_define_polygon_3d, tool_define_analytical_curve, tool_define_extrude_curve, tool_transform_shape, tool_transform_curve, tool_create_horn_segment, tool_create_loft_sweep, tool_create_hollow_sweep, tool_add_to_history, tool_pick_face, tool_define_loft, tool_export_e_field, tool_export_surface_current, tool_export_voltage
from .pipelines.registry import PIPELINES
from .pipelines.impl import (
    pipeline_inspect_project,
    pipeline_prepare_experiment,
)

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ── 自动检测 CST 库路径并加入 sys.path ──
_CST_SEARCH_PATHS = [
    r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    r"C:\Program Files\CST Studio Suite 2025\AMD64\python_cst_libraries",
    r"C:\Program Files (x86)\CST Studio Suite 2026\AMD64\python_cst_libraries",
]
_cst_found = False
try:
    _pp = Path.cwd().resolve() / "pyproject.toml"
    if _pp.exists():
        import tomllib
        _src = tomllib.loads(_pp.read_text(encoding="utf-8")).get("tool", {}).get("uv", {}).get("sources", {}).get("cst-studio-suite-link", {})
        if isinstance(_src, dict) and _src.get("path"):
            _p = Path(_src["path"]).resolve()
            if _p.is_dir() and (_p / "cst").is_dir() and str(_p) not in sys.path:
                sys.path.insert(0, str(_p))
                _cst_found = True
except Exception:
    pass
if not _cst_found:
    for _csp in _CST_SEARCH_PATHS:
        _d = Path(_csp)
        if _d.is_dir() and (_d / "cst").is_dir():
            sys.path.insert(0, str(_d.resolve()))
            break

CLI_VERSION = "0.1.0"
_BOOTSTRAP_ENTRYPOINT = "python <skill-root>\\scripts\\cst_runtime_cli.py"
_UV_ENTRYPOINT = "uv run python -m cst_runtime"
SAFE_WORKSPACE_COMMANDS = {
    "health-check",
    "usage-guide",
    "list-tools",
    "list-pipelines",
    "describe-tool",
    "describe-pipeline",
    "args-template",
    "pipeline-template",
}
WORKSPACE_OPTIONAL_TOOLS = {
    "init-workspace",
    "init-task",
    "inspect-cst-environment",
    "cleanup-cst-processes",
    "cst-session-inspect",
    "cst-session-quit",
    "export-run-results",
    "generate-report",
    "plot-exported-file",
    "inspect-farfield-monitors",
    "calculate-farfield-neighborhood-flatness",
    "list-materials",
    "install-cst-libraries",
    "health-check",
    "stage-evidence",
}
CST_INTERFACE_TOOLS = {
    "create-blank-project",
    "save-project",
    "list-parameters",
    "list-entities",
    "change-parameter",
    "start-simulation",
    "start-simulation-async",
    "is-simulation-running",
    "wait-simulation",
    "list-open-projects",
    "verify-project-identity",
    "cst-session-open",
    "cst-session-reattach",
    "cst-session-close",
    "cst-session-quit",
    "define-brick",
    "define-cylinder",
    "define-cone",
    "define-rectangle",
    "boolean-subtract",
    "boolean-add",
    "boolean-intersect",
    "boolean-insert",
    "delete-entity",
    "create-component",
    "change-material",
    "define-frequency-range",
    "change-frequency-range",
    "change-solver-type",
    "define-background",
    "define-boundary",
    "define-mesh",
    "define-solver",
    "define-port",
    "define-monitor",
    "rename-entity",
    "set-entity-color",
    "define-units",
    "set-farfield-monitor",
    "set-efield-monitor",
    "set-field-monitor",
    "set-probe",
    "delete-probe",
    "delete-monitor",
    "set-background-with-space",
    "set-farfield-plot-cuts",
    "show-bounding-box",
    "activate-post-process",
    "create-mesh-group",
    "stop-simulation",
    "set-solver-acceleration",
    "set-fdsolver-extrude-open-bc",
    "set-mesh-fpbavoid-nonreg-unite",
    "set-mesh-minimum-step-number",
    "define-polygon-3d",
    "define-analytical-curve",
    "define-extrude-curve",
    "transform-shape",
    "transform-curve",
    "create-horn-segment",
    "create-loft-sweep",
    "create-hollow-sweep",
    "add-to-history",
    "pick-face",
    "define-loft",
    "export-e-field",
    "export-surface-current",
    "export-voltage",
    "define-parameters",
    "pause-simulation",
    "resume-simulation",
    "define-material-from-mtd",
    "inspect-project",
    "prepare-experiment",
    "run-experiment",
}
CST_RESULTS_TOOLS = {
    "open-results-project",
    "list-subprojects",
    "list-run-ids",
    "get-parameter-combination",
    "get-1d-result",
    "get-2d-result",
    "get-version-info",
    "list-result-items",
    "plot-project-result",
}
CST_FARFIELD_TOOLS = {
    "export-farfield-grid",
    "export-farfield-cut",
}

TOP_LEVEL_HELP = """Examples:
  python <skill-root>\\scripts\\cst_runtime_cli.py health-check --auto-fix false
  python <skill-root>\\scripts\\cst_runtime_cli.py init-workspace --workspace C:\\path\\to\\workspace
  python <skill-root>\\scripts\\cst_runtime_cli.py list-tools
  python <skill-root>\\scripts\\cst_runtime_cli.py describe-tool --tool get-1d-result
  python <skill-root>\\scripts\\cst_runtime_cli.py args-template --tool get-1d-result --output args.json

Output:
  Runtime commands return JSON on stdout by default. Logs, warnings, and
  diagnostics must not pollute stdout JSON.

Exit codes:
  0  success
  1  tool or runtime error with JSON error payload
  2  CLI usage error with JSON error payload
"""

DIRECT_TOOL_HELP = """Input:
  Prefer --args-file for Windows paths and complex parameters.
  Use --args-stdin only when intentionally merging upstream JSON with explicit args.

Output:
  JSON object on stdout. Check status == "success" before continuing.

Exit codes:
  0  success
  1  tool or runtime error with JSON error payload
  2  CLI usage error with JSON error payload
"""


class JsonArgumentParser(argparse.ArgumentParser):
    def print_help(self) -> None:
        """Override default help to show categorized tool overview."""
        func = globals().get("_categorized_help_text")
        if func:
            print(func())
        else:
            super().print_help()

    def error(self, message: str) -> None:
        payload = {
            "status": "error",
            "error_type": "cli_usage_error",
            "message": message,
            "usage": self.format_usage().strip(),
            "adapter": "cst_runtime_cli",
            "next_steps": [
                f"Run: {_cmd('--help')}",
                f"Run: {_cmd('help --category <category>')}",
                f"Run: {_cmd('describe-tool --tool <tool>')}",
                f"Run: {_cmd('describe-pipeline --pipeline <pipeline>')}",
                f"Run: {_cmd('args-template --tool <tool> --output <args.json>')}",
            ],
        }
        tools = globals().get("TOOLS")
        if isinstance(tools, dict):
            payload["available_tools"] = sorted(tools)
        pipelines = globals().get("PIPELINES")
        if isinstance(pipelines, dict):
            payload["available_pipelines"] = sorted(pipelines)
        print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
        raise SystemExit(2)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
    return 0 if payload.get("status") != "error" else 1


def _entrypoint() -> str:
    main_script = Path(sys.argv[0]).name if sys.argv else ""
    if main_script in ("cst_runtime_cli.py", "cli.py"):
        return _BOOTSTRAP_ENTRYPOINT
    return _UV_ENTRYPOINT


def _categorized_help_text() -> str:
    """Build categorized help text for --help output."""
    from collections import defaultdict

    tools = globals().get("TOOLS", {})
    if not tools:
        return _entrypoint() + " — CST Studio Suite automation CLI"

    cat_order = ["modeling", "project_ops", "simulation", "results", "farfield",
                 "session_manager", "audit", "workspace", "run", "process_cleanup", "project_identity"]
    cat_labels = {
        "modeling": "Modeling", "project_ops": "Project Ops",
        "simulation": "Simulation", "results": "Results",
        "farfield": "Farfield", "session_manager": "Session",
        "audit": "Audit", "workspace": "Workspace",
        "run": "Run", "process_cleanup": "Process Cleanup",
        "project_identity": "Project Identity",
    }

    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, rec in tools.items():
        cat = rec.get("category", "other")
        desc = rec.get("description", "")
        # Truncate long descriptions to first sentence
        short = desc.split(".")[0] if desc else ""
        if len(short) > 60:
            short = short[:57] + "..."
        grouped[cat].append((name, short))

    lines = [
        f"{_entrypoint()} — CST Studio Suite automation CLI",
        "",
        "Usage:",
        f"  {_entrypoint()} <tool> [options]",
        "",
        "Categories:",
    ]

    for cat in cat_order:
        if cat not in grouped:
            continue
        cat_tools = grouped[cat]
        label = cat_labels.get(cat, cat.title())
        # Show first 3 tools as examples
        examples = ", ".join(t[0] for t in cat_tools[:3])
        extra = f" +{len(cat_tools) - 3} more" if len(cat_tools) > 3 else ""
        lines.append(f"  {label:20s} ({len(cat_tools):2d})  {examples}{extra}")

    # Uncategorized
    others = [t for t in grouped if t not in cat_order]
    for cat in others:
        cat_tools = grouped[cat]
        lines.append(f"  {cat:20s} ({len(cat_tools):2d})")

    lines.extend([
        "",
        "Meta commands:",
        f"  help --category <name>     List all tools in a category",
        f"  <tool> --help              Show details for a specific tool",
        f"  list-pipelines             List pipeline recipes",
        f"  describe-tool --tool <t>   Show tool parameters and schema",
        f"  args-template --tool <t>   Generate a parameter template",
        "",
        "Options:",
        "  -h, --help  Show this help",
        "  --version   Show version",
    ])
    return "\n".join(lines)


def _category_detail_text(category: str) -> str:
    """Build help text listing tools in a specific category."""
    tools = globals().get("TOOLS", {})
    in_cat = [(n, rec.get("description", ""))
              for n, rec in sorted(tools.items())
              if rec.get("category") == category]
    if not in_cat:
        available = sorted(set(rec.get("category", "") for rec in tools.values()))
        return f"Unknown category '{category}'. Available: {', '.join(available)}"

    lines = [f"Category: {category} ({len(in_cat)} tools)", ""]
    for name, desc in in_cat:
        short = desc.split(".")[0] if desc else ""
        lines.append(f"  {name:35s} {short}")
    lines.extend([
        "",
        f"  {_entrypoint()} <tool> --help    Show full details for a tool",
        f"  {_entrypoint()} describe-tool --tool <tool>    Show parameters and schema",
    ])
    return "\n".join(lines)


def _cmd(suffix: str = "") -> str:
    return f"{_entrypoint()} {suffix}".rstrip()


def _usage_guide() -> dict[str, Any]:
    return {
        "status": "success",
        "adapter": "cst_runtime_cli",
        "entrypoint": _entrypoint(),
        "error_contract": {
            "stdout": "Always read stdout as JSON for CLI/runtime commands and usage errors.",
            "success": "status == 'success'",
            "failure": "status == 'error'; inspect error_type/message and stop unless the next step explicitly handles it.",
            "exit_code": "Non-zero exit means failure, but agents must still parse stdout JSON.",
            "workspace_not_initialized": "Initialize the runtime workspace before production commands.",
            "source_project_missing": "Provide an existing .cst/.prj source_project before prepare-run.",
            "production_dependency_missing": "Configure CST Python libraries/session dependencies before real CST production commands.",
        },
        "workspace": {
            "environment_variable": "CST_WORKSPACE",
            "marker": ".cst_runtime/workspace.json",
            "init": _cmd("init-workspace --workspace <workspace>"),
            "init_task": _cmd("init-task --workspace <workspace> --task-id task_001_demo --source-project C:\\path\\model.cst --goal demo"),
            "resolution_order": ["--workspace", "CST_WORKSPACE", "ancestor marker", "current directory"],
        },
        "agent_steps": [
            "Run health-check --auto-fix false first when using a new shell, machine, IDE agent, or migrated workspace.",
            "Run list-tools to discover tool names.",
            "Run list-pipelines to discover known pipeable chains before inventing one.",
            "Run describe-pipeline --pipeline <pipeline> before using a multi-tool chain.",
            "Run describe-tool --tool <tool> before first use.",
            "Run args-template --tool <tool> --output <run-or-task>\\stages\\<tool>_args.json.",
            "Edit the args file; prefer args-file over inline JSON for Windows paths.",
            "Invoke the tool with --args-file or pipe JSON to stdin.",
            "After every call, check status before continuing.",
        ],
        "input_styles": {
            "args_file": _cmd("<tool> --args-file C:\\path\\to\\args.json"),
            "direct_flags": "For supported common fields, direct flags may be used, for example: "
            + _cmd("change-parameter --project-path C:\\path\\working.cst --name g --value 24"),
            "stdin": f"@{{ project_path = $workingProject }} | ConvertTo-Json -Depth 8 | {_cmd('<tool>')}",
            "merge": "When using stdin together with --args-file/--args-json, add --args-stdin. Stdin JSON is loaded first; explicit args override same-name fields.",
        },
        "safe_discovery_commands": [
            _cmd("health-check --auto-fix false"),
            _cmd("usage-guide"),
            _cmd("list-tools"),
            _cmd("list-pipelines"),
            _cmd("describe-pipeline --pipeline prepare-experiment"),
            _cmd("describe-tool --tool get-1d-result"),
            _cmd("args-template --tool get-1d-result"),
        ],
        "pipeline_discovery": {
            "list": _cmd("list-pipelines"),
            "describe": _cmd("describe-pipeline --pipeline <pipeline>"),
            "template": _cmd("pipeline-template --pipeline <pipeline> --output <pipeline_plan.json>"),
            "available": sorted(PIPELINES),
        },
        "tool_families": {
            "workspace": ["init-workspace", "init-task", "install-cst-libraries", "health-check"],
            "run": ["prepare-run", "get-run-context"],
            "audit": ["record-stage", "update-status", "stage-evidence"],
            "project_identity": ["infer-run-dir", "wait-project-unlocked", "verify-project-identity", "list-open-projects"],
            "session_manager": ["cst-session-inspect", "cst-session-open", "cst-session-reattach", "cst-session-close", "cst-session-quit", "create-blank-project", "save-project"],
            "process_cleanup": ["inspect-cst-environment", "cleanup-cst-processes"],
            "project_ops": ["list-parameters", "change-parameter", "define-parameters", "define-frequency-range", "change-frequency-range", "define-background", "define-boundary", "define-mesh", "define-solver", "define-port", "define-monitor", "change-solver-type", "start-simulation", "start-simulation-async", "is-simulation-running", "wait-simulation", "pause-simulation", "resume-simulation", "stop-simulation", "set-solver-acceleration", "set-fdsolver-extrude-open-bc", "set-mesh-fpbavoid-nonreg-unite", "set-mesh-minimum-step-number"],
            "modeling": ["define-brick", "define-cylinder", "define-cone", "define-rectangle", "define-units", "define-polygon-3d", "define-analytical-curve", "define-extrude-curve", "define-loft", "transform-shape", "transform-curve", "create-horn-segment", "create-loft-sweep", "create-hollow-sweep", "boolean-add", "boolean-subtract", "boolean-intersect", "boolean-insert", "create-component", "delete-entity", "rename-entity", "set-entity-color", "change-material", "define-material-from-mtd", "list-materials", "list-entities", "set-farfield-monitor", "set-efield-monitor", "set-field-monitor", "set-probe", "delete-probe", "delete-monitor", "set-background-with-space", "set-farfield-plot-cuts", "show-bounding-box", "activate-post-process", "create-mesh-group", "pick-face", "add-to-history", "export-e-field", "export-surface-current", "export-voltage"],
            "results": ["open-results-project", "list-subprojects", "list-run-ids", "get-parameter-combination", "get-1d-result", "get-2d-result", "export-run-results", "generate-report", "plot-exported-file", "plot-project-result"],
            "farfield": ["export-farfield-grid", "export-farfield-cut", "inspect-farfield-monitors"],
        },
        "hard_rules": [
            "Use explicit project_path for CST project operations.",
            "project_path must point to the concrete .cst file, not only to the project directory.",
            "For change-parameter, use name and value; do not invent parameter_name or parameter_value.",
            "For complex or unfamiliar calls, args-template plus --args-file is the preferred path; direct flags are convenience for known common fields.",
            "After modeler simulation, close the modeler project with save=false, reopen results, list run_ids, and read the latest run_id.",
            "Do not edit ref/ source projects; operate on a run working copy.",
            "Do not treat Abs(E) as dBi; use Realized Gain/Gain/Directivity for gain evidence.",
            "Do not continue a pipeline after status == 'error' unless the recovery step is explicit.",
            "Treat pipeline recipes as guidance, not a hidden black-box runner; keep checking each JSON result.",
            "Only force-kill CST process names in the cleanup allowlist; record Access is denied residuals instead of claiming they were killed.",
        ],
    }


def _check_import(module_name: str) -> dict[str, Any]:
    try:
        __import__(module_name)
        return {"name": f"import:{module_name}", "status": "success"}
    except Exception as exc:
        return {"name": f"import:{module_name}", "status": "warning", "message": str(exc)}


def _add_workspace_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace")


def _workspace_marker_from_tool_args(tool_args: dict[str, Any]) -> Path | None:
    candidate_keys = (
        "task_path",
        "project_path",
        "source_project",
        "output_file",
        "output_json",
        "output_html",
        "file_path",
    )
    for key in candidate_keys:
        value = tool_args.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            marker = workspace.find_workspace_marker(Path(value))
        except Exception:
            marker = None
        if marker:
            return marker
    return None


def _workspace_status_for_command(explicit_workspace: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    if explicit_workspace:
        return workspace.workspace_status(explicit_workspace)

    args_workspace = tool_args.get("workspace")
    if isinstance(args_workspace, str) and args_workspace.strip():
        return workspace.workspace_status(args_workspace)

    marker = _workspace_marker_from_tool_args(tool_args)
    if marker:
        return workspace.workspace_status(str(marker.parents[1]))

    return workspace.workspace_status("")


def _workspace_required_error(workspace_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "error",
        "error_type": "workspace_not_initialized",
        "message": "production commands require an initialized CST runtime workspace",
        "workspace": workspace_info,
        "next_steps": [
            _cmd("health-check --workspace <workspace>"),
            _cmd("init-workspace --workspace <workspace>"),
            _cmd("init-task --workspace <workspace> --task-id task_001_demo --source-project C:\\path\\model.cst --goal demo"),
        ],
        "adapter": "cst_runtime_cli",
    }


def _tool_requires_workspace(tool_name: str) -> bool:
    return tool_name not in WORKSPACE_OPTIONAL_TOOLS


def _missing_imports_for_tool(tool_name: str) -> list[str]:
    modules: list[str] = []
    if tool_name in CST_INTERFACE_TOOLS or tool_name in CST_FARFIELD_TOOLS:
        modules.append("cst.interface")
    if tool_name in CST_RESULTS_TOOLS or tool_name in CST_FARFIELD_TOOLS:
        modules.append("cst.results")
    missing: list[str] = []
    for module_name in modules:
        if _check_import(module_name)["status"] != "success":
            missing.append(module_name)
    return missing


def _production_dependency_error(tool_name: str, missing_modules: list[str]) -> dict[str, Any]:
    return {
        "status": "error",
        "error_type": "production_dependency_missing",
        "message": "CST production command dependencies are not available",
        "tool": tool_name,
        "missing_modules": missing_modules,
        "next_steps": [
            _cmd("health-check --workspace <workspace>"),
            "Configure CST Studio Suite Python libraries for the Python executable running this Skill.",
        ],
        "adapter": "cst_runtime_cli",
    }


def _tool_requires_check_solid(tool_name: str) -> bool:
    return False  # gate disabled — model_intent/check_solid not yet implemented


def _tool_pipeline_mode(record: dict[str, Any]) -> str:
    risk = str(record.get("risk", ""))
    category = str(record.get("category", ""))
    if category == "modeling" and risk == "write":
        return "not_pipeable_destructive"
    if risk in {"session", "process-control", "long-running"}:
        return "not_pipeable_session"
    if risk == "filesystem-write":
        return "pipe_sink"
    if risk == "write":
        return "not_pipeable_destructive"
    if risk == "read":
        return "pipe_source"
    return "pipe_optional"


def _tool_validation_level(record: dict[str, Any]) -> str:
    risk = str(record.get("risk", ""))
    category = str(record.get("category", ""))
    if category == "modeling" and risk == "write":
        return "check_solid_gate_plus_cst_smoke"
    if risk in {"session", "process-control", "long-running"}:
        return "workflow"
    if risk == "filesystem-write":
        return "mock_or_parse"
    return "static_contract"


def _tool_governance(tool_name: str, record: dict[str, Any]) -> dict[str, Any]:
    requires_check_solid = _tool_requires_check_solid(tool_name)
    return {
        "pipeline_mode": _tool_pipeline_mode(record),
        "validation_level": _tool_validation_level(record),
        "requires_run_context": requires_check_solid or record.get("risk") in {"write", "session", "long-running"},
        "requires_check_solid": requires_check_solid,
        "writes_project": record.get("risk") == "write",
        "terminal_step": tool_name in CST_FARFIELD_TOOLS,
    }


def _check_solid_gate_error(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | None:
    if not _tool_requires_check_solid(tool_name):
        return None

    required_fields = ("model_intent_path", "check_solid_report_path")
    missing = [field for field in required_fields if not str(tool_args.get(field) or "").strip()]
    if missing:
        return {
            "status": "error",
            "error_type": "check_solid_required",
            "state": "blocked",
            "tool": tool_name,
            "message": "modeling write tools require approved model_intent and check_solid_report context",
            "missing_fields": missing,
            "required_fields": list(required_fields),
            "next_steps": [
                "Generate model_intent.json in the current task/run context.",
                "Run the deterministic Check Solid gate and write check_solid_report.json.",
                "Only invoke modeling write tools after the report status is pass.",
            ],
            "adapter": "cst_runtime_cli",
        }

    model_intent_path = Path(str(tool_args["model_intent_path"])).expanduser().resolve()
    if not model_intent_path.exists() or not model_intent_path.is_file():
        return {
            "status": "error",
            "error_type": "model_intent_missing",
            "state": "blocked",
            "tool": tool_name,
            "message": "model_intent_path must point to an existing JSON intent file",
            "model_intent_path": str(model_intent_path),
            "adapter": "cst_runtime_cli",
        }

    try:
        json.loads(model_intent_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "invalid_model_intent",
            "state": "blocked",
            "tool": tool_name,
            "message": str(exc),
            "model_intent_path": str(model_intent_path),
            "adapter": "cst_runtime_cli",
        }

    report_path = Path(str(tool_args["check_solid_report_path"])).expanduser().resolve()
    if not report_path.exists() or not report_path.is_file():
        return {
            "status": "error",
            "error_type": "check_solid_report_missing",
            "state": "blocked",
            "tool": tool_name,
            "message": "check_solid_report_path must point to an existing JSON report",
            "check_solid_report_path": str(report_path),
            "adapter": "cst_runtime_cli",
        }

    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "invalid_check_solid_report",
            "state": "blocked",
            "tool": tool_name,
            "message": str(exc),
            "check_solid_report_path": str(report_path),
            "adapter": "cst_runtime_cli",
        }

    gate_status = str(
        report.get("status")
        or report.get("gate_status")
        or report.get("decision")
        or ""
    ).lower()
    if gate_status != "pass":
        return {
            "status": "error",
            "error_type": "check_solid_not_passed",
            "state": "blocked",
            "tool": tool_name,
            "message": "modeling write tools require check_solid_report status == 'pass'",
            "check_solid_report_path": str(report_path),
            "check_solid_status": gate_status or None,
            "adapter": "cst_runtime_cli",
        }

    return None


def _tool_runbook(tool_name: str) -> dict[str, Any]:
    runbook = {
        "discover": _cmd(f"describe-tool --tool {tool_name}"),
        "template": _cmd(f"args-template --tool {tool_name} --output <args.json>"),
        "invoke": _cmd(f"{tool_name} --args-file <args.json>"),
        "pipe": f"<json-producing-command> | {_cmd(tool_name)}",
        "pipe_with_args_file": f"<json-producing-command> | {_cmd(f'{tool_name} --args-stdin --args-file <args.json>')}",
        "must_check": "Read stdout JSON and require status == 'success' before the next step.",
    }
    direct_fields = DIRECT_ARG_SPECS.get(tool_name)
    if direct_fields:
        flags = " ".join(f"--{field.replace('_', '-')} <{field}>" for field in direct_fields)
        runbook["direct_flags"] = _cmd(f"{tool_name} {flags}")
    if _tool_requires_check_solid(tool_name):
        runbook["check_solid_gate"] = (
            "Modeling write tools require model_intent_path and a check_solid_report_path whose JSON status is pass; "
            "use args-template/--args-file rather than direct flags for production calls."
        )
    return runbook


def _loads_json_object(text: str, source: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        value = None
        last_error: Exception | None = None
        for start in reversed([index for index, char in enumerate(text) if char in "{["]):
            try:
                value, _ = decoder.raw_decode(text[start:])
                break
            except json.JSONDecodeError as exc:
                last_error = exc
        if value is None:
            raise ValueError(f"invalid JSON from {source}: {last_error}") from last_error
    if not isinstance(value, dict):
        raise ValueError(f"JSON args from {source} must be an object")
    return value


def _read_stdin_text(timeout_seconds: float = 0.2) -> str:
    try:
        if sys.stdin is None or not sys.stdin.readable():
            return ""
    except Exception:
        return ""

    try:
        if sys.stdin.isatty():
            return ""
    except Exception:
        pass

    try:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
        if not ready:
            return ""
        return sys.stdin.read()
    except Exception:
        pass

    result_queue: queue.Queue[str | Exception] = queue.Queue(maxsize=1)

    def reader() -> None:
        try:
            result_queue.put(sys.stdin.read())
        except Exception as exc:
            result_queue.put(exc)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        return ""
    if isinstance(value, Exception):
        return ""
    return value or ""


def _load_json_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.args_json and args.args_file:
        raise ValueError("--args-json and --args-file are mutually exclusive")
    stdin_args: dict[str, Any] = {}
    wants_stdin = bool(getattr(args, "args_stdin", False))
    explicit_input = bool(args.args_json or args.args_file)
    if wants_stdin or not explicit_input:
        stdin_content = _read_stdin_text()
        if stdin_content.strip():
            stdin_args = _loads_json_object(stdin_content, "stdin")
    explicit_args: dict[str, Any] = {}
    if args.args_json:
        explicit_args = _loads_json_object(args.args_json, "--args-json")
    if args.args_file:
        explicit_args = _loads_json_object(Path(args.args_file).read_text(encoding="utf-8-sig"), "--args-file")
    return {**stdin_args, **explicit_args}


def _parse_cli_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


DIRECT_ARG_SPECS: dict[str, dict[str, str]] = build_direct_arg_specs()


def _add_direct_args(parser: argparse.ArgumentParser, tool_name: str) -> None:
    for field in DIRECT_ARG_SPECS.get(tool_name, {}):
        flag = "--" + field.replace("_", "-")
        parser.add_argument(flag, dest=field)


def _direct_args_from_namespace(args: argparse.Namespace, tool_name: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field, _default in DIRECT_ARG_SPECS.get(tool_name, {}).items():
        value = getattr(args, field, None)
        if value is not None:
            values[field] = _parse_cli_scalar(str(value))
    return values


def _attach_captured_stdout(result: dict[str, Any], captured: str) -> dict[str, Any]:
    lines = [line for line in captured.splitlines() if line.strip()]
    if not lines:
        return result
    preview = lines[:20]
    if len(lines) > len(preview):
        preview.append(f"... truncated {len(lines) - len(preview)} stdout lines")
    return {**result, "captured_stdout": preview}


def _archive_args_file(src_path: str, tool_name: str, tool_args: dict[str, Any]) -> None:
    src = Path(src_path).expanduser().resolve()
    tmp_dir = Path.cwd().resolve() / ".cst_runtime" / "tmp"
    is_temp = str(src.parent).lower() == str(tmp_dir).lower()

    run_dir = None
    candidate = tool_args.get("project_path") or tool_args.get("data_dir")
    if candidate:
        from ..core import identity
        rd = identity.infer_run_dir_from_project(str(candidate))
        if rd:
            run_dir = rd
    if run_dir is None:
        candidate = tool_args.get("output_html") or tool_args.get("export_path")
        if candidate:
            p = Path(str(candidate)).expanduser().resolve()
            for parent in [p.parent, *p.parents]:
                if parent.name.startswith("run_") and (parent / "stages").is_dir():
                    run_dir = parent
                    break

    if run_dir and (run_dir / "stages").is_dir():
        dst = run_dir / "stages" / f"args_{tool_name}_{src.stem}.json"
        shutil.copy2(str(src), str(dst))

    if is_temp:
        try:
            src.unlink(missing_ok=True)
        except Exception:
            pass


def _with_audit(tool_name: str, tool_args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    project_path = tool_args.get("project_path") or tool_args.get("fullpath") or tool_args.get("working_project")
    run_dir = None
    if project_path:
        run_dir = project_identity.infer_run_dir_from_project(str(project_path))
        if run_dir is not None and not ((run_dir / "logs").exists() and (run_dir / "stages").exists()):
            run_dir = None
    if run_dir is None:
        for key in ("output_html", "export_path", "output_file", "output_json", "file_path"):
            candidate = tool_args.get(key)
            if not candidate:
                continue
            path = Path(str(candidate)).expanduser().resolve()
            for parent in [path.parent, *path.parents]:
                if parent.name.startswith("run_") and (parent / "logs").exists() and (parent / "stages").exists():
                    run_dir = parent
                    break
            if run_dir is not None:
                break
    if run_dir is None:
        return result
    audit_paths = audit.append_tool_call(
        run_dir=run_dir,
        adapter="cst_runtime_cli",
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
    )
    return {**result, "audit": audit_paths}


def _lazy_tool(mod_name: str, func_name: str) -> Callable:
    """Return a wrapper that imports and calls the tool function on first invocation."""
    import importlib
    from functools import wraps
    @wraps(lambda: None)
    def wrapper(args: dict):
        mod = importlib.import_module(f"..tools.{mod_name}", __package__)
        fn = getattr(mod, f"tool_{func_name}")
        return fn(args)
    return wrapper


# Build handler map from all tool_* functions defined above
_HANDLER_MAP: dict[str, Callable] = {
    "tool_run_experiment": tool_run_experiment,
    "tool_record_stage": tool_record_stage,
    "tool_update_status": tool_update_status,
    "tool_stage_evidence": tool_stage_evidence,
    "tool_init_workspace": tool_init_workspace,
    "tool_init_task": tool_init_task,
    "tool_prepare_run": tool_prepare_run,
    "tool_get_run_context": tool_get_run_context,
    "tool_install_cst_libraries": tool_install_cst_libraries,
    "tool_health_check": tool_health_check,
    "tool_cleanup_cst_processes": tool_cleanup_cst_processes,
    "tool_create_blank_project": tool_create_blank_project,
    "tool_cst_session_close": tool_cst_session_close,
    "tool_cst_session_inspect": tool_cst_session_inspect,
    "tool_cst_session_open": tool_cst_session_open,
    "tool_cst_session_quit": tool_cst_session_quit,
    "tool_cst_session_reattach": tool_cst_session_reattach,
    "tool_inspect_cst_environment": tool_inspect_cst_environment,
    "tool_save_project": tool_save_project,
    "tool_inspect_farfield_monitors": tool_inspect_farfield_monitors,
    "tool_export_farfield_grid": tool_export_farfield_grid,
    "tool_export_farfield_cut": tool_export_farfield_cut,
    "tool_calculate_farfield_neighborhood_flatness": tool_calculate_farfield_neighborhood_flatness,
    "tool_open_results_project": tool_open_results_project,
    "tool_list_subprojects": tool_list_subprojects,
    "tool_get_version_info": tool_get_version_info,
    "tool_list_result_items": tool_list_result_items,
    "tool_list_run_ids": tool_list_run_ids,
    "tool_get_parameter_combination": tool_get_parameter_combination,
    "tool_get_1d_result": tool_get_1d_result,
    "tool_get_2d_result": tool_get_2d_result,
    "tool_export_run_results": tool_export_run_results,
    "tool_generate_report": tool_generate_report,
    "tool_plot_exported_file": tool_plot_exported_file,
    "tool_plot_project_result": tool_plot_project_result,
    "tool_inspect_project": tool_inspect_project,
    "tool_prepare_experiment": tool_prepare_experiment,
    "tool_list_materials": tool_list_materials,
    "tool_list_parameters": tool_list_parameters,
    "tool_list_entities": tool_list_entities,
    "tool_change_parameter": tool_change_parameter,
    "tool_define_parameters": tool_define_parameters,
    "tool_start_simulation": tool_start_simulation,
    "tool_start_simulation_async": tool_start_simulation_async,
    "tool_is_simulation_running": tool_is_simulation_running,
    "tool_wait_simulation": tool_wait_simulation,
    "tool_stop_simulation": tool_stop_simulation,
    "tool_pause_simulation": tool_pause_simulation,
    "tool_resume_simulation": tool_resume_simulation,
    "tool_set_solver_acceleration": tool_set_solver_acceleration,
    "tool_set_fdsolver_extrude_open_bc": tool_set_fdsolver_extrude_open_bc,
    "tool_set_mesh_fpbavoid_nonreg_unite": tool_set_mesh_fpbavoid_nonreg_unite,
    "tool_set_mesh_minimum_step_number": tool_set_mesh_minimum_step_number,
    "tool_list_open_projects": tool_list_open_projects,
    "tool_verify_project_identity": tool_verify_project_identity,
    "tool_infer_run_dir": tool_infer_run_dir,
    "tool_wait_project_unlocked": tool_wait_project_unlocked,
    "tool_define_frequency_range": tool_define_frequency_range,
    "tool_change_frequency_range": tool_change_frequency_range,
    "tool_change_solver_type": tool_change_solver_type,
    "tool_define_background": tool_define_background,
    "tool_define_boundary": tool_define_boundary,
    "tool_define_mesh": tool_define_mesh,
    "tool_define_solver": tool_define_solver,
    "tool_define_port": tool_define_port,
    "tool_define_monitor": tool_define_monitor,
    "tool_define_material_from_mtd": tool_define_material_from_mtd,
    "tool_define_brick": tool_define_brick,
    "tool_define_cylinder": tool_define_cylinder,
    "tool_define_cone": tool_define_cone,
    "tool_define_rectangle": tool_define_rectangle,
    "tool_boolean_subtract": tool_boolean_subtract,
    "tool_boolean_add": tool_boolean_add,
    "tool_boolean_intersect": tool_boolean_intersect,
    "tool_boolean_insert": tool_boolean_insert,
    "tool_delete_entity": tool_delete_entity,
    "tool_create_component": tool_create_component,
    "tool_change_material": tool_change_material,
    "tool_rename_entity": tool_rename_entity,
    "tool_set_entity_color": tool_set_entity_color,
    "tool_define_units": tool_define_units,
    "tool_set_farfield_monitor": tool_set_farfield_monitor,
    "tool_set_efield_monitor": tool_set_efield_monitor,
    "tool_set_field_monitor": tool_set_field_monitor,
    "tool_set_probe": tool_set_probe,
    "tool_delete_probe": tool_delete_probe,
    "tool_delete_monitor": tool_delete_monitor,
    "tool_set_background_with_space": tool_set_background_with_space,
    "tool_set_farfield_plot_cuts": tool_set_farfield_plot_cuts,
    "tool_show_bounding_box": tool_show_bounding_box,
    "tool_activate_post_process": tool_activate_post_process,
    "tool_create_mesh_group": tool_create_mesh_group,
    "tool_define_polygon_3d": tool_define_polygon_3d,
    "tool_define_analytical_curve": tool_define_analytical_curve,
    "tool_define_extrude_curve": tool_define_extrude_curve,
    "tool_transform_shape": tool_transform_shape,
    "tool_transform_curve": tool_transform_curve,
    "tool_create_horn_segment": tool_create_horn_segment,
    "tool_create_loft_sweep": tool_create_loft_sweep,
    "tool_create_hollow_sweep": tool_create_hollow_sweep,
    "tool_add_to_history": tool_add_to_history,
    "tool_pick_face": tool_pick_face,
    "tool_define_loft": tool_define_loft,
    "tool_export_e_field": tool_export_e_field,
    "tool_export_surface_current": tool_export_surface_current,
    "tool_export_voltage": tool_export_voltage,
}
_HANDLER_MAP["tool_create_study"] = _lazy_tool("optimization", "create_study")
_HANDLER_MAP["tool_ask_study"] = _lazy_tool("optimization", "ask_study")
_HANDLER_MAP["tool_tell_study"] = _lazy_tool("optimization", "tell_study")
_HANDLER_MAP["tool_best_study"] = _lazy_tool("optimization", "best_study")
_HANDLER_MAP["tool_add_trials"] = _lazy_tool("optimization", "add_trials")
_HANDLER_MAP["tool_param_importances"] = _lazy_tool("optimization", "param_importances")
_HANDLER_MAP["tool_terminate_check"] = _lazy_tool("optimization", "terminate_check")
assert len(_HANDLER_MAP) > 100, f"Handler map too small: {len(_HANDLER_MAP)}"
_TOOLS: dict[str, dict[str, Any]] = build_tools(_HANDLER_MAP)
TOOLS = _TOOLS


def _public_tool_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
        **_tool_governance(name, record),
    }


def _public_pipeline_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
        "when_to_use": record.get("when_to_use", ""),
        "steps": [step.get("tool") for step in record.get("steps", [])],
    }


def _pipeline_record(pipeline_name: str) -> dict[str, Any] | None:
    record = PIPELINES.get(pipeline_name)
    if record is None:
        return None
    return json.loads(json.dumps(record, ensure_ascii=False))


def _pipeline_runbook(pipeline_name: str) -> dict[str, Any]:
    return {
        "discover": _cmd("list-pipelines"),
        "describe": _cmd(f"describe-pipeline --pipeline {pipeline_name}"),
        "template": _cmd(f"pipeline-template --pipeline {pipeline_name} --output <pipeline_plan.json>"),
        "must_check": "After each step, parse stdout JSON and require status == 'success' before continuing.",
        "rule": "Pipeline recipes are guidance for agent-controlled chaining, not an opaque runner.",
    }


def _tool_args_template(tool_name: str) -> dict[str, Any] | None:
    template = build_args_templates().get(tool_name)
    if template is None:
        return None
    result = json.loads(json.dumps(template, ensure_ascii=False))
    if _tool_requires_check_solid(tool_name):
        result.setdefault("model_intent_path", "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\stages\\model_intent.json")
        result.setdefault("check_solid_report_path", "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\stages\\check_solid_report.json")
    return result


def _invoke_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    record = TOOLS.get(tool_name)
    if record is None:
        return {
            "status": "error",
            "error_type": "unknown_tool",
            "tool": tool_name,
            "available_tools": sorted(TOOLS),
        }
    try:
        captured_stdout = io.StringIO()
        with contextlib.redirect_stdout(captured_stdout):
            result = record["function"](tool_args)
        result = _attach_captured_stdout(result, captured_stdout.getvalue())
    except ValueError as exc:
        message = str(exc)
        result = {
            "status": "error",
            "error_type": "missing_required_arg" if " is required" in message else "invalid_tool_args",
            "tool": tool_name,
            "message": message,
            "runbook": _tool_runbook(tool_name),
        }
    except Exception as exc:
        result = {
            "status": "error",
            "error_type": "tool_exception",
            "tool": tool_name,
            "message": str(exc),
        }
    result.setdefault("tool", tool_name)
    result.setdefault("adapter", "cst_runtime_cli")
    return _with_audit(tool_name, tool_args, result)


def main() -> int:
    parser = JsonArgumentParser(
        description="CLI adapter for cst_runtime.",
        epilog=TOP_LEVEL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"cst_runtime {CLI_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    list_tools = subparsers.add_parser(
        "list-tools",
        help="List available runtime tools.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workspace_arg(list_tools)
    list_pipelines = subparsers.add_parser(
        "list-pipelines",
        help="List known runtime pipeline recipes.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workspace_arg(list_pipelines)
    usage_guide = subparsers.add_parser(
        "usage-guide",
        help="Print a machine-readable agent usage guide.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workspace_arg(usage_guide)

    help_cmd = subparsers.add_parser(
        "help",
        help="Show help for a category or tool.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    help_cmd.add_argument("--category", default="", help="Category name to list tools for.")
    _add_workspace_arg(help_cmd)

    describe = subparsers.add_parser(
        "describe-tool",
        help="Describe a runtime tool.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    describe.add_argument("--tool", required=True)
    _add_workspace_arg(describe)

    describe_pipeline = subparsers.add_parser(
        "describe-pipeline",
        help="Describe a runtime pipeline recipe.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    describe_pipeline.add_argument("--pipeline", required=True)
    _add_workspace_arg(describe_pipeline)

    pipeline_template = subparsers.add_parser(
        "pipeline-template",
        help="Print or write a JSON pipeline plan.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pipeline_template.add_argument("--pipeline", required=True)
    pipeline_template.add_argument("--output")
    _add_workspace_arg(pipeline_template)

    args_template = subparsers.add_parser(
        "args-template",
        help="Print or write a JSON args template for a runtime tool.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    args_template.add_argument("--tool", required=True)
    args_template.add_argument("--output")
    _add_workspace_arg(args_template)

    invoke = subparsers.add_parser(
        "invoke",
        help="Invoke a runtime tool with JSON arguments.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    invoke.add_argument("--tool", required=True)
    invoke.add_argument("--args-json")
    invoke.add_argument("--args-file")
    invoke.add_argument("--args-stdin", action="store_true")
    _add_workspace_arg(invoke)

    for tool_name in sorted(TOOLS):
        direct = subparsers.add_parser(
            tool_name,
            help=TOOLS[tool_name]["description"],
            epilog=DIRECT_TOOL_HELP,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        direct.add_argument("--args-json")
        direct.add_argument("--args-file")
        direct.add_argument("--args-stdin", action="store_true")
        if "workspace" not in DIRECT_ARG_SPECS.get(tool_name, {}):
            _add_workspace_arg(direct)
        _add_direct_args(direct, tool_name)

    args = parser.parse_args()

    if args.command == "list-tools":
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "tools": [_public_tool_record(name, TOOLS[name]) for name in sorted(TOOLS)],
            }
        )

    if args.command == "list-pipelines":
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "pipelines": [_public_pipeline_record(name, PIPELINES[name]) for name in sorted(PIPELINES)],
            }
        )

    if args.command == "usage-guide":
        return _json_response(_usage_guide())

    if args.command == "help":
        category = args.category
        if category:
            print(_category_detail_text(category))
        else:
            print(_categorized_help_text())
        return 0

    if args.command == "describe-tool":
        record = TOOLS.get(args.tool)
        if record is None:
            return _json_response(
                {
                    "status": "error",
                    "error_type": "unknown_tool",
                    "tool": args.tool,
                    "available_tools": sorted(TOOLS),
                }
            )
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "tool": _public_tool_record(args.tool, record),
                "args_template": _tool_args_template(args.tool),
                "runbook": _tool_runbook(args.tool),
                "input_style": "Preferred: generate args-template, edit JSON, invoke with --args-file. Direct flags are available for common fields only. Stdin args merge first; --args-file/--args-json/direct flags override earlier values.",
                "direct_flags": sorted("--" + field.replace("_", "-") for field in DIRECT_ARG_SPECS.get(args.tool, {})),
                "output_style": "JSON object; production calls also write run audit when project_path maps to a run.",
            }
        )

    if args.command == "describe-pipeline":
        record = _pipeline_record(args.pipeline)
        if record is None:
            return _json_response(
                {
                    "status": "error",
                    "error_type": "unknown_pipeline",
                    "pipeline": args.pipeline,
                    "available_pipelines": sorted(PIPELINES),
                    "adapter": "cst_runtime_cli",
                }
            )
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "pipeline": args.pipeline,
                "recipe": record,
                "runbook": _pipeline_runbook(args.pipeline),
            }
        )

    if args.command == "pipeline-template":
        record = _pipeline_record(args.pipeline)
        if record is None:
            return _json_response(
                {
                    "status": "error",
                    "error_type": "unknown_pipeline",
                    "pipeline": args.pipeline,
                    "available_pipelines": sorted(PIPELINES),
                    "adapter": "cst_runtime_cli",
                }
            )
        plan = {
            "status": "success",
            "adapter": "cst_runtime_cli",
            "pipeline": args.pipeline,
            "pipeline_plan": record,
            "runbook": _pipeline_runbook(args.pipeline),
        }
        output_path = ""
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_path = str(output)
        return _json_response({**plan, "output_path": output_path or None})

    if args.command == "args-template":
        record = TOOLS.get(args.tool)
        template = _tool_args_template(args.tool)
        if record is None or template is None:
            return _json_response(
                {
                    "status": "error",
                    "error_type": "unknown_tool",
                    "tool": args.tool,
                    "available_tools": sorted(TOOLS),
                    "adapter": "cst_runtime_cli",
                }
            )
        output_path = ""
        output = None
        if args.output:
            output = Path(args.output).expanduser().resolve()
        else:
            tmp_dir = Path.cwd().resolve() / ".cst_runtime" / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = tmp_dir / f"args_{args.tool}_{ts}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output_path = str(output)
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "tool": args.tool,
                "args_template": template,
                "runbook": _tool_runbook(args.tool),
                "output_path": output_path or None,
                "usage": _cmd(f"{args.tool} --args-file {output_path or '<args.json>'}"),
                "pipe_usage": f"<json-producing-command> | {_cmd(args.tool)}",
            }
        )

    tool_name = args.tool if args.command == "invoke" else args.command
    try:
        tool_args = _load_json_args(args)
    except Exception as exc:
        return _json_response(
            {
                "status": "error",
                "error_type": "invalid_json_args",
                "message": str(exc),
                "adapter": "cst_runtime_cli",
            }
        )

    # Archive args file to run stages/ when --args-file is used
    args_file_src = getattr(args, "args_file", None)
    if args_file_src and Path(args_file_src).is_file():
        _archive_args_file(str(args_file_src), tool_name, tool_args)

    tool_args = {**tool_args, **_direct_args_from_namespace(args, tool_name)}
    if tool_name in TOOLS and _tool_requires_workspace(tool_name):
        workspace_info = _workspace_status_for_command(str(getattr(args, "workspace", "") or ""), tool_args)
        if not workspace_info.get("workspace_initialized"):
            return _json_response(_workspace_required_error(workspace_info))

    if tool_name in TOOLS:
        gate_error = _check_solid_gate_error(tool_name, tool_args)
        if gate_error:
            return _json_response(_with_audit(tool_name, tool_args, gate_error))

    if tool_name in TOOLS:
        missing_modules = _missing_imports_for_tool(tool_name)
        if missing_modules:
            return _json_response(_production_dependency_error(tool_name, missing_modules))

    gov_fields = {"model_intent_path", "check_solid_report_path"}
    clean_args = {k: v for k, v in tool_args.items() if k not in gov_fields}
    return _json_response(_invoke_tool(tool_name, clean_args))


if __name__ == "__main__":
    raise SystemExit(main())
