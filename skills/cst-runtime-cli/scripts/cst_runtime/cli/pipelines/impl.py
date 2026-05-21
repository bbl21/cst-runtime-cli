from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from ...core.errors import error_response
from ...core.utils import safe_log_db as _safe_log_db


def _parse_s11_json(file_path: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
        xdata = payload.get("xdata") or []
        ydata = payload.get("ydata") or []
        if not xdata or not ydata:
            return None
        db_values: list[float] = []
        for item in ydata:
            if isinstance(item, dict):
                real = float(item.get("real", 0.0))
                imag = float(item.get("imag", 0.0))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                real, imag = float(item[0]), float(item[1])
            elif isinstance(item, (int, float)):
                real, imag = float(item), 0.0
            else:
                real, imag = 0.0, 0.0
            db_values.append(_safe_log_db(math.hypot(real, imag)))
        if not db_values:
            return None
        min_idx = db_values.index(min(db_values))
        return {
            "run_id": payload.get("run_id"),
            "min_db": min(db_values),
            "best_freq": xdata[min_idx] if min_idx < len(xdata) else None,
            "point_count": len(db_values),
            "file": Path(file_path).name,
        }
    except Exception:
        return None


def _max_exported_run_id(project_path: str) -> int:
    p = Path(project_path).expanduser().resolve()
    exports_dir = p.parent.parent / "exports"
    if not exports_dir.is_dir():
        return 0
    max_rid = 0
    for f in exports_dir.glob("s11_run*.json"):
        m = re.search(r"s11_run(\d+)\.json$", f.name)
        if m:
            max_rid = max(max_rid, int(m.group(1)))
    return max_rid


# ── inspect-project ──

def pipeline_inspect_project(project_path: str) -> dict[str, Any]:
    from ...core.session import open_project as sm_open, close_project as sm_close
    from ...core.project import list_parameters, list_entities
    from ...core.farfield import discover_farfield_monitors

    open_result = sm_open(project_path)
    if open_result.get("status") != "success":
        return error_response(
            "pipeline_open_failed",
            open_result.get("message", "failed to open project"),
            step="inspect-project:open",
            open_result=open_result,
        )

    params = list_parameters(project_path)
    if params.get("status") != "success":
        sm_close(project_path, save=False)
        return error_response(
            "pipeline_list_params_failed",
            params.get("message", "failed to list parameters"),
            step="inspect-project:list-params",
        )

    entities = list_entities(project_path)
    if entities.get("status") != "success":
        sm_close(project_path, save=False)
        return error_response(
            "pipeline_list_entities_failed",
            entities.get("message", "failed to list entities"),
            step="inspect-project:list-entities",
        )

    farfield_info = discover_farfield_monitors(project_path)

    close_result = sm_close(project_path, save=False)
    ff_count = farfield_info.get("count", 0) if farfield_info.get("status") == "success" else 0
    ff_names = farfield_info.get("farfield_names", []) if ff_count > 0 else []
    return {
        "status": "success",
        "pipeline": "inspect-project",
        "project_path": open_result.get("project_path", project_path),
        "parameters": params.get("parameters", {}),
        "parameters_count": params.get("count", 0),
        "entities": entities.get("entities", []),
        "entities_count": entities.get("count", 0),
        "farfield_monitors": ff_names,
        "farfield_monitors_count": ff_count,
        "close_status": close_result.get("status", "unknown"),
    }


# ── prepare-experiment ──

def pipeline_prepare_experiment(
    project_path: str,
    param_name: str = "",
    param_value: float = 0,
    names: list[str] | None = None,
    values: list[float] | None = None,
) -> dict[str, Any]:
    from ...core.session import open_project as sm_open, close_project as sm_close
    from ...core.project import change_parameter, list_parameters, save_project

    resolved_names: list[str] = []
    resolved_values: list[float] = []
    if names and values:
        resolved_names = names
        resolved_values = values
    elif param_name:
        resolved_names = [param_name]
        resolved_values = [param_value]
    else:
        return error_response(
            "pipeline_param_missing",
            "provide param_name+param_value or names+values",
            step="prepare-experiment:validate",
        )

    if len(resolved_names) != len(resolved_values):
        return error_response(
            "pipeline_param_count_mismatch",
            f"names ({len(resolved_names)}) != values ({len(resolved_values)})",
            step="prepare-experiment:validate",
        )

    open_result = sm_open(project_path)
    if open_result.get("status") != "success":
        return open_result

    all_changed: dict[str, Any] = {}
    for n, v in zip(resolved_names, resolved_values):
        cr = change_parameter(project_path=project_path, name=n, value=v)
        if cr.get("status") != "success":
            sm_close(project_path, save=False)
            return error_response(
                "pipeline_change_param_failed",
                cr.get("message", f"failed to change {n}={v}"),
                step="prepare-experiment:change-param",
                change_result=cr,
            )
        all_changed.update(cr.get("changed", {}))

    confirm_result = list_parameters(project_path)
    if confirm_result.get("status") != "success":
        sm_close(project_path, save=False)
        return error_response(
            "pipeline_confirm_params_failed",
            confirm_result.get("message", "failed to confirm parameter change"),
            step="prepare-experiment:confirm",
        )

    save_result = save_project(project_path)
    if save_result.get("status") != "success":
        sm_close(project_path, save=False)
        return error_response(
            "pipeline_save_failed",
            save_result.get("message", "failed to save project"),
            step="prepare-experiment:save",
        )

    sm_close(project_path, save=False)
    return {
        "status": "success",
        "pipeline": "prepare-experiment",
        "project_path": open_result.get("project_path", project_path),
        "changed": all_changed,
        "param_names": resolved_names,
        "param_values": resolved_values,
        "parameters": confirm_result.get("parameters", {}),
    }


# ── run-experiment ──

def pipeline_run_experiment(
    project_path: str,
    farfield_names: list[str] | None = None,
    farfield_plot_mode: str = "Realized Gain",
    farfield_theta_step: float = 2.0,
    farfield_phi_step: float = 2.0,
    timeout_seconds: int = 3600,
    poll_interval_seconds: float = 10.0,
) -> dict[str, Any]:
    from ...core.session import open_project as sm_open, close_project as sm_close
    from ...core.project import start_simulation_async, is_simulation_running
    from ...core.results import export_run_results

    # Record pre-existing exported file count to detect if solver produced new results.
    # Checks the exports/ directory before and after export:
    #   - mode A (existing project): file number must increase
    #   - mode B (new project): first file is created (0 → N)
    max_before_export = _max_exported_run_id(project_path)

    open_result = sm_open(project_path)
    if open_result.get("status") != "success":
        return error_response(
            "pipeline_open_failed",
            open_result.get("message", "failed to open project for simulation"),
            step="run-experiment:open",
        )

    sim_result = start_simulation_async(project_path)
    if sim_result.get("status") != "success":
        sm_close(project_path, save=False)
        return error_response(
            "pipeline_sim_start_failed",
            sim_result.get("message", "failed to start simulation"),
            step="run-experiment:start-sim",
        )

    import time
    polls = 0
    waited = 0.0
    while True:
        time.sleep(poll_interval_seconds)
        waited += poll_interval_seconds
        polls += 1
        running_result = is_simulation_running(project_path)
        if running_result.get("status") != "success":
            sm_close(project_path, save=False)
            return error_response(
                "pipeline_sim_check_failed",
                running_result.get("message", "failed to check simulation status"),
                step="run-experiment:check",
                polls=polls,
                waited_seconds=waited,
            )
        if not running_result.get("running", True):
            break
        if waited >= timeout_seconds:
            sm_close(project_path, save=False)
            return error_response(
                "pipeline_sim_timeout",
                f"simulation still running after {waited:.0f}s",
                step="run-experiment:timeout",
                polls=polls,
                timeout_seconds=timeout_seconds,
            )

    close_result = sm_close(project_path, save=False)
    if close_result.get("status") != "success":
        return error_response(
            "pipeline_close_failed",
            close_result.get("message", "failed to close modeler session"),
            step="run-experiment:close",
        )

    export_result = export_run_results(
        project_path=project_path,
        farfield_names=farfield_names,
        farfield_plot_mode=farfield_plot_mode,
        farfield_theta_step=farfield_theta_step,
        farfield_phi_step=farfield_phi_step,
    )
    if export_result.get("status") != "success":
        return error_response(
            "pipeline_export_failed",
            export_result.get("message", "failed to export results"),
            step="run-experiment:export",
            export_result=export_result,
        )

    exported_files = export_result.get("exported", [])
    s11_files = [f for f in exported_files if re.search(r"s11_run\d+\.json$", str(f), re.IGNORECASE)]
    farfield_files = [f for f in exported_files if re.search(r"farfield", str(f), re.IGNORECASE)]

    s11_metric = None
    s11_export_path = ""
    if s11_files:
        s11_export_path = str(s11_files[-1])
        s11_metric = _parse_s11_json(s11_export_path)

    run_id = s11_metric.get("run_id") if s11_metric else None

    # Verify solver produced new results by checking if exported file number increased
    max_after_export = _max_exported_run_id(project_path)
    solver_produced_new_data = max_after_export > max_before_export

    if not solver_produced_new_data:
        return {
            "status": "error",
            "error_type": "solver_did_not_complete",
            "message": (
                f"Solver did not produce new results: "
                f"exported file number {max_after_export} <= pre-existing {max_before_export}. "
                f"The simulation may have failed silently (e.g. mesh error, geometry issue). "
                f"Check CST solver logs in Result/*.log for details."
            ),
            "pipeline": "run-experiment",
            "project_path": project_path,
            "polls": polls,
            "waited_seconds": waited,
            "exported_count": len(exported_files),
            "exported": exported_files,
            "pre_export_max_file_num": max_before_export,
            "post_export_max_file_num": max_after_export,
        }

    output: dict[str, Any] = {
        "status": "success",
        "pipeline": "run-experiment",
        "project_path": open_result.get("project_path", project_path),
        "polls": polls,
        "waited_seconds": waited,
        "exported_count": len(exported_files),
        "exported": exported_files,
        "s11_export_path": s11_export_path,
        "s11_metric": s11_metric,
        "farfield_exported": farfield_files,
        "solver_completed": True,
        "pre_export_max_file_num": max_before_export,
        "post_export_max_file_num": max_after_export,
    }
    if run_id is not None:
        output["run_id"] = run_id
    return output
