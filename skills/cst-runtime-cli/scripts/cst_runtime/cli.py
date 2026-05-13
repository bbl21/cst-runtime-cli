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
from pathlib import Path
from typing import Any, Callable

from cst_runtime import audit, farfield, modeling, process_cleanup, project_identity, project_ops, results, run_workspace, session_manager, workspace
from cst_runtime.cli_args_templates import ARGS_TEMPLATES
from cst_runtime.cli_pipelines import PIPELINES

warnings.filterwarnings("ignore", category=DeprecationWarning)

CLI_VERSION = "0.1.0"
ENTRYPOINT_DISPLAY = "python <skill-root>\\scripts\\cst_runtime_cli.py"
SAFE_WORKSPACE_COMMANDS = {
    "doctor",
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
    "generate-s11-comparison",
    "generate-s11-farfield-dashboard",
    "plot-exported-file",
    "inspect-farfield-ascii",
    "plot-farfield-multi",
    "calculate-farfield-neighborhood-flatness",
    "list-materials",
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
    "export-farfield-fresh-session",
    "export-existing-farfield-cut-fresh-session",
    "read-realized-gain-grid-fresh-session",
}

TOP_LEVEL_HELP = """Examples:
  python <skill-root>\\scripts\\cst_runtime_cli.py doctor
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
    def error(self, message: str) -> None:
        payload = {
            "status": "error",
            "error_type": "cli_usage_error",
            "message": message,
            "usage": self.format_usage().strip(),
            "adapter": "cst_runtime_cli",
            "next_steps": [
                f"Run: {_cmd('doctor')}",
                f"Run: {_cmd('usage-guide')}",
                f"Run: {_cmd('list-tools')}",
                f"Run: {_cmd('list-pipelines')}",
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
    payload = _rewrite_entrypoints(payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
    return 0 if payload.get("status") != "error" else 1


def _entrypoint() -> str:
    return ENTRYPOINT_DISPLAY


def _cmd(suffix: str = "") -> str:
    return f"{_entrypoint()} {suffix}".rstrip()


def _rewrite_entrypoints(value: Any) -> Any:
    if isinstance(value, str):
        return (
            value.replace("uv run python -m cst_runtime", _entrypoint())
            .replace("python -m cst_runtime", _entrypoint())
        )
    if isinstance(value, list):
        return [_rewrite_entrypoints(item) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_entrypoints(item) for key, item in value.items()}
    return value


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
            "environment_variable": "CST_MCP_WORKSPACE",
            "marker": ".cst_mcp_runtime/workspace.json",
            "init": _cmd("init-workspace --workspace <workspace>"),
            "init_task": _cmd("init-task --workspace <workspace> --task-id task_001_demo --source-project C:\\path\\model.cst --goal demo"),
            "resolution_order": ["--workspace", "CST_MCP_WORKSPACE", "ancestor marker", "current directory"],
        },
        "agent_steps": [
            "Run doctor first when using a new shell, machine, IDE agent, or migrated workspace.",
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
            _cmd("doctor"),
            _cmd("usage-guide"),
            _cmd("list-tools"),
            _cmd("list-pipelines"),
            _cmd("describe-pipeline --pipeline latest-s11-preview"),
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
            "workspace": ["init-workspace", "init-task"],
            "run": ["prepare-run", "get-run-context"],
            "audit": ["record-stage", "update-status"],
            "project_identity": ["infer-run-dir", "wait-project-unlocked", "verify-project-identity", "list-open-projects"],
            "session_manager": ["cst-session-inspect", "cst-session-open", "cst-session-reattach", "cst-session-close", "cst-session-quit", "create-blank-project", "save-project"],
            "process_cleanup": ["inspect-cst-environment", "cleanup-cst-processes"],
            "project_ops": ["list-parameters", "change-parameter", "define-parameters", "define-frequency-range", "change-frequency-range", "define-background", "define-boundary", "define-mesh", "define-solver", "define-port", "define-monitor", "change-solver-type", "start-simulation", "start-simulation-async", "is-simulation-running", "wait-simulation", "pause-simulation", "resume-simulation", "stop-simulation", "set-solver-acceleration", "set-fdsolver-extrude-open-bc", "set-mesh-fpbavoid-nonreg-unite", "set-mesh-minimum-step-number"],
            "modeling": ["define-brick", "define-cylinder", "define-cone", "define-rectangle", "define-units", "define-polygon-3d", "define-analytical-curve", "define-extrude-curve", "define-loft", "transform-shape", "transform-curve", "create-horn-segment", "create-loft-sweep", "create-hollow-sweep", "boolean-add", "boolean-subtract", "boolean-intersect", "boolean-insert", "create-component", "delete-entity", "rename-entity", "set-entity-color", "change-material", "define-material-from-mtd", "list-materials", "list-entities", "set-farfield-monitor", "set-efield-monitor", "set-field-monitor", "set-probe", "delete-probe", "delete-monitor", "set-background-with-space", "set-farfield-plot-cuts", "show-bounding-box", "activate-post-process", "create-mesh-group", "pick-face", "add-to-history", "export-e-field", "export-surface-current", "export-voltage"],
            "results": ["open-results-project", "list-subprojects", "list-run-ids", "get-parameter-combination", "get-1d-result", "get-2d-result", "generate-s11-comparison", "generate-s11-farfield-dashboard", "plot-exported-file", "plot-project-result"],
            "farfield": ["export-farfield-fresh-session", "read-realized-gain-grid-fresh-session", "inspect-farfield-ascii", "plot-farfield-multi"],
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
            _cmd("doctor --workspace <workspace>"),
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
            _cmd("doctor --workspace <workspace>"),
            "Configure CST Studio Suite Python libraries for the Python executable running this Skill.",
        ],
        "adapter": "cst_runtime_cli",
    }


def _doctor(explicit_workspace: str = "") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    workspace_info = workspace.workspace_status(explicit_workspace)
    skill_root = workspace.skill_root()
    scripts_root = workspace.scripts_root()
    uv_path = shutil.which("uv")
    checks.append(
        {
            "name": "uv_on_path",
            "status": "success" if uv_path else "warning",
            "path": uv_path,
            "message": None if uv_path else "uv not found on PATH; use the Python executable that can import CST dependencies.",
        }
    )
    checks.append(
        {
            "name": "python_version",
            "status": "success" if sys.version_info >= (3, 13) else "warning",
            "version": sys.version,
            "executable": sys.executable,
            "required": ">=3.13",
        }
    )
    workspace_root = Path(str(workspace_info["workspace_root"]))
    pyproject_path = workspace_root / "pyproject.toml"
    cst_link_path = None
    if pyproject_path.exists():
        try:
            import tomllib

            pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            cst_source = (
                pyproject_data.get("tool", {})
                .get("uv", {})
                .get("sources", {})
                .get("cst-studio-suite-link", {})
            )
            if isinstance(cst_source, dict):
                cst_link_path = cst_source.get("path")
        except Exception:
            cst_link_path = None
    checks.append(
        {
            "name": "pyproject_cst_path_dependency",
            "status": "success" if cst_link_path and Path(str(cst_link_path)).exists() else "warning",
            "path": cst_link_path,
            "message": None
            if cst_link_path and Path(str(cst_link_path)).exists()
            else "pyproject CST path dependency is missing or not readable; CST production commands may need PYTHONPATH or installed CST libraries.",
        }
    )
    checks.append(
        {
            "name": "skill_package",
            "status": "success" if (scripts_root / "cst_runtime").exists() else "error",
            "skill_root": str(skill_root),
            "scripts_root": str(scripts_root),
            "entrypoint": _entrypoint(),
        }
    )
    checks.append(
        {
            "name": "workspace",
            "status": "success" if workspace_info["workspace_initialized"] else "warning",
            "path": workspace_info["workspace_root"],
            "source": workspace_info["workspace_source"],
            "cwd": str(Path.cwd()),
            "marker": workspace_info["workspace_marker"],
            "pyproject_exists": pyproject_path.exists(),
            "message": None if workspace_info["workspace_initialized"] else "workspace is not initialized; run init-workspace before production commands.",
        }
    )
    stdin_info: dict[str, Any] = {"name": "stdin", "status": "success"}
    for attr in ("isatty", "readable"):
        try:
            value = getattr(sys.stdin, attr)()
        except Exception as exc:
            value = f"error: {exc}"
        stdin_info[attr] = value
    checks.append(stdin_info)
    checks.append(
        {
            "name": "encoding",
            "status": "success",
            "stdout_encoding": getattr(sys.stdout, "encoding", None),
            "stderr_encoding": getattr(sys.stderr, "encoding", None),
            "filesystem_encoding": sys.getfilesystemencoding(),
        }
    )
    checks.append(_check_import("cst_runtime"))
    checks.append(_check_import("cst.interface"))
    checks.append(_check_import("cst.results"))

    cst_import_ready = all(
        item.get("status") == "success"
        for item in checks
        if item.get("name") in {"import:cst.interface", "import:cst.results"}
    )
    skill_ready = all(
        item.get("status") == "success"
        for item in checks
        if item.get("name") in {"skill_package", "import:cst_runtime"}
    )
    workspace_ready = bool(workspace_info["workspace_initialized"])
    production_ready = bool(skill_ready and workspace_ready and cst_import_ready)
    warning_count = sum(1 for item in checks if item.get("status") == "warning")
    error_count = sum(1 for item in checks if item.get("status") == "error")
    readiness = "ready" if error_count == 0 and warning_count == 0 else "degraded"
    if error_count:
        readiness = "blocked"
    return {
        "status": "success",
        "adapter": "cst_runtime_cli",
        "readiness": readiness,
        "skill_ready": skill_ready,
        "workspace_ready": workspace_ready,
        "production_ready": production_ready,
        "workspace": workspace_info,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "recommended_entrypoints": [
            _cmd("<command>"),
        ],
        "checks": checks,
        "compatibility_notes": [
            "Use --args-file for Windows paths and cross-shell compatibility.",
            "When combining stdin with --args-file or --args-json, add --args-stdin.",
            "Run init-workspace in an empty directory before production commands.",
            "Use CST_MCP_WORKSPACE or --workspace when the current directory is not the target workspace.",
            "Meta commands such as doctor, usage-guide, list-tools, describe-tool, and args-template do not start CST.",
        ],
    }


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


DIRECT_ARG_SPECS: dict[str, dict[str, str]] = {
    "init-workspace": {"workspace": "workspace"},
    "init-task": {
        "workspace": "workspace",
        "task_id": "task_id",
        "source_project": "source_project",
        "goal": "goal",
        "title": "title",
        "force": "force",
    },
    "save-project": {"project_path": "project_path"},
    "list-parameters": {"project_path": "project_path"},
    "list-entities": {"project_path": "project_path", "component": "component"},
    "change-parameter": {"project_path": "project_path", "name": "name", "value": "value"},
    "start-simulation": {"project_path": "project_path"},
    "start-simulation-async": {"project_path": "project_path"},
    "is-simulation-running": {"project_path": "project_path"},
    "wait-simulation": {
        "project_path": "project_path",
        "timeout_seconds": "timeout_seconds",
        "poll_interval_seconds": "poll_interval_seconds",
    },
    "infer-run-dir": {"project_path": "project_path"},
    "wait-project-unlocked": {
        "project_path": "project_path",
        "timeout_seconds": "timeout_seconds",
        "poll_interval_seconds": "poll_interval_seconds",
    },
    "verify-project-identity": {"project_path": "project_path"},
    "open-results-project": {
        "project_path": "project_path",
        "allow_interactive": "allow_interactive",
        "subproject_treepath": "subproject_treepath",
    },
    "list-subprojects": {
        "project_path": "project_path",
        "allow_interactive": "allow_interactive",
    },
    "list-run-ids": {
        "project_path": "project_path",
        "treepath": "treepath",
        "module_type": "module_type",
        "allow_interactive": "allow_interactive",
        "subproject_treepath": "subproject_treepath",
        "skip_nonparametric": "skip_nonparametric",
        "max_mesh_passes_only": "max_mesh_passes_only",
    },
    "get-1d-result": {
        "project_path": "project_path",
        "treepath": "treepath",
        "module_type": "module_type",
        "run_id": "run_id",
        "load_impedances": "load_impedances",
        "export_path": "export_path",
        "allow_interactive": "allow_interactive",
        "subproject_treepath": "subproject_treepath",
    },
    "plot-exported-file": {"file_path": "file_path", "output_html": "output_html", "page_title": "page_title"},
    "plot-project-result": {
        "project_path": "project_path",
        "treepath": "treepath",
        "module_type": "module_type",
        "run_id": "run_id",
        "load_impedances": "load_impedances",
        "output_html": "output_html",
        "page_title": "page_title",
        "allow_interactive": "allow_interactive",
        "subproject_treepath": "subproject_treepath",
        "result_kind": "result_kind",
        "intermediate_json": "intermediate_json",
    },
    "cleanup-cst-processes": {
        "project_path": "project_path",
        "dry_run": "dry_run",
        "settle_seconds": "settle_seconds",
    },
    "inspect-cst-environment": {
        "project_path": "project_path",
    },
    "cst-session-inspect": {
        "project_path": "project_path",
    },
    "cst-session-open": {
        "project_path": "project_path",
    },
    "cst-session-reattach": {
        "project_path": "project_path",
    },
    "cst-session-close": {
        "project_path": "project_path",
        "save": "save",
        "wait_unlock": "wait_unlock",
        "timeout_seconds": "timeout_seconds",
        "poll_interval_seconds": "poll_interval_seconds",
    },
    "cst-session-quit": {
        "project_path": "project_path",
        "dry_run": "dry_run",
        "settle_seconds": "settle_seconds",
    },
    "create-blank-project": {"project_path": "project_path"},
    "define-brick": {
        "project_path": "project_path",
        "name": "name",
        "component": "component",
        "material": "material",
        "x_min": "x_min",
        "x_max": "x_max",
        "y_min": "y_min",
        "y_max": "y_max",
        "z_min": "z_min",
        "z_max": "z_max",
    },
    "define-cylinder": {
        "project_path": "project_path",
        "name": "name",
        "component": "component",
        "material": "material",
        "outer_radius": "outer_radius",
        "inner_radius": "inner_radius",
        "axis": "axis",
    },
    "define-cone": {
        "project_path": "project_path",
        "name": "name",
        "component": "component",
        "material": "material",
        "bottom_radius": "bottom_radius",
        "top_radius": "top_radius",
        "axis": "axis",
    },
    "define-rectangle": {
        "project_path": "project_path",
        "name": "name",
        "curve": "curve",
        "x_min": "x_min",
        "x_max": "x_max",
        "y_min": "y_min",
        "y_max": "y_max",
    },
    "boolean-subtract": {"project_path": "project_path", "target": "target", "tool": "tool"},
    "boolean-add": {"project_path": "project_path", "shape1": "shape1", "shape2": "shape2"},
    "boolean-intersect": {"project_path": "project_path", "shape1": "shape1", "shape2": "shape2"},
    "boolean-insert": {"project_path": "project_path", "shape1": "shape1", "shape2": "shape2"},
    "delete-entity": {"project_path": "project_path", "component": "component", "name": "name"},
    "create-component": {"project_path": "project_path", "component_name": "component_name"},
    "list-materials": {},
    "change-material": {"project_path": "project_path", "shape_name": "shape_name", "material": "material"},
    "define-frequency-range": {"project_path": "project_path", "start_freq": "start_freq", "end_freq": "end_freq"},
    "change-frequency-range": {"project_path": "project_path", "min_frequency": "min_frequency", "max_frequency": "max_frequency"},
    "change-solver-type": {"project_path": "project_path", "solver_type": "solver_type"},
    "define-background": {"project_path": "project_path"},
    "define-boundary": {"project_path": "project_path"},
    "define-mesh": {"project_path": "project_path"},
    "define-solver": {"project_path": "project_path"},
    "define-port": {
        "project_path": "project_path",
        "port_number": "port_number",
        "x_min": "x_min",
        "x_max": "x_max",
        "y_min": "y_min",
        "y_max": "y_max",
        "z_min": "z_min",
        "z_max": "z_max",
        "orientation": "orientation",
    },
    "define-monitor": {"project_path": "project_path", "start_freq": "start_freq", "end_freq": "end_freq", "step": "step"},
    "rename-entity": {"project_path": "project_path", "old_name": "old_name", "new_name": "new_name"},
    "set-entity-color": {"project_path": "project_path", "shape_name": "shape_name"},
    "define-units": {"project_path": "project_path"},
    "set-farfield-monitor": {"project_path": "project_path", "start_freq": "start_freq", "end_freq": "end_freq", "step": "step"},
    "set-efield-monitor": {"project_path": "project_path", "start_freq": "start_freq", "end_freq": "end_freq"},
    "set-field-monitor": {"project_path": "project_path", "field_type": "field_type", "start_frequency": "start_frequency", "end_frequency": "end_frequency"},
    "set-probe": {"project_path": "project_path", "field_type": "field_type", "x_pos": "x_pos", "y_pos": "y_pos", "z_pos": "z_pos"},
    "delete-probe": {"project_path": "project_path", "probe_id": "probe_id"},
    "delete-monitor": {"project_path": "project_path", "monitor_name": "monitor_name"},
    "set-background-with-space": {"project_path": "project_path"},
    "set-farfield-plot-cuts": {"project_path": "project_path"},
    "show-bounding-box": {"project_path": "project_path"},
    "activate-post-process": {"project_path": "project_path", "operation": "operation"},
    "create-mesh-group": {"project_path": "project_path", "group_name": "group_name"},
    "stop-simulation": {"project_path": "project_path"},
    "pause-simulation": {"project_path": "project_path"},
    "resume-simulation": {"project_path": "project_path"},
    "set-solver-acceleration": {"project_path": "project_path"},
    "set-fdsolver-extrude-open-bc": {"project_path": "project_path"},
    "set-mesh-fpbavoid-nonreg-unite": {"project_path": "project_path"},
    "set-mesh-minimum-step-number": {"project_path": "project_path"},
    "define-polygon-3d": {"project_path": "project_path", "name": "name", "curve": "curve"},
    "define-analytical-curve": {"project_path": "project_path", "name": "name", "curve": "curve", "law_x": "law_x", "law_y": "law_y", "law_z": "law_z"},
    "define-extrude-curve": {"project_path": "project_path", "name": "name", "component": "component", "material": "material", "curve": "curve", "thickness": "thickness"},
    "transform-shape": {"project_path": "project_path", "shape_name": "shape_name", "transform_type": "transform_type"},
    "transform-curve": {"project_path": "project_path", "curve_name": "curve_name"},
    "create-horn-segment": {"project_path": "project_path", "segment_id": "segment_id", "bottom_radius": "bottom_radius", "top_radius": "top_radius"},
    "create-loft-sweep": {"project_path": "project_path", "name": "name", "component": "component", "material": "material"},
    "create-hollow-sweep": {"project_path": "project_path", "name": "name", "component": "component", "material": "material", "wall_thickness": "wall_thickness"},
    "add-to-history": {"project_path": "project_path", "command": "command"},
    "pick-face": {"project_path": "project_path", "component": "component", "name": "name", "face_id": "face_id"},
    "define-loft": {"project_path": "project_path", "name": "name", "component": "component", "material": "material"},
    "export-e-field": {"project_path": "project_path", "frequency": "frequency", "file_path": "file_path"},
    "export-surface-current": {"project_path": "project_path", "frequency": "frequency", "file_path": "file_path"},
    "export-voltage": {"project_path": "project_path", "voltage_index": "voltage_index", "file_path": "file_path"},
    "define-parameters": {"project_path": "project_path"},
    "define-material-from-mtd": {"project_path": "project_path", "material_name": "material_name"},
}


def _add_direct_args(parser: argparse.ArgumentParser, tool_name: str) -> None:
    for field in DIRECT_ARG_SPECS.get(tool_name, {}):
        flag = "--" + field.replace("_", "-")
        parser.add_argument(flag, dest=field)


def _direct_args_from_namespace(args: argparse.Namespace, tool_name: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field, target in DIRECT_ARG_SPECS.get(tool_name, {}).items():
        value = getattr(args, field, None)
        if value is not None:
            values[target] = _parse_cli_scalar(str(value))
    return values


def _attach_captured_stdout(result: dict[str, Any], captured: str) -> dict[str, Any]:
    lines = [line for line in captured.splitlines() if line.strip()]
    if not lines:
        return result
    preview = lines[:20]
    if len(lines) > len(preview):
        preview.append(f"... truncated {len(lines) - len(preview)} stdout lines")
    return {**result, "captured_stdout": preview}


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


def _project_path_from_args(args: dict[str, Any]) -> str:
    project_path = project_identity.project_path_from_args(args)
    if Path(project_path).suffix.lower() != ".cst":
        raise ValueError("project_path must point to a concrete .cst file, not a directory")
    return project_path


def tool_init_workspace(args: dict[str, Any]) -> dict[str, Any]:
    return workspace.init_workspace(str(args.get("workspace") or ""))


def tool_init_task(args: dict[str, Any]) -> dict[str, Any]:
    return workspace.init_task(
        workspace=str(args.get("workspace") or ""),
        task_id=str(args.get("task_id") or ""),
        source_project=str(args.get("source_project") or ""),
        goal=str(args.get("goal") or ""),
        title=str(args.get("title") or ""),
        force=bool(args.get("force", False)),
    )


def tool_prepare_run(args: dict[str, Any]) -> dict[str, Any]:
    return run_workspace.prepare_new_run(**args)


def tool_get_run_context(args: dict[str, Any]) -> dict[str, Any]:
    return run_workspace.get_run_context(**args)


def tool_record_stage(args: dict[str, Any]) -> dict[str, Any]:
    return audit.record_run_stage(**args)


def tool_update_status(args: dict[str, Any]) -> dict[str, Any]:
    return audit.update_run_status(**args)


def tool_cleanup_cst_processes(args: dict[str, Any]) -> dict[str, Any]:
    return process_cleanup.cleanup_cst_processes(
        project_path=str(args.get("project_path") or ""),
        dry_run=bool(args.get("dry_run", False)),
        settle_seconds=float(args.get("settle_seconds", 0.5)),
    )


def tool_inspect_cst_environment(args: dict[str, Any]) -> dict[str, Any]:
    return process_cleanup.inspect_cst_environment(
        project_path=str(args.get("project_path") or ""),
    )


def tool_cst_session_inspect(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.inspect(project_path=str(args.get("project_path") or ""))


def tool_cst_session_open(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.open_project(_project_path_from_args(args))


def tool_cst_session_reattach(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.reattach_project(_project_path_from_args(args))


def tool_cst_session_close(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.close_project(
        project_path=_project_path_from_args(args),
        save=bool(args.get("save", False)),
        wait_unlock=bool(args.get("wait_unlock", True)),
        timeout_seconds=float(args.get("timeout_seconds", 30.0)),
        poll_interval_seconds=float(args.get("poll_interval_seconds", 0.5)),
    )


def tool_cst_session_quit(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.quit_cst(
        project_path=str(args.get("project_path") or ""),
        dry_run=bool(args.get("dry_run", False)),
        settle_seconds=float(args.get("settle_seconds", 0.5)),
    )


def tool_list_materials(args: dict[str, Any]) -> dict[str, Any]:
    materials_path = Path(__file__).resolve().parents[2] / "references" / "materials_name_list.txt"
    if not materials_path.is_file():
        return {
            "status": "error",
            "error_type": "materials_list_not_found",
            "expected_path": str(materials_path),
        }
    names = [line.strip() for line in materials_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "status": "success",
        "count": len(names),
        "material_names": names,
        "source": str(materials_path),
        "usage": "Pass the name to change-material --material '<name>', or use define-material-from-mtd --material-name '<name>'.",
    }


def tool_define_material_from_mtd(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_material_from_mtd(
        project_path=_project_path_from_args(args),
        material_name=str(args.get("material_name", "")),
    )


def tool_create_blank_project(args: dict[str, Any]) -> dict[str, Any]:
    return session_manager.create_blank_project(_project_path_from_args(args))


def tool_save_project(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.save_project(_project_path_from_args(args))


def tool_list_parameters(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.list_parameters(_project_path_from_args(args))


def tool_list_entities(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.list_entities(
        project_path=_project_path_from_args(args),
        component=str(args.get("component", "")),
    )


def tool_change_parameter(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    tool_args = {key: value for key, value in args.items() if key not in {"project_path", "fullpath", "working_project"}}
    return project_ops.change_parameter(project_path=project_path, **tool_args)


def tool_start_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.start_simulation(_project_path_from_args(args))


def tool_start_simulation_async(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.start_simulation_async(_project_path_from_args(args))


def tool_is_simulation_running(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.is_simulation_running(_project_path_from_args(args))


def tool_wait_simulation(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    timeout_seconds = float(args.get("timeout_seconds", 3600.0))
    poll_interval_seconds = float(args.get("poll_interval_seconds", 10.0))
    started = time.monotonic()
    polls = 0
    last_result: dict[str, Any] | None = None
    while True:
        polls += 1
        last_result = project_ops.is_simulation_running(project_path)
        if last_result.get("status") == "error":
            return {**last_result, "polls": polls, "waited_seconds": round(time.monotonic() - started, 3)}
        if not bool(last_result.get("running")):
            return {
                "status": "success",
                "project_path": last_result.get("project_path", project_path),
                "running": False,
                "polls": polls,
                "waited_seconds": round(time.monotonic() - started, 3),
                "runtime_module": "cst_runtime.cli",
            }
        if time.monotonic() - started >= timeout_seconds:
            return {
                "status": "error",
                "error_type": "simulation_wait_timeout",
                "message": "simulation still running after timeout",
                "project_path": project_path,
                "running": True,
                "polls": polls,
                "timeout_seconds": timeout_seconds,
                "last_result": last_result,
                "runtime_module": "cst_runtime.cli",
            }
        time.sleep(poll_interval_seconds)


def tool_define_brick(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_brick(**args)


def tool_define_cylinder(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_cylinder(**args)


def tool_define_cone(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_cone(**args)


def tool_define_rectangle(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_rectangle(**args)


def tool_boolean_subtract(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.boolean_subtract(**args)


def tool_boolean_add(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.boolean_add(**args)


def tool_boolean_intersect(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.boolean_intersect(**args)


def tool_boolean_insert(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.boolean_insert(**args)


def tool_delete_entity(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.delete_entity(**args)


def tool_create_component(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.create_component(**args)


def tool_change_material(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.change_material(**args)


def tool_define_frequency_range(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_frequency_range(**args)


def tool_change_frequency_range(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.change_frequency_range(**args)


def tool_change_solver_type(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.change_solver_type(**args)


def tool_define_background(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_background(**args)


def tool_define_boundary(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_boundary(**args)


def tool_define_mesh(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_mesh(**args)


def tool_define_solver(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_solver(**args)


def tool_define_port(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_port(**args)


def tool_define_monitor(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_monitor(**args)


def tool_rename_entity(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.rename_entity(**args)


def tool_set_entity_color(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_entity_color(**args)


def tool_define_units(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_units(**args)


def tool_set_farfield_monitor(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_farfield_monitor(**args)


def tool_set_efield_monitor(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_efield_monitor(**args)


def tool_set_field_monitor(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_field_monitor(**args)


def tool_set_probe(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_probe(**args)


def tool_delete_probe(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.delete_probe_by_id(**args)


def tool_delete_monitor(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.delete_monitor(**args)


def tool_set_background_with_space(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_background_with_space(**args)


def tool_set_farfield_plot_cuts(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.set_farfield_plot_cuts(**args)


def tool_show_bounding_box(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.show_bounding_box(**args)


def tool_activate_post_process(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.activate_post_process_operation(**args)


def tool_create_mesh_group(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.create_mesh_group(**args)


def tool_stop_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.stop_simulation(_project_path_from_args(args))


def tool_pause_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.pause_simulation(_project_path_from_args(args))


def tool_resume_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.resume_simulation(_project_path_from_args(args))


def tool_set_solver_acceleration(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.set_solver_acceleration(**args)


def tool_set_fdsolver_extrude_open_bc(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.set_fdsolver_extrude_open_bc(**args)


def tool_set_mesh_fpbavoid_nonreg_unite(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.set_mesh_fpbavoid_nonreg_unite(**args)


def tool_set_mesh_minimum_step_number(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.set_mesh_minimum_step_number(**args)


def tool_define_polygon_3d(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_polygon_3d(**args)


def tool_define_analytical_curve(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_analytical_curve(**args)


def tool_define_extrude_curve(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_extrude_curve(**args)


def tool_transform_shape(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.transform_shape(**args)


def tool_transform_curve(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.transform_curve(**args)


def tool_create_horn_segment(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.create_horn_segment(**args)


def tool_create_loft_sweep(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.create_loft_sweep(**args)


def tool_create_hollow_sweep(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.create_hollow_sweep(**args)


def tool_add_to_history(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.add_to_history(**args)


def tool_pick_face(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.pick_face(**args)


def tool_define_loft(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.define_loft(**args)


def tool_export_e_field(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.export_e_field(**args)


def tool_export_surface_current(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.export_surface_current(**args)


def tool_export_voltage(args: dict[str, Any]) -> dict[str, Any]:
    return modeling.export_voltage(**args)


def tool_define_parameters(args: dict[str, Any]) -> dict[str, Any]:
    return project_ops.define_parameters(**args)


def tool_infer_run_dir(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    run_dir = project_identity.infer_run_dir_from_project(project_path)
    return {
        "status": "success",
        "project_path": os.path.abspath(project_path),
        "run_dir": run_dir.as_posix() if run_dir else None,
        "runtime_module": "cst_runtime.project_identity",
    }


def tool_wait_project_unlocked(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    return project_identity.wait_project_unlocked(
        project_path=project_path,
        timeout_seconds=float(args.get("timeout_seconds", 10.0)),
        poll_interval_seconds=float(args.get("poll_interval_seconds", 0.5)),
    )


def tool_list_open_projects(args: dict[str, Any]) -> dict[str, Any]:
    return project_identity.list_open_projects()


def tool_verify_project_identity(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    return project_identity.verify_project_identity(project_path)


def tool_open_results_project(args: dict[str, Any]) -> dict[str, Any]:
    return results.open_project(
        project_path=_project_path_from_args(args),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_list_subprojects(args: dict[str, Any]) -> dict[str, Any]:
    return results.list_subprojects(
        project_path=_project_path_from_args(args),
        allow_interactive=bool(args.get("allow_interactive", False)),
    )


def tool_get_version_info(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_version_info()


def tool_list_result_items(args: dict[str, Any]) -> dict[str, Any]:
    return results.list_result_items(
        project_path=_project_path_from_args(args),
        module_type=str(args.get("module_type", "3d")),
        filter_type=str(args.get("filter_type", "0D/1D")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_list_run_ids(args: dict[str, Any]) -> dict[str, Any]:
    return results.list_run_ids(
        project_path=_project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
        skip_nonparametric=bool(args.get("skip_nonparametric", False)),
        max_mesh_passes_only=bool(args.get("max_mesh_passes_only", True)),
    )


def _run_id_from_args(args: dict[str, Any], default: int = 0) -> int:
    if args.get("run_id") is not None:
        return int(args.get("run_id", default))
    run_ids = args.get("run_ids")
    if isinstance(run_ids, list) and run_ids:
        return int(max(run_ids))
    return default


def tool_get_parameter_combination(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_parameter_combination(
        project_path=_project_path_from_args(args),
        run_id=_run_id_from_args(args),
        module_type=str(args.get("module_type", "3d")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_get_1d_result(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_1d_result(
        project_path=_project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        run_id=_run_id_from_args(args),
        load_impedances=bool(args.get("load_impedances", True)),
        export_path=str(args.get("export_path", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_get_2d_result(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_2d_result(
        project_path=_project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        export_path=str(args.get("export_path", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
        include_data=bool(args.get("include_data", False)),
    )


def tool_plot_exported_file(args: dict[str, Any]) -> dict[str, Any]:
    file_path = args.get("file_path") or args.get("export_path") or args.get("output_file")
    return results.plot_exported_file(
        file_path=str(file_path or ""),
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
    )


def tool_plot_project_result(args: dict[str, Any]) -> dict[str, Any]:
    return results.plot_project_result(
        project_path=_project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        run_id=_run_id_from_args(args),
        load_impedances=bool(args.get("load_impedances", True)),
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
        result_kind=str(args.get("result_kind", "auto")),
        intermediate_json=str(args.get("intermediate_json", "")),
    )


def tool_generate_s11_comparison(args: dict[str, Any]) -> dict[str, Any]:
    file_paths = args.get("file_paths") or []
    if isinstance(file_paths, str):
        file_paths = json.loads(file_paths)
    if not file_paths and args.get("export_path"):
        file_paths = [str(args["export_path"])]
    return results.generate_s11_comparison(
        file_paths=[str(path) for path in file_paths],
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
    )


def tool_generate_s11_farfield_dashboard(args: dict[str, Any]) -> dict[str, Any]:
    s11_file_paths = args.get("s11_file_paths") or []
    farfield_file_paths = args.get("farfield_file_paths") or []
    if isinstance(s11_file_paths, str):
        s11_file_paths = json.loads(s11_file_paths)
    if isinstance(farfield_file_paths, str):
        farfield_file_paths = json.loads(farfield_file_paths)
    return results.generate_s11_farfield_dashboard(
        s11_file_paths=[str(path) for path in s11_file_paths],
        farfield_file_paths=[str(path) for path in farfield_file_paths],
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
        farfield_run_id=int(args.get("farfield_run_id") or 0),
    )


def tool_inspect_farfield_ascii(args: dict[str, Any]) -> dict[str, Any]:
    file_path = args.get("file_path") or args.get("output_file") or args.get("export_path")
    if not file_path:
        return {
            "status": "error",
            "error_code": "file_path_missing",
            "message": "file_path is required",
            "runtime_module": "cst_runtime.cli",
        }
    return {
        "status": "success",
        "file_path": str(file_path),
        "grid": farfield.inspect_farfield_ascii_grid(str(file_path)),
        "runtime_module": "cst_runtime.farfield",
    }


def tool_export_farfield_fresh_session(args: dict[str, Any]) -> dict[str, Any]:
    return farfield.export_farfield_fresh_session(
        project_path=_project_path_from_args(args),
        farfield_name=str(args.get("farfield_name", "")),
        output_file=str(args.get("output_file", "")),
        plot_mode=str(args.get("plot_mode", "Realized Gain")),
        prime_with_cut=bool(args.get("prime_with_cut", False)),
        cut_axis=str(args.get("cut_axis", "Phi")),
        cut_angle=str(args.get("cut_angle", "0")),
        theta_step_deg=float(args.get("theta_step_deg", 5.0)),
        phi_step_deg=float(args.get("phi_step_deg", 5.0)),
        theta_min_deg=args.get("theta_min_deg"),
        theta_max_deg=args.get("theta_max_deg"),
        phi_min_deg=args.get("phi_min_deg"),
        phi_max_deg=args.get("phi_max_deg"),
        max_attempts=int(args.get("max_attempts", farfield.FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS)),
        keep_prime_cut_file=bool(args.get("keep_prime_cut_file", False)),
    )


def tool_export_existing_farfield_cut_fresh_session(args: dict[str, Any]) -> dict[str, Any]:
    return farfield.export_existing_farfield_cut_fresh_session(
        project_path=_project_path_from_args(args),
        tree_path=str(args.get("tree_path", "")),
        output_file=str(args.get("output_file", "")),
    )


def tool_read_realized_gain_grid_fresh_session(args: dict[str, Any]) -> dict[str, Any]:
    run_id = args.get("run_id")
    return farfield.read_realized_gain_grid_fresh_session(
        project_path=_project_path_from_args(args),
        farfield_name=str(args.get("farfield_name", "")),
        run_id=None if run_id in (None, "") else int(run_id),
        theta_step_deg=float(args.get("theta_step_deg", 1.0)),
        phi_step_deg=float(args.get("phi_step_deg", 2.0)),
        theta_min_deg=args.get("theta_min_deg"),
        theta_max_deg=args.get("theta_max_deg"),
        phi_min_deg=args.get("phi_min_deg"),
        phi_max_deg=args.get("phi_max_deg"),
        selection_tree_path=str(args.get("selection_tree_path", "1D Results\\S-Parameters")),
        output_json=str(args.get("output_json", "")),
    )


def tool_calculate_farfield_neighborhood_flatness(args: dict[str, Any]) -> dict[str, Any]:
    file_paths = args.get("file_paths") or []
    if isinstance(file_paths, str):
        file_paths = json.loads(file_paths)
    if not file_paths and args.get("file_path"):
        file_paths = [str(args["file_path"])]
    return farfield.calculate_farfield_neighborhood_flatness(
        file_paths=[str(path) for path in file_paths],
        theta_max_deg=float(args.get("theta_max_deg", 15.0)),
        output_json=str(args.get("output_json", "")),
    )


def tool_plot_farfield_multi(args: dict[str, Any]) -> dict[str, Any]:
    file_paths = args.get("file_paths") or []
    if isinstance(file_paths, str):
        file_paths = json.loads(file_paths)
    if not file_paths:
        single = args.get("file_path") or args.get("output_file") or args.get("export_path")
        if single:
            file_paths = [str(single)]
    return results.plot_farfield_multi(
        file_paths=[str(path) for path in file_paths],
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
    )


ToolFunc = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: dict[str, dict[str, Any]] = {
    "init-workspace": {
        "category": "workspace",
        "risk": "filesystem-write",
        "description": "Initialize a minimal CST runtime workspace in an empty or existing directory.",
        "function": tool_init_workspace,
    },
    "init-task": {
        "category": "workspace",
        "risk": "filesystem-write",
        "description": "Create a task.json and runs directory inside a runtime workspace.",
        "function": tool_init_task,
    },
    "prepare-run": {
        "category": "run",
        "risk": "filesystem-write",
        "description": "Create a standard run workspace through cst_runtime.",
        "function": tool_prepare_run,
    },
    "get-run-context": {
        "category": "run",
        "risk": "read",
        "description": "Read standard run context through cst_runtime.",
        "function": tool_get_run_context,
    },
    "record-stage": {
        "category": "audit",
        "risk": "filesystem-write",
        "description": "Write a stage record and production-chain log entry.",
        "function": tool_record_stage,
    },
    "update-status": {
        "category": "audit",
        "risk": "filesystem-write",
        "description": "Update the formal run status.json file.",
        "function": tool_update_status,
    },
    "cleanup-cst-processes": {
        "category": "process_cleanup",
        "risk": "process-control",
        "description": "Force-kill only allowlisted CST processes and report Access is denied residuals with lock-file evidence.",
        "function": tool_cleanup_cst_processes,
    },
    "inspect-cst-environment": {
        "category": "process_cleanup",
        "risk": "read",
        "description": "Inspect allowlisted CST processes, project locks, open projects, and attach readiness.",
        "function": tool_inspect_cst_environment,
    },
    "cst-session-inspect": {
        "category": "session_manager",
        "risk": "read",
        "description": "Central session/process gate: inspect processes, locks, open projects, and reattach readiness.",
        "function": tool_cst_session_inspect,
    },
    "cst-session-open": {
        "category": "session_manager",
        "risk": "session",
        "description": "Open a CST project through the central session manager and inspect the environment afterward.",
        "function": tool_cst_session_open,
    },
    "cst-session-reattach": {
        "category": "session_manager",
        "risk": "read",
        "description": "Reattach to the expected CST project only if it is the sole open project.",
        "function": tool_cst_session_reattach,
    },
    "cst-session-close": {
        "category": "session_manager",
        "risk": "session",
        "description": "Close the expected CST project, optionally wait for locks to clear, then inspect the environment.",
        "function": tool_cst_session_close,
    },
    "cst-session-quit": {
        "category": "session_manager",
        "risk": "process-control",
        "description": "Quit CST through the central session manager using only the process allowlist and lock evidence.",
        "function": tool_cst_session_quit,
    },
    "create-blank-project": {
        "category": "session_manager",
        "risk": "write",
        "description": "Create a new blank CST project at the specified path.",
        "function": tool_create_blank_project,
    },
    "save-project": {
        "category": "session_manager",
        "risk": "filesystem-write",
        "description": "Save the verified CST working project.",
        "function": tool_save_project,
    },
    "list-parameters": {
        "category": "project_ops",
        "risk": "read",
        "description": "List parameters from the verified CST working project.",
        "function": tool_list_parameters,
    },
    "list-entities": {
        "category": "modeling",
        "risk": "read",
        "description": "List geometry entities from the verified CST working project.",
        "function": tool_list_entities,
    },
    "change-parameter": {
        "category": "project_ops",
        "risk": "write",
        "description": "Change one CST parameter in the verified working project.",
        "function": tool_change_parameter,
    },
    "start-simulation": {
        "category": "project_ops",
        "risk": "long-running",
        "description": "Run the CST solver synchronously for the verified working project.",
        "function": tool_start_simulation,
    },
    "start-simulation-async": {
        "category": "project_ops",
        "risk": "long-running",
        "description": "Start the CST solver asynchronously for the verified working project.",
        "function": tool_start_simulation_async,
    },
    "is-simulation-running": {
        "category": "project_ops",
        "risk": "read",
        "description": "Check whether the CST solver is currently running for the verified working project.",
        "function": tool_is_simulation_running,
    },
    "wait-simulation": {
        "category": "project_ops",
        "risk": "long-running",
        "description": "Poll is-simulation-running until the solver finishes or timeout expires.",
        "function": tool_wait_simulation,
    },
    "infer-run-dir": {
        "category": "project-identity",
        "risk": "read",
        "description": "Infer run_dir from a projects/working.cst project path.",
        "function": tool_infer_run_dir,
    },
    "wait-project-unlocked": {
        "category": "project-identity",
        "risk": "read",
        "description": "Wait for a project companion directory to have no .lok files.",
        "function": tool_wait_project_unlocked,
    },
    "list-open-projects": {
        "category": "project-identity",
        "risk": "read",
        "description": "List CST projects visible through DesignEnvironment.connect_to_any().",
        "function": tool_list_open_projects,
    },
    "verify-project-identity": {
        "category": "project-identity",
        "risk": "read",
        "description": "Verify the expected project is the sole open CST project before writes.",
        "function": tool_verify_project_identity,
    },
    "open-results-project": {
        "category": "results",
        "risk": "read",
        "description": "Validate that cst.results can open a project path.",
        "function": tool_open_results_project,
    },
    "list-subprojects": {
        "category": "results",
        "risk": "read",
        "description": "List subprojects from a CST results project by explicit project_path.",
        "function": tool_list_subprojects,
    },
    "get-version-info": {
        "category": "results",
        "risk": "read",
        "description": "Read cst.results version information.",
        "function": tool_get_version_info,
    },
    "list-result-items": {
        "category": "results",
        "risk": "read",
        "description": "List result tree items from a project path.",
        "function": tool_list_result_items,
    },
    "list-run-ids": {
        "category": "results",
        "risk": "read",
        "description": "List CST result run IDs from a project path.",
        "function": tool_list_run_ids,
    },
    "get-parameter-combination": {
        "category": "results",
        "risk": "read",
        "description": "Read the parameter combination for a result run ID.",
        "function": tool_get_parameter_combination,
    },
    "get-1d-result": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Export a 0D/1D result item to JSON from a project path.",
        "function": tool_get_1d_result,
    },
    "get-2d-result": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Export a 2D result item to JSON from a project path.",
        "function": tool_get_2d_result,
    },
    "plot-exported-file": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Render an exported JSON result or CST farfield ASCII/TXT file to an HTML preview.",
        "function": tool_plot_exported_file,
    },
    "plot-project-result": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Export a project result with explicit project_path and render it to an HTML preview.",
        "function": tool_plot_project_result,
    },
    "generate-s11-comparison": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Generate an HTML S11 comparison from exported JSON files.",
        "function": tool_generate_s11_comparison,
    },
    "generate-s11-farfield-dashboard": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Generate a combined S11 and farfield HTML dashboard from exported JSON/TXT files.",
        "function": tool_generate_s11_farfield_dashboard,
    },
    "inspect-farfield-ascii": {
        "category": "farfield",
        "risk": "read",
        "description": "Inspect a CST farfield ASCII/TXT grid and return row/theta/phi counts.",
        "function": tool_inspect_farfield_ascii,
    },
    "export-farfield-fresh-session": {
        "category": "farfield",
        "risk": "long-running",
        "description": "Export a FarfieldCalculator scalar grid to ASCII/TXT in a fresh CST GUI session.",
        "function": tool_export_farfield_fresh_session,
    },
    "export-existing-farfield-cut-fresh-session": {
        "category": "farfield",
        "risk": "long-running",
        "description": "Export an existing CST Farfield Cut tree item to ASCII/TXT in a fresh CST GUI session.",
        "function": tool_export_existing_farfield_cut_fresh_session,
    },
    "read-realized-gain-grid-fresh-session": {
        "category": "farfield",
        "risk": "long-running",
        "description": "Read a Realized Gain dBi grid through FarfieldCalculator in a fresh CST GUI session.",
        "function": tool_read_realized_gain_grid_fresh_session,
    },
    "calculate-farfield-neighborhood-flatness": {
        "category": "farfield",
        "risk": "filesystem-write",
        "description": "Calculate near-boresight farfield cut flatness from exported cut JSON payloads.",
        "function": tool_calculate_farfield_neighborhood_flatness,
    },
    "plot-farfield-multi": {
        "category": "farfield",
        "risk": "filesystem-write",
        "description": "Render one or more farfield ASCII/TXT or 2D JSON grids to an HTML preview.",
        "function": tool_plot_farfield_multi,
    },
    "define-brick": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a rectangular brick in the CST project.",
        "function": tool_define_brick,
    },
    "define-cylinder": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a cylinder in the CST project.",
        "function": tool_define_cylinder,
    },
    "define-cone": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a cone in the CST project.",
        "function": tool_define_cone,
    },
    "define-rectangle": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a 2D rectangle on a curve in the CST project.",
        "function": tool_define_rectangle,
    },
    "boolean-subtract": {
        "category": "modeling",
        "risk": "write",
        "description": "Subtract one solid from another (boolean difference).",
        "function": tool_boolean_subtract,
    },
    "boolean-add": {
        "category": "modeling",
        "risk": "write",
        "description": "Unite two solids (boolean union).",
        "function": tool_boolean_add,
    },
    "boolean-intersect": {
        "category": "modeling",
        "risk": "write",
        "description": "Intersect two solids (boolean intersection).",
        "function": tool_boolean_intersect,
    },
    "boolean-insert": {
        "category": "modeling",
        "risk": "write",
        "description": "Insert one solid into another (boolean insert).",
        "function": tool_boolean_insert,
    },
    "delete-entity": {
        "category": "modeling",
        "risk": "write",
        "description": "Delete a geometry entity from the CST project.",
        "function": tool_delete_entity,
    },
    "create-component": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a new component in the CST project.",
        "function": tool_create_component,
    },
    "change-material": {
        "category": "modeling",
        "risk": "write",
        "description": "Change the material of a geometry entity. Use list-materials to see available names.",
        "function": tool_change_material,
    },
    "list-materials": {
        "category": "modeling",
        "risk": "read",
        "description": "List available CST material names from the Materials library.",
        "function": tool_list_materials,
    },
    "define-material-from-mtd": {
        "category": "modeling",
        "risk": "write",
        "description": "Define a CST material from .mtd file by material name. Material must exist in references/Materials/. Use list-materials to see available names.",
        "function": tool_define_material_from_mtd,
    },
    "define-frequency-range": {
        "category": "project_ops",
        "risk": "write",
        "description": "Set the simulation frequency range.",
        "function": tool_define_frequency_range,
    },
    "change-frequency-range": {
        "category": "project_ops",
        "risk": "write",
        "description": "Change the simulation frequency range.",
        "function": tool_change_frequency_range,
    },
    "change-solver-type": {
        "category": "project_ops",
        "risk": "write",
        "description": "Change the CST solver type.",
        "function": tool_change_solver_type,
    },
    "define-background": {
        "category": "project_ops",
        "risk": "write",
        "description": "Set the background type to Normal.",
        "function": tool_define_background,
    },
    "define-boundary": {
        "category": "project_ops",
        "risk": "write",
        "description": "Set expanded open boundary conditions.",
        "function": tool_define_boundary,
    },
    "define-mesh": {
        "category": "project_ops",
        "risk": "write",
        "description": "Configure the hexahedral mesh parameters.",
        "function": tool_define_mesh,
    },
    "define-solver": {
        "category": "project_ops",
        "risk": "write",
        "description": "Configure the time-domain solver settings.",
        "function": tool_define_solver,
    },
    "define-port": {
        "category": "project_ops",
        "risk": "write",
        "description": "Define a waveguide port.",
        "function": tool_define_port,
    },
    "define-monitor": {
        "category": "project_ops",
        "risk": "write",
        "description": "Define a farfield monitor over a frequency range.",
        "function": tool_define_monitor,
    },
    "rename-entity": {
        "category": "modeling",
        "risk": "write",
        "description": "Rename a geometry entity.",
        "function": tool_rename_entity,
    },
    "set-entity-color": {
        "category": "modeling",
        "risk": "write",
        "description": "Set the display color of a geometry entity.",
        "function": tool_set_entity_color,
    },
    "define-units": {
        "category": "modeling",
        "risk": "write",
        "description": "Set the CST project unit system.",
        "function": tool_define_units,
    },
    "set-farfield-monitor": {
        "category": "modeling",
        "risk": "write",
        "description": "Set a farfield monitor over a frequency range.",
        "function": tool_set_farfield_monitor,
    },
    "set-efield-monitor": {
        "category": "modeling",
        "risk": "write",
        "description": "Set an E-field monitor over a frequency range.",
        "function": tool_set_efield_monitor,
    },
    "set-field-monitor": {
        "category": "modeling",
        "risk": "write",
        "description": "Set a field monitor (e.g. H-field) over a frequency range.",
        "function": tool_set_field_monitor,
    },
    "set-probe": {
        "category": "modeling",
        "risk": "write",
        "description": "Set a field probe at a specified position.",
        "function": tool_set_probe,
    },
    "delete-probe": {
        "category": "modeling",
        "risk": "write",
        "description": "Delete a probe by its ID.",
        "function": tool_delete_probe,
    },
    "delete-monitor": {
        "category": "modeling",
        "risk": "write",
        "description": "Delete a monitor by name.",
        "function": tool_delete_monitor,
    },
    "set-background-with-space": {
        "category": "modeling",
        "risk": "write",
        "description": "Set background space distances.",
        "function": tool_set_background_with_space,
    },
    "set-farfield-plot-cuts": {
        "category": "modeling",
        "risk": "write",
        "description": "Set farfield plot cut angles.",
        "function": tool_set_farfield_plot_cuts,
    },
    "show-bounding-box": {
        "category": "modeling",
        "risk": "write",
        "description": "Toggle bounding box display.",
        "function": tool_show_bounding_box,
    },
    "activate-post-process": {
        "category": "modeling",
        "risk": "write",
        "description": "Activate or deactivate a post-processing operation.",
        "function": tool_activate_post_process,
    },
    "create-mesh-group": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a mesh group and add items.",
        "function": tool_create_mesh_group,
    },
    "stop-simulation": {
        "category": "project_ops",
        "risk": "session",
        "description": "Stop the currently running CST solver.",
        "function": tool_stop_simulation,
    },
    "pause-simulation": {
        "category": "project_ops",
        "risk": "session",
        "description": "Pause the currently running CST solver.",
        "function": tool_pause_simulation,
    },
    "resume-simulation": {
        "category": "project_ops",
        "risk": "session",
        "description": "Resume a paused CST solver.",
        "function": tool_resume_simulation,
    },
    "set-solver-acceleration": {
        "category": "project_ops",
        "risk": "write",
        "description": "Configure solver parallelization and hardware acceleration.",
        "function": tool_set_solver_acceleration,
    },
    "set-fdsolver-extrude-open-bc": {
        "category": "project_ops",
        "risk": "write",
        "description": "Enable or disable FD solver extruded open boundary.",
        "function": tool_set_fdsolver_extrude_open_bc,
    },
    "set-mesh-fpbavoid-nonreg-unite": {
        "category": "project_ops",
        "risk": "write",
        "description": "Enable or disable mesh FPBA non-regular unite avoidance.",
        "function": tool_set_mesh_fpbavoid_nonreg_unite,
    },
    "set-mesh-minimum-step-number": {
        "category": "project_ops",
        "risk": "write",
        "description": "Set the minimum mesh step number.",
        "function": tool_set_mesh_minimum_step_number,
    },
    "define-polygon-3d": {
        "category": "modeling",
        "risk": "write",
        "description": "Define a 3D polygon curve from a list of points.",
        "function": tool_define_polygon_3d,
    },
    "define-analytical-curve": {
        "category": "modeling",
        "risk": "write",
        "description": "Define an analytical curve using parametric equations.",
        "function": tool_define_analytical_curve,
    },
    "define-extrude-curve": {
        "category": "modeling",
        "risk": "write",
        "description": "Extrude a curve profile into a solid.",
        "function": tool_define_extrude_curve,
    },
    "transform-shape": {
        "category": "modeling",
        "risk": "write",
        "description": "Mirror or rotate a geometry shape.",
        "function": tool_transform_shape,
    },
    "transform-curve": {
        "category": "modeling",
        "risk": "write",
        "description": "Mirror a curve.",
        "function": tool_transform_curve,
    },
    "create-horn-segment": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a horn segment (outer cone - inner cone).",
        "function": tool_create_horn_segment,
    },
    "create-loft-sweep": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a loft sweep between two 2D profiles in one step.",
        "function": tool_create_loft_sweep,
    },
    "create-hollow-sweep": {
        "category": "modeling",
        "risk": "write",
        "description": "Create a hollow loft sweep with outer and inner walls.",
        "function": tool_create_hollow_sweep,
    },
    "add-to-history": {
        "category": "modeling",
        "risk": "write",
        "description": "Execute a raw VBA command via add_to_history for operations not covered by other tools.",
        "function": tool_add_to_history,
    },
    "pick-face": {
        "category": "modeling",
        "risk": "write",
        "description": "Select a face by ID for loft operations (zero-thickness entities only).",
        "function": tool_pick_face,
    },
    "define-loft": {
        "category": "modeling",
        "risk": "write",
        "description": "Execute a loft between pre-picked faces.",
        "function": tool_define_loft,
    },
    "export-e-field": {
        "category": "modeling",
        "risk": "filesystem-write",
        "description": "Export E-field data at a given frequency to ASCII.",
        "function": tool_export_e_field,
    },
    "export-surface-current": {
        "category": "modeling",
        "risk": "filesystem-write",
        "description": "Export surface current data at a given frequency to ASCII.",
        "function": tool_export_surface_current,
    },
    "export-voltage": {
        "category": "modeling",
        "risk": "filesystem-write",
        "description": "Export voltage monitor data to ASCII.",
        "function": tool_export_voltage,
    },
    "define-parameters": {
        "category": "project_ops",
        "risk": "write",
        "description": "Batch-define multiple CST parameters using StoreParameters.",
        "function": tool_define_parameters,
    },
}


def _public_tool_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
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
    return _rewrite_entrypoints(json.loads(json.dumps(record, ensure_ascii=False)))


def _pipeline_runbook(pipeline_name: str) -> dict[str, Any]:
    return {
        "discover": _cmd("list-pipelines"),
        "describe": _cmd(f"describe-pipeline --pipeline {pipeline_name}"),
        "template": _cmd(f"pipeline-template --pipeline {pipeline_name} --output <pipeline_plan.json>"),
        "must_check": "After each step, parse stdout JSON and require status == 'success' before continuing.",
        "rule": "Pipeline recipes are guidance for agent-controlled chaining, not an opaque runner.",
    }


def _tool_args_template(tool_name: str) -> dict[str, Any] | None:
    template = ARGS_TEMPLATES.get(tool_name)
    if template is None:
        return None
    return json.loads(json.dumps(template, ensure_ascii=False))


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

    doctor = subparsers.add_parser(
        "doctor",
        help="Run a no-CST-start compatibility self-check.",
        epilog=DIRECT_TOOL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_workspace_arg(doctor)
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

    if args.command == "doctor":
        return _json_response(_doctor(str(getattr(args, "workspace", "") or "")))

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
        if args.output:
            output = Path(args.output).expanduser().resolve()
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
    tool_args = {**tool_args, **_direct_args_from_namespace(args, tool_name)}
    if tool_name in TOOLS and _tool_requires_workspace(tool_name):
        workspace_info = _workspace_status_for_command(str(getattr(args, "workspace", "") or ""), tool_args)
        if not workspace_info.get("workspace_initialized"):
            return _json_response(_workspace_required_error(workspace_info))

    if tool_name in TOOLS:
        missing_modules = _missing_imports_for_tool(tool_name)
        if missing_modules:
            return _json_response(_production_dependency_error(tool_name, missing_modules))

    return _json_response(_invoke_tool(tool_name, tool_args))


if __name__ == "__main__":
    raise SystemExit(main())
