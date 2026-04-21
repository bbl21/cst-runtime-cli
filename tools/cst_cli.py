from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import cst.interface


REPO_ROOT = Path(__file__).resolve().parent.parent
warnings.filterwarnings("ignore", category=DeprecationWarning)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    return 0


def _load_json_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.args_json and args.args_file:
        raise ValueError("--args-json and --args-file are mutually exclusive")
    if args.args_json:
        return json.loads(args.args_json)
    if args.args_file:
        return json.loads(Path(args.args_file).read_text(encoding="utf-8-sig"))
    return {}


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def _project_path_from_args(args: dict[str, Any]) -> str:
    project_path = args.get("project_path") or args.get("fullpath") or args.get("working_project")
    if not project_path:
        raise ValueError("project_path is required")
    return str(project_path)


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe[:80] or "tool"


def _infer_run_dir(project_path: str) -> Path | None:
    path = Path(project_path).expanduser().resolve()
    if path.parent.name.lower() == "projects":
        return path.parent.parent
    return None


def _write_audit(tool_name: str, tool_args: dict[str, Any], result: dict[str, Any]) -> dict[str, str] | None:
    project_path = tool_args.get("project_path") or tool_args.get("fullpath") or tool_args.get("working_project")
    if not project_path:
        return None
    run_dir = _infer_run_dir(str(project_path))
    if run_dir is None:
        return None

    logs_dir = run_dir / "logs"
    stages_dir = run_dir / "stages"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stages_dir.mkdir(parents=True, exist_ok=True)

    audit_payload = {
        "timestamp": _now_iso(),
        "adapter": "cst_cli_poc",
        "tool": tool_name,
        "args": tool_args,
        "status": result.get("status"),
        "result": result,
    }
    tool_calls_path = logs_dir / "tool_calls.jsonl"
    with tool_calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_payload, ensure_ascii=False, default=_json_default) + "\n")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stage_path = stages_dir / f"cli_{stamp}_{_safe_name(tool_name)}.json"
    stage_path.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )
    return {
        "tool_calls_jsonl": stage_path.parent.parent.joinpath("logs", "tool_calls.jsonl").as_posix(),
        "stage_file": stage_path.as_posix(),
    }


def _with_audit(tool_name: str, tool_args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    audit = _write_audit(tool_name, tool_args, result)
    if audit:
        result = {**result, "audit": audit}
    return result


def _connect_to_any():
    try:
        return cst.interface.DesignEnvironment.connect_to_any()
    except Exception as exc:
        return None, str(exc)


def _list_open_project_paths() -> tuple[list[str], str | None]:
    connected = _connect_to_any()
    if isinstance(connected, tuple):
        return [], connected[1]
    de = connected
    try:
        paths = list(de.list_open_projects() or [])
        return [str(path) for path in paths], None
    except Exception as exc:
        return [], str(exc)


def _attach_expected_project(project_path: str) -> tuple[Any | None, dict[str, Any]]:
    expected = _normalize_path(project_path)
    connected = _connect_to_any()
    if isinstance(connected, tuple):
        return None, {
            "status": "error",
            "error_type": "no_cst_session",
            "message": connected[1],
            "expected_project_path": os.path.abspath(project_path),
        }

    de = connected
    try:
        open_projects = list(de.list_open_projects() or [])
    except Exception as exc:
        return None, {
            "status": "error",
            "error_type": "list_open_projects_failed",
            "message": str(exc),
            "expected_project_path": os.path.abspath(project_path),
        }

    normalized_open = [_normalize_path(path) for path in open_projects]
    matching = [path for path, normalized in zip(open_projects, normalized_open) if normalized == expected]
    if not matching:
        return None, {
            "status": "error",
            "error_type": "project_not_open",
            "expected_project_path": os.path.abspath(project_path),
            "open_projects": open_projects,
        }

    # CST's public Python API exposes active_project(), not an obvious project-by-path lookup.
    # To avoid silent misoperation, this POC only mutates when the expected project is the sole open project.
    if len(open_projects) != 1:
        return None, {
            "status": "error",
            "error_type": "ambiguous_open_projects",
            "message": "Refusing to attach because multiple CST projects are open in this POC.",
            "expected_project_path": os.path.abspath(project_path),
            "open_projects": open_projects,
        }

    try:
        if not de.has_active_project():
            return None, {
                "status": "error",
                "error_type": "no_active_project",
                "expected_project_path": os.path.abspath(project_path),
                "open_projects": open_projects,
            }
        return de.active_project(), {
            "status": "success",
            "expected_project_path": os.path.abspath(project_path),
            "open_projects": open_projects,
        }
    except Exception as exc:
        return None, {
            "status": "error",
            "error_type": "attach_active_project_failed",
            "message": str(exc),
            "expected_project_path": os.path.abspath(project_path),
            "open_projects": open_projects,
        }


def _load_advanced_mcp_module():
    module_path = REPO_ROOT / "mcp" / "advanced_mcp.py"
    spec = importlib.util.spec_from_file_location("cst_cli_advanced_mcp", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load advanced_mcp.py: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool_list_open_projects(args: dict[str, Any]) -> dict[str, Any]:
    open_projects, error = _list_open_project_paths()
    if error:
        return {
            "status": "error",
            "error_type": "list_open_projects_failed",
            "message": error,
            "open_projects": [],
        }
    return {
        "status": "success",
        "open_projects": [
            {
                "project_path": os.path.abspath(path),
                "project_name": Path(path).stem,
            }
            for path in open_projects
        ],
        "count": len(open_projects),
    }


def tool_assert_project_open(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    _, status = _attach_expected_project(project_path)
    return status


def tool_open_project(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    normalized_project = os.path.abspath(project_path)
    if not normalized_project.lower().endswith(".cst"):
        normalized_project += ".cst"
    if not Path(normalized_project).is_file():
        return {
            "status": "error",
            "error_type": "project_file_missing",
            "project_path": normalized_project,
        }

    current, _ = _attach_expected_project(normalized_project)
    if current is not None:
        return {
            "status": "success",
            "project_path": normalized_project,
            "already_open": True,
        }

    try:
        de = cst.interface.DesignEnvironment()
        de.open_project(normalized_project)
        open_projects, list_error = _list_open_project_paths()
        result = {
            "status": "success",
            "project_path": normalized_project,
            "already_open": False,
            "open_projects": open_projects,
        }
        if list_error:
            result["warning"] = list_error
        return result
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "open_project_failed",
            "project_path": normalized_project,
            "message": str(exc),
        }


def tool_close_project(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    save = bool(args.get("save", False))
    project, status = _attach_expected_project(project_path)
    if project is None:
        return status
    try:
        if save:
            project.save()
        project.close()
        return {
            "status": "success",
            "project_path": os.path.abspath(project_path),
            "saved": save,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "close_project_failed",
            "project_path": os.path.abspath(project_path),
            "message": str(exc),
        }


def tool_list_parameters(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    project, status = _attach_expected_project(project_path)
    if project is None:
        return status
    try:
        m3d = project.model3d
        params: dict[str, Any] = {}
        for index in range(int(m3d.GetNumberOfParameters())):
            name = m3d.GetParameterName(index)
            try:
                value = m3d.RestoreDoubleParameter(name)
            except Exception:
                value = None
            params[name] = round(value, 6) if isinstance(value, float) else value
        return {
            "status": "success",
            "project_path": os.path.abspath(project_path),
            "parameters": params,
            "count": len(params),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "list_parameters_failed",
            "project_path": os.path.abspath(project_path),
            "message": str(exc),
        }


def tool_change_parameter(args: dict[str, Any]) -> dict[str, Any]:
    project_path = _project_path_from_args(args)
    name = args.get("name") or args.get("parameter") or args.get("para_name")
    if not name:
        raise ValueError("name/parameter/para_name is required")
    if "value" in args:
        value = args["value"]
    elif "para_value" in args:
        value = args["para_value"]
    else:
        raise ValueError("value/para_value is required")

    project, status = _attach_expected_project(project_path)
    if project is None:
        return status
    try:
        project.modeler.add_to_history("ChangeParameter", f'StoreDoubleParameter "{name}", {value}')
        return {
            "status": "success",
            "project_path": os.path.abspath(project_path),
            "changed": {str(name): value},
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "change_parameter_failed",
            "project_path": os.path.abspath(project_path),
            "message": str(exc),
        }


def tool_prepare_run(args: dict[str, Any]) -> dict[str, Any]:
    module = _load_advanced_mcp_module()
    return module.prepare_new_run(**args)


ToolFunc = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: dict[str, dict[str, Any]] = {
    "list-open-projects": {
        "category": "project",
        "risk": "read",
        "description": "List CST projects currently visible through CST DesignEnvironment.",
        "requires_project_path": False,
        "function": tool_list_open_projects,
    },
    "assert-project-open": {
        "category": "project",
        "risk": "read",
        "description": "Verify that the expected project_path is the sole open CST project in this POC.",
        "requires_project_path": True,
        "function": tool_assert_project_open,
    },
    "open-project": {
        "category": "project",
        "risk": "session",
        "description": "Open a CST project by explicit project_path.",
        "requires_project_path": True,
        "function": tool_open_project,
    },
    "close-project": {
        "category": "project",
        "risk": "session",
        "description": "Close the expected CST project after identity verification; defaults to save=false.",
        "requires_project_path": True,
        "function": tool_close_project,
    },
    "list-parameters": {
        "category": "modeler",
        "risk": "read",
        "description": "List CST model parameters after verifying the expected project_path.",
        "requires_project_path": True,
        "function": tool_list_parameters,
    },
    "change-parameter": {
        "category": "modeler",
        "risk": "write",
        "description": "Change one CST parameter in the verified project using StoreDoubleParameter.",
        "requires_project_path": True,
        "function": tool_change_parameter,
    },
    "prepare-run": {
        "category": "run",
        "risk": "filesystem-write",
        "description": "Create a standard run workspace by reusing the existing prepare_new_run implementation.",
        "requires_project_path": False,
        "function": tool_prepare_run,
    },
}


def _public_tool_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
        "requires_project_path": record["requires_project_path"],
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
    func: ToolFunc = record["function"]
    try:
        result = func(tool_args)
    except Exception as exc:
        result = {
            "status": "error",
            "error_type": "tool_exception",
            "tool": tool_name,
            "message": str(exc),
        }
    result.setdefault("tool", tool_name)
    result.setdefault("adapter", "cst_cli_poc")
    return _with_audit(tool_name, tool_args, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="POC agent-friendly CLI for CST_MCP tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-tools", help="List available POC tools.")

    describe = subparsers.add_parser("describe-tool", help="Describe a POC tool.")
    describe.add_argument("--tool", required=True)

    invoke = subparsers.add_parser("invoke", help="Invoke a POC tool with JSON arguments.")
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
                "adapter": "cst_cli_poc",
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
                "adapter": "cst_cli_poc",
                "tool": _public_tool_record(args.tool, record),
                "input_style": "Pass arguments with --args-file path.json or --args-json '{...}'.",
                "output_style": "JSON object with status, tool data, and audit paths when a run project_path is provided.",
            }
        )

    tool_name = args.tool if args.command == "invoke" else args.command
    tool_args = _load_json_args(args)
    return _json_response(_invoke_tool(tool_name, tool_args))


if __name__ == "__main__":
    raise SystemExit(main())
