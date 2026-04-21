from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import error_response
from .project_identity import attach_expected_project


def _abs_project_path(project_path: str) -> str:
    normalized = os.path.abspath(os.path.expanduser(project_path))
    if not normalized.lower().endswith(".cst"):
        normalized += ".cst"
    return normalized


def _connect_new_design_environment():
    import cst.interface

    return cst.interface.DesignEnvironment()


def open_project(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    if not Path(normalized_project).is_file():
        return error_response(
            "project_file_missing",
            "project_path does not exist",
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )

    current, _ = attach_expected_project(normalized_project)
    if current is not None:
        return {
            "status": "success",
            "project_path": normalized_project,
            "already_open": True,
            "runtime_module": "cst_runtime.modeler",
        }

    try:
        de = _connect_new_design_environment()
        de.open_project(normalized_project)
        return {
            "status": "success",
            "project_path": normalized_project,
            "already_open": False,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "open_project_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def close_project(project_path: str, save: bool = False) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        if save:
            project.save()
        project.close()
        return {
            "status": "success",
            "project_path": normalized_project,
            "saved": save,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "close_project_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def save_project(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.save()
        return {
            "status": "success",
            "project_path": normalized_project,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "save_project_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def list_parameters(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
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
            "project_path": normalized_project,
            "parameters": params,
            "count": len(params),
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "list_parameters_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def change_parameter(project_path: str, name: str = "", value: float | int | str | None = None, **aliases: Any) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    parameter_name = name or aliases.get("parameter") or aliases.get("para_name") or ""
    parameter_value = value if value is not None else aliases.get("para_value")
    if not parameter_name:
        return error_response("parameter_name_missing", "name/parameter/para_name is required")
    if parameter_value is None:
        return error_response("parameter_value_missing", "value/para_value is required")

    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.add_to_history(
            "ChangeParameter",
            f'StoreDoubleParameter "{parameter_name}", {parameter_value}',
        )
        return {
            "status": "success",
            "project_path": normalized_project,
            "changed": {str(parameter_name): parameter_value},
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "change_parameter_failed",
            str(exc),
            project_path=normalized_project,
            parameter=str(parameter_name),
            runtime_module="cst_runtime.modeler",
        )


def start_simulation(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.run_solver()
        return {
            "status": "success",
            "project_path": normalized_project,
            "message": "simulation completed",
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "start_simulation_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def start_simulation_async(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.start_solver()
        return {
            "status": "success",
            "project_path": normalized_project,
            "message": "simulation started",
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "start_simulation_async_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


def is_simulation_running(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        running = bool(project.modeler.is_solver_running())
        return {
            "status": "success",
            "project_path": normalized_project,
            "running": running,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "is_simulation_running_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )
