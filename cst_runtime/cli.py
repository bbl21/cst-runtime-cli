from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cst_runtime import audit, modeler, project_identity, results, run_workspace

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    return 0 if payload.get("status") != "error" else 1


def _load_json_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.args_json and args.args_file:
        raise ValueError("--args-json and --args-file are mutually exclusive")
    if args.args_json:
        return json.loads(args.args_json)
    if args.args_file:
        return json.loads(Path(args.args_file).read_text(encoding="utf-8-sig"))
    return {}


def _with_audit(tool_name: str, tool_args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    project_path = tool_args.get("project_path") or tool_args.get("fullpath") or tool_args.get("working_project")
    run_dir = None
    if project_path:
        run_dir = project_identity.infer_run_dir_from_project(str(project_path))
    if run_dir is None:
        for key in ("output_html", "export_path", "output_file"):
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
    return project_identity.project_path_from_args(args)


def tool_prepare_run(args: dict[str, Any]) -> dict[str, Any]:
    return run_workspace.prepare_new_run(**args)


def tool_get_run_context(args: dict[str, Any]) -> dict[str, Any]:
    return run_workspace.get_run_context(**args)


def tool_record_stage(args: dict[str, Any]) -> dict[str, Any]:
    return audit.record_run_stage(**args)


def tool_update_status(args: dict[str, Any]) -> dict[str, Any]:
    return audit.update_run_status(**args)


def tool_open_project(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.open_project(_project_path_from_args(args))


def tool_close_project(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.close_project(
        project_path=_project_path_from_args(args),
        save=bool(args.get("save", False)),
    )


def tool_save_project(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.save_project(_project_path_from_args(args))


def tool_list_parameters(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.list_parameters(_project_path_from_args(args))


def tool_change_parameter(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    tool_args = {key: value for key, value in args.items() if key not in {"project_path", "fullpath", "working_project"}}
    return modeler.change_parameter(project_path=project_path, **tool_args)


def tool_start_simulation(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.start_simulation(_project_path_from_args(args))


def tool_start_simulation_async(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.start_simulation_async(_project_path_from_args(args))


def tool_is_simulation_running(args: dict[str, Any]) -> dict[str, Any]:
    return modeler.is_simulation_running(_project_path_from_args(args))


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


def tool_get_parameter_combination(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_parameter_combination(
        project_path=_project_path_from_args(args),
        run_id=int(args.get("run_id", 0)),
        module_type=str(args.get("module_type", "3d")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_get_1d_result(args: dict[str, Any]) -> dict[str, Any]:
    return results.get_1d_result(
        project_path=_project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        run_id=int(args.get("run_id", 0)),
        load_impedances=bool(args.get("load_impedances", True)),
        export_path=str(args.get("export_path", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_generate_s11_comparison(args: dict[str, Any]) -> dict[str, Any]:
    file_paths = args.get("file_paths", [])
    if isinstance(file_paths, str):
        file_paths = json.loads(file_paths)
    return results.generate_s11_comparison(
        file_paths=[str(path) for path in file_paths],
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
    )


ToolFunc = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: dict[str, dict[str, Any]] = {
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
    "open-project": {
        "category": "modeler",
        "risk": "session",
        "description": "Open a CST working project by explicit project_path.",
        "function": tool_open_project,
    },
    "close-project": {
        "category": "modeler",
        "risk": "session",
        "description": "Close the verified CST working project; defaults to save=false.",
        "function": tool_close_project,
    },
    "save-project": {
        "category": "modeler",
        "risk": "filesystem-write",
        "description": "Save the verified CST working project.",
        "function": tool_save_project,
    },
    "list-parameters": {
        "category": "modeler",
        "risk": "read",
        "description": "List parameters from the verified CST working project.",
        "function": tool_list_parameters,
    },
    "change-parameter": {
        "category": "modeler",
        "risk": "write",
        "description": "Change one CST parameter in the verified working project.",
        "function": tool_change_parameter,
    },
    "start-simulation": {
        "category": "modeler",
        "risk": "long-running",
        "description": "Run the CST solver synchronously for the verified working project.",
        "function": tool_start_simulation,
    },
    "start-simulation-async": {
        "category": "modeler",
        "risk": "long-running",
        "description": "Start the CST solver asynchronously for the verified working project.",
        "function": tool_start_simulation_async,
    },
    "is-simulation-running": {
        "category": "modeler",
        "risk": "read",
        "description": "Check whether the CST solver is currently running for the verified working project.",
        "function": tool_is_simulation_running,
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
    "generate-s11-comparison": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Generate an HTML S11 comparison from exported JSON files.",
        "function": tool_generate_s11_comparison,
    },
}


def _public_tool_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
    }


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
        result = record["function"](tool_args)
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
    parser = argparse.ArgumentParser(description="CLI adapter for cst_runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-tools", help="List available runtime tools.")

    describe = subparsers.add_parser("describe-tool", help="Describe a runtime tool.")
    describe.add_argument("--tool", required=True)

    invoke = subparsers.add_parser("invoke", help="Invoke a runtime tool with JSON arguments.")
    invoke.add_argument("--tool", required=True)
    invoke.add_argument("--args-json")
    invoke.add_argument("--args-file")

    for tool_name in sorted(TOOLS):
        direct = subparsers.add_parser(tool_name, help=TOOLS[tool_name]["description"])
        direct.add_argument("--args-json")
        direct.add_argument("--args-file")

    args = parser.parse_args()

    if args.command == "list-tools":
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "tools": [_public_tool_record(name, TOOLS[name]) for name in sorted(TOOLS)],
            }
        )

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
                "input_style": "Pass arguments with --args-file path.json or --args-json '{...}'.",
                "output_style": "JSON object; production calls also write run audit when project_path maps to a run.",
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
    return _json_response(_invoke_tool(tool_name, tool_args))


if __name__ == "__main__":
    raise SystemExit(main())
