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
import warnings
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cst_runtime import audit, farfield, modeler, project_identity, results, run_workspace

warnings.filterwarnings("ignore", category=DeprecationWarning)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        payload = {
            "status": "error",
            "error_type": "cli_usage_error",
            "message": message,
            "usage": self.format_usage().strip(),
            "adapter": "cst_runtime_cli",
            "next_steps": [
                "Run: python -m cst_runtime doctor",
                "Run: uv run python -m cst_runtime usage-guide",
                "Run: uv run python -m cst_runtime list-tools",
                "Run: uv run python -m cst_runtime describe-tool --tool <tool>",
                "Run: uv run python -m cst_runtime args-template --tool <tool> --output <args.json>",
            ],
        }
        tools = globals().get("TOOLS")
        if isinstance(tools, dict):
            payload["available_tools"] = sorted(tools)
        print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
        raise SystemExit(2)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
    return 0 if payload.get("status") != "error" else 1


def _usage_guide() -> dict[str, Any]:
    return {
        "status": "success",
        "adapter": "cst_runtime_cli",
        "entrypoint": "uv run python -m cst_runtime",
        "fallback_entrypoint": "python -m cst_runtime",
        "error_contract": {
            "stdout": "Always read stdout as JSON for CLI/runtime commands and usage errors.",
            "success": "status == 'success'",
            "failure": "status == 'error'; inspect error_type/message and stop unless the next step explicitly handles it.",
            "exit_code": "Non-zero exit means failure, but agents must still parse stdout JSON.",
        },
        "agent_steps": [
            "Run doctor first when using a new shell, machine, IDE agent, or migrated workspace.",
            "Run list-tools to discover tool names.",
            "Run describe-tool --tool <tool> before first use.",
            "Run args-template --tool <tool> --output <run-or-task>\\stages\\<tool>_args.json.",
            "Edit the args file; prefer args-file over inline JSON for Windows paths.",
            "Invoke the tool with --args-file or pipe JSON to stdin.",
            "After every call, check status before continuing.",
        ],
        "input_styles": {
            "args_file": "uv run python -m cst_runtime <tool> --args-file C:\\path\\to\\args.json",
            "stdin": "@{ project_path = $workingProject } | ConvertTo-Json -Depth 8 | uv run python -m cst_runtime <tool>",
            "merge": "When using stdin together with --args-file/--args-json, add --args-stdin. Stdin JSON is loaded first; explicit args override same-name fields.",
        },
        "safe_discovery_commands": [
            "python -m cst_runtime doctor",
            "uv run python -m cst_runtime usage-guide",
            "uv run python -m cst_runtime list-tools",
            "uv run python -m cst_runtime describe-tool --tool get-1d-result",
            "uv run python -m cst_runtime args-template --tool get-1d-result",
        ],
        "tool_families": {
            "run": ["prepare-run", "get-run-context"],
            "audit": ["record-stage", "update-status"],
            "project_identity": ["infer-run-dir", "wait-project-unlocked", "verify-project-identity", "list-open-projects"],
            "modeler": ["open-project", "list-parameters", "change-parameter", "start-simulation-async", "is-simulation-running", "save-project", "close-project"],
            "results": ["open-results-project", "list-run-ids", "get-parameter-combination", "get-1d-result", "get-2d-result", "generate-s11-comparison", "plot-exported-file"],
            "farfield": ["export-farfield-fresh-session", "read-realized-gain-grid-fresh-session", "inspect-farfield-ascii", "plot-farfield-multi"],
        },
        "hard_rules": [
            "Use explicit project_path for CST project operations.",
            "Do not edit ref/ source projects; operate on a run working copy.",
            "Do not treat Abs(E) as dBi; use Realized Gain/Gain/Directivity for gain evidence.",
            "Do not continue a pipeline after status == 'error' unless the recovery step is explicit.",
        ],
    }


def _check_import(module_name: str) -> dict[str, Any]:
    try:
        __import__(module_name)
        return {"name": f"import:{module_name}", "status": "success"}
    except Exception as exc:
        return {"name": f"import:{module_name}", "status": "warning", "message": str(exc)}


def _doctor() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    uv_path = shutil.which("uv")
    checks.append(
        {
            "name": "uv_on_path",
            "status": "success" if uv_path else "warning",
            "path": uv_path,
            "message": None if uv_path else "uv not found on PATH; use python -m cst_runtime if dependencies are already available.",
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
    pyproject_path = REPO_ROOT / "pyproject.toml"
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
            else "pyproject CST path dependency is missing or not readable on this machine; uv run may fail before the CLI starts.",
        }
    )
    checks.append(
        {
            "name": "repo_root",
            "status": "success" if REPO_ROOT.exists() else "error",
            "path": str(REPO_ROOT),
            "cwd": str(Path.cwd()),
            "pyproject_exists": (REPO_ROOT / "pyproject.toml").exists(),
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

    warning_count = sum(1 for item in checks if item.get("status") == "warning")
    error_count = sum(1 for item in checks if item.get("status") == "error")
    readiness = "ready" if error_count == 0 and warning_count == 0 else "degraded"
    if error_count:
        readiness = "blocked"
    return {
        "status": "success",
        "adapter": "cst_runtime_cli",
        "readiness": readiness,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "recommended_entrypoints": [
            "uv run python -m cst_runtime <command>",
            "python -m cst_runtime <command>",
        ],
        "checks": checks,
        "compatibility_notes": [
            "Use --args-file for Windows paths and cross-shell compatibility.",
            "When combining stdin with --args-file or --args-json, add --args-stdin.",
            "If uv cannot resolve the CST absolute path dependency on a migrated machine, run python -m cst_runtime doctor from an environment where CST Python libraries are already on PYTHONPATH.",
            "Meta commands such as doctor, usage-guide, list-tools, describe-tool, and args-template do not start CST.",
        ],
    }


def _tool_runbook(tool_name: str) -> dict[str, Any]:
    return {
        "discover": f"uv run python -m cst_runtime describe-tool --tool {tool_name}",
        "template": f"uv run python -m cst_runtime args-template --tool {tool_name} --output <args.json>",
        "invoke": f"uv run python -m cst_runtime {tool_name} --args-file <args.json>",
        "pipe": f"<json-producing-command> | uv run python -m cst_runtime {tool_name}",
        "pipe_with_args_file": f"<json-producing-command> | uv run python -m cst_runtime {tool_name} --args-stdin --args-file <args.json>",
        "must_check": "Read stdout JSON and require status == 'success' before the next step.",
    }


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


ARGS_TEMPLATES: dict[str, dict[str, Any]] = {
    "prepare-run": {
        "task_path": "C:\\path\\to\\tasks\\task_xxx",
    },
    "get-run-context": {
        "task_path": "C:\\path\\to\\tasks\\task_xxx",
        "run_id": "",
    },
    "record-stage": {
        "task_path": "C:\\path\\to\\tasks\\task_xxx",
        "run_id": "run_001",
        "stage": "cli_runtime_iteration",
        "status": "completed",
        "message": "",
        "details_json": "{}",
    },
    "update-status": {
        "task_path": "C:\\path\\to\\tasks\\task_xxx",
        "run_id": "run_001",
        "status": "validated",
        "stage": "cli_runtime_iteration",
        "best_result_json": "{}",
        "output_files_json": "{}",
        "error_json": "",
        "extra_json": "{}",
    },
    "open-project": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "close-project": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "save": False,
    },
    "save-project": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "list-parameters": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "change-parameter": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "name": "R",
        "value": 0.102,
    },
    "start-simulation": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "start-simulation-async": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "is-simulation-running": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "infer-run-dir": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "wait-project-unlocked": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "timeout_seconds": 30,
        "poll_interval_seconds": 0.5,
    },
    "list-open-projects": {},
    "verify-project-identity": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
    },
    "open-results-project": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "allow_interactive": False,
        "subproject_treepath": "",
    },
    "get-version-info": {},
    "list-result-items": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "module_type": "3d",
        "filter_type": "0D/1D",
        "allow_interactive": False,
        "subproject_treepath": "",
    },
    "list-run-ids": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "treepath": "1D Results\\S-Parameters\\S1,1",
        "module_type": "3d",
        "allow_interactive": False,
        "skip_nonparametric": False,
        "max_mesh_passes_only": False,
    },
    "get-parameter-combination": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "run_id": 1,
        "module_type": "3d",
        "allow_interactive": False,
    },
    "get-1d-result": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "treepath": "1D Results\\S-Parameters\\S1,1",
        "module_type": "3d",
        "run_id": 1,
        "load_impedances": True,
        "export_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run1.json",
        "allow_interactive": False,
    },
    "get-2d-result": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "treepath": "2D/3D Results\\example",
        "module_type": "3d",
        "export_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\result_2d.json",
        "allow_interactive": False,
        "subproject_treepath": "",
        "include_data": False,
    },
    "plot-exported-file": {
        "file_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run1.json",
        "output_html": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\result_preview.html",
        "page_title": "CST Result Preview",
    },
    "generate-s11-comparison": {
        "file_paths": [
            "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run0.json",
            "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run1.json",
        ],
        "output_html": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_comparison.html",
        "page_title": "S11 Comparison",
    },
    "inspect-farfield-ascii": {
        "file_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\farfield_13ghz_port1.txt",
    },
    "export-farfield-fresh-session": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "farfield_name": "farfield (f=13) [1]",
        "output_file": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\farfield_13ghz_port1_realized_gain.txt",
        "plot_mode": "Realized Gain",
        "prime_with_cut": False,
        "cut_axis": "Phi",
        "cut_angle": "0",
        "theta_step_deg": 1.0,
        "phi_step_deg": 2.0,
        "theta_min_deg": 0.0,
        "theta_max_deg": 15.0,
        "phi_min_deg": 0.0,
        "phi_max_deg": 360.0,
        "max_attempts": 6,
        "keep_prime_cut_file": False,
    },
    "export-existing-farfield-cut-fresh-session": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "tree_path": "Farfields\\Farfield Cuts\\Excitation [1]\\Phi=0\\farfield (f=13)",
        "output_file": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\farfield_cut_phi0_port1.txt",
    },
    "read-realized-gain-grid-fresh-session": {
        "project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst",
        "farfield_name": "farfield (f=13) [1]",
        "run_id": "",
        "theta_step_deg": 1.0,
        "phi_step_deg": 2.0,
        "theta_min_deg": 0.0,
        "theta_max_deg": 15.0,
        "phi_min_deg": 0.0,
        "phi_max_deg": 360.0,
        "selection_tree_path": "1D Results\\S-Parameters",
        "output_json": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\realized_gain_grid.json",
    },
    "calculate-farfield-neighborhood-flatness": {
        "file_paths": [
            "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_cut_phi0_port1.json",
            "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_cut_phi90_port1.json",
        ],
        "theta_max_deg": 15.0,
        "output_json": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_flatness.json",
    },
    "plot-farfield-multi": {
        "file_paths": [
            "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\farfield_13ghz_port1_realized_gain.txt"
        ],
        "output_html": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\farfield_preview.html",
        "page_title": "Farfield Preview",
    },
}


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
    "generate-s11-comparison": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Generate an HTML S11 comparison from exported JSON files.",
        "function": tool_generate_s11_comparison,
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
}


def _public_tool_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "category": record["category"],
        "risk": record["risk"],
        "description": record["description"],
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
    parser = JsonArgumentParser(description="CLI adapter for cst_runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    subparsers.add_parser("doctor", help="Run a no-CST-start compatibility self-check.")
    subparsers.add_parser("list-tools", help="List available runtime tools.")
    subparsers.add_parser("usage-guide", help="Print a machine-readable agent usage guide.")

    describe = subparsers.add_parser("describe-tool", help="Describe a runtime tool.")
    describe.add_argument("--tool", required=True)

    args_template = subparsers.add_parser("args-template", help="Print or write a JSON args template for a runtime tool.")
    args_template.add_argument("--tool", required=True)
    args_template.add_argument("--output")

    invoke = subparsers.add_parser("invoke", help="Invoke a runtime tool with JSON arguments.")
    invoke.add_argument("--tool", required=True)
    invoke.add_argument("--args-json")
    invoke.add_argument("--args-file")
    invoke.add_argument("--args-stdin", action="store_true")

    for tool_name in sorted(TOOLS):
        direct = subparsers.add_parser(tool_name, help=TOOLS[tool_name]["description"])
        direct.add_argument("--args-json")
        direct.add_argument("--args-file")
        direct.add_argument("--args-stdin", action="store_true")

    args = parser.parse_args()

    if args.command == "doctor":
        return _json_response(_doctor())

    if args.command == "list-tools":
        return _json_response(
            {
                "status": "success",
                "adapter": "cst_runtime_cli",
                "tools": [_public_tool_record(name, TOOLS[name]) for name in sorted(TOOLS)],
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
                "input_style": "Pass arguments with --args-file path.json, --args-json '{...}', --args-stdin, or pipe JSON to stdin. Stdin args merge first; explicit args override them.",
                "output_style": "JSON object; production calls also write run audit when project_path maps to a run.",
            }
        )

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
                "usage": f"uv run python -m cst_runtime {args.tool} --args-file {output_path or '<args.json>'}",
                "pipe_usage": f"<json-producing-command> | uv run python -m cst_runtime {args.tool}",
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
