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


def list_entities(project_path: str, component: str = "") -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        all_items = project.modeler.get_tree_items()
        sep = "\\"
        entity_paths = [item for item in all_items if str(item).startswith("Components" + sep)]
        entities: list[dict[str, str]] = []
        for path in entity_paths:
            parts = str(path).split(sep)
            if len(parts) < 3:
                continue
            entity_component = parts[1]
            name = sep.join(parts[2:])
            if not component or entity_component.lower() == component.lower():
                entities.append({"component": entity_component, "name": name})
        return {
            "status": "success",
            "project_path": normalized_project,
            "component_filter": component or None,
            "count": len(entities),
            "entities": entities,
            "tree_paths": entity_paths,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "list_entities_failed",
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
            runtime_module="cst_runtime.project_ops",
        )


def stop_simulation(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.abort_solver()
        return {
            "status": "success",
            "project_path": normalized_project,
            "runtime_module": "cst_runtime.project_ops",
        }
    except Exception as exc:
        return error_response(
            "stop_simulation_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.project_ops",
        )


def pause_simulation(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.pause_solver()
        return {
            "status": "success",
            "project_path": normalized_project,
            "message": "simulation paused",
            "runtime_module": "cst_runtime.project_ops",
        }
    except Exception as exc:
        return error_response(
            "pause_simulation_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.project_ops",
        )


def resume_simulation(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.resume_solver()
        return {
            "status": "success",
            "project_path": normalized_project,
            "message": "simulation resumed",
            "runtime_module": "cst_runtime.project_ops",
        }
    except Exception as exc:
        return error_response(
            "resume_simulation_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.project_ops",
        )


def set_solver_acceleration(
    project_path: str,
    use_parallelization: bool = True,
    max_threads: int = 1024,
    max_cpu_devices: int = 2,
    remote_calc: bool = False,
    use_distributed: bool = False,
    max_distributed_ports: int = 64,
    distribute_matrix: bool = True,
    mpi_parallel: bool = False,
    auto_mpi: bool = False,
    hardware_accel: bool = True,
    max_gpus: int = 4,
) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    def _b(v: bool) -> str:
        return "True" if v else "False"
    vba = [
        "With Solver",
        f'     .UseParallelization "{_b(use_parallelization)}"',
        f'     .MaximumNumberOfThreads "{max_threads}"',
        f'     .MaximumNumberOfCPUDevices "{max_cpu_devices}"',
        f'     .RemoteCalculation "{_b(remote_calc)}"',
        f'     .UseDistributedComputing "{_b(use_distributed)}"',
        f'     .MaxNumberOfDistributedComputingPorts "{max_distributed_ports}"',
        f'     .DistributeMatrixCalculation "{_b(distribute_matrix)}"',
        f'     .MPIParallelization "{_b(mpi_parallel)}"',
        f'     .AutomaticMPI "{_b(auto_mpi)}"',
        f'     .HardwareAcceleration "{_b(hardware_accel)}"',
        f'     .MaximumNumberOfGPUs "{max_gpus}"',
        "End With",
    ]
    try:
        sCommand = "\n".join(vba)
        project.modeler.add_to_history("Set Solver Acceleration", sCommand)
        return {"status": "success", "project_path": normalized_project, "runtime_module": "cst_runtime.project_ops"}
    except Exception as exc:
        return error_response("set_solver_acceleration_failed", str(exc), project_path=normalized_project, runtime_module="cst_runtime.project_ops")


def set_fdsolver_extrude_open_bc(project_path: str, enable: bool = True) -> dict[str, Any]:
    return _single_vba_pops(project_path, "set FDSolver ExtrudeOpenBC", f'FDSolver.ExtrudeOpenBC {"True" if enable else "False"}')


def set_mesh_fpbavoid_nonreg_unite(project_path: str, enable: bool = True) -> dict[str, Any]:
    return _single_vba_pops(project_path, "set Mesh.FPBAAvoidNonRegUnite", f'Mesh.FPBAAvoidNonRegUnite {"True" if enable else "False"}')


def set_mesh_minimum_step_number(project_path: str, num_steps: int = 5) -> dict[str, Any]:
    return _single_vba_pops(project_path, "set Mesh.MinimumStepNumber", f'Mesh.MinimumStepNumber "{num_steps}"')


def _single_vba_pops(project_path: str, history_name: str, vba_line: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        project.modeler.add_to_history(history_name, vba_line)
        return {"status": "success", "project_path": normalized_project, "runtime_module": "cst_runtime.project_ops"}
    except Exception as exc:
        return error_response(f"{history_name}_failed", str(exc), project_path=normalized_project, runtime_module="cst_runtime.project_ops")


def define_parameters(project_path: str, names: list[str], values: list[str]) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    if len(names) != len(values):
        return error_response("parameter_mismatch", "names and values must have the same length")
    try:
        dim = len(names)
        dim_decl = f"Dim names(1 To {dim}) As String\nDim values(1 To {dim}) As String\n"
        entries = "\n".join(f'names({i+1}) = "{names[i]}"\nvalues({i+1}) = "{values[i]}"' for i in range(dim))
        vba = f"{dim_decl}{entries}\nStoreParameters names, values"
        project.modeler.add_to_history("Define Parameters", vba)
        return {"status": "success", "project_path": normalized_project, "count": dim, "runtime_module": "cst_runtime.project_ops"}
    except Exception as exc:
        return error_response("define_parameters_failed", str(exc), project_path=normalized_project, runtime_module="cst_runtime.project_ops")
