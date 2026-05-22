"""project_ops.py — project_ops + project_identity 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"change-parameter": {
    "category": "project_ops",
    "risk": "write",
    "description": "Change one CST parameter in the verified working project.",
    "handler": "tool_change_parameter",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "name": "R", "value": 0.102},
},

"change-solver-type": {
    "category": "project_ops",
    "risk": "write",
    "description": "Change the CST solver type.",
    "handler": "tool_change_solver_type",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "solver_type": "HF Time Domain"},
},

"define-background": {
    "category": "project_ops",
    "risk": "write",
    "description": "Set the background type to Normal.",
    "handler": "tool_define_background",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"define-boundary": {
    "category": "project_ops",
    "risk": "write",
    "description": "Set expanded open boundary conditions.",
    "handler": "tool_define_boundary",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"define-frequency-range": {
    "category": "project_ops",
    "risk": "write",
    "description": "Set the simulation frequency range.",
    "handler": "tool_define_frequency_range",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "start_freq": 2.0, "end_freq": 18.0},
},

"define-mesh": {
    "category": "project_ops",
    "risk": "write",
    "description": "Configure the hexahedral mesh parameters.",
    "handler": "tool_define_mesh",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "steps_per_wave_near": 5, "steps_per_wave_far": 5, "steps_per_box_near": 5, "steps_per_box_far": 1},
},

"define-monitor": {
    "category": "project_ops",
    "risk": "write",
    "description": "Define a farfield monitor over a frequency range.",
    "handler": "tool_define_monitor",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "start_freq": 2.0, "end_freq": 18.0, "step": 1},
},

"define-parameters": {
    "category": "project_ops",
    "risk": "write",
    "description": "Batch-define multiple CST parameters using StoreParameters.",
    "handler": "tool_define_parameters",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "names": ["a", "b", "h"], "values": ["10", "5*b", "2"]},
},

"define-port": {
    "category": "project_ops",
    "risk": "write",
    "description": "Define a waveguide port.",
    "handler": "tool_define_port",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "port_number": "1", "x_min": -10, "x_max": 10, "y_min": -10, "y_max": 10, "z_min": 0, "z_max": 5, "orientation": "zmin"},
},

"define-solver": {
    "category": "project_ops",
    "risk": "write",
    "description": "Configure the time-domain solver settings.",
    "handler": "tool_define_solver",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "stimulation_port": "All", "steady_state_limit": -40, "norming_impedance": 50},
},

"infer-run-dir": {
    "category": "project_identity",
    "risk": "read",
    "description": "Infer run_dir from a projects/working.cst project path.",
    "handler": "tool_infer_run_dir",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"inspect-project": {
    "category": "project_ops",
    "risk": "read",
    "description": "Open a CST project, list all parameters and entities, then close. Returns parameter names/values and entity names.",
    "handler": "tool_inspect_project",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"is-simulation-running": {
    "category": "project_ops",
    "risk": "read",
    "description": "Check whether the CST solver is currently running for the verified working project.",
    "handler": "tool_is_simulation_running",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"list-open-projects": {
    "category": "project_identity",
    "risk": "read",
    "description": "List CST projects visible through DesignEnvironment.connect_to_any().",
    "handler": "tool_list_open_projects",
    "direct_flags": False,
    "args_template": {},
},

"list-parameters": {
    "category": "project_ops",
    "risk": "read",
    "description": "List parameters from the verified CST working project.",
    "handler": "tool_list_parameters",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"pause-simulation": {
    "category": "project_ops",
    "risk": "session",
    "description": "Pause the currently running CST solver.",
    "handler": "tool_pause_simulation",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"prepare-experiment": {
    "category": "project_ops",
    "risk": "write",
    "description": "Open a CST project, change one or more parameters, confirm, then save and close. Supports batch via names+values arrays. Use before run-experiment.",
    "handler": "tool_prepare_experiment",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "param_name": "g", "param_value": 23.5, "names": ["R", "g"], "values": [0.16, 23.0]},
},

"resume-simulation": {
    "category": "project_ops",
    "risk": "write",
    "description": "Resume a paused CST solver.",
    "handler": "tool_resume_simulation",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"set-fdsolver-extrude-open-bc": {
    "category": "project_ops",
    "risk": "write",
    "description": "Enable or disable FD solver extruded open boundary.",
    "handler": "tool_set_fdsolver_extrude_open_bc",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"set-mesh-fpbavoid-nonreg-unite": {
    "category": "project_ops",
    "risk": "write",
    "description": "Enable or disable mesh FPBA non-regular unite avoidance.",
    "handler": "tool_set_mesh_fpbavoid_nonreg_unite",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"set-mesh-minimum-step-number": {
    "category": "project_ops",
    "risk": "write",
    "description": "Set the minimum mesh step number.",
    "handler": "tool_set_mesh_minimum_step_number",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "num_steps": 5},
},

"set-solver-acceleration": {
    "category": "project_ops",
    "risk": "write",
    "description": "Configure solver parallelization and hardware acceleration.",
    "handler": "tool_set_solver_acceleration",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "use_parallelization": True, "max_threads": 1024},
},

"start-simulation-async": {
    "category": "project_ops",
    "risk": "long-running",
    "description": "Start the CST solver asynchronously for the verified working project.",
    "handler": "tool_start_simulation_async",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"stop-simulation": {
    "category": "project_ops",
    "risk": "session",
    "description": "Stop the currently running CST solver.",
    "handler": "tool_stop_simulation",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"verify-project-identity": {
    "category": "project_identity",
    "risk": "read",
    "description": "Verify the expected project is the sole open CST project before writes.",
    "handler": "tool_verify_project_identity",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"},
},

"wait-project-unlocked": {
    "category": "project_identity",
    "risk": "read",
    "description": "Wait for a project companion directory to have no .lok files.",
    "handler": "tool_wait_project_unlocked",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "timeout_seconds": 30, "poll_interval_seconds": 0.5},
},

"wait-simulation": {
    "category": "project_ops",
    "risk": "long-running",
    "description": "Poll is-simulation-running until the solver finishes or timeout expires.",
    "handler": "tool_wait_simulation",
    "direct_flags": True,
    "args_template": {"project_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst", "timeout_seconds": 3600, "poll_interval_seconds": 10},
},
}


# --- Handlers ---

from ..core import project as _po
from ..core import simulation as _sim
from ..core import modeling as _md
from ..core import identity as _pi
from ..core.utils import project_path_from_args
from pathlib import Path
import time


def _lazy_pipeline(name: str):
    """Lazy-import a pipeline function to break circular dependency."""
    import importlib
    mod = importlib.import_module("..cli.pipelines.impl", __package__)
    return getattr(mod, name)


def tool_inspect_project(args: dict) -> dict:
    _inspect = _lazy_pipeline("pipeline_inspect_project")
    return _inspect(
        project_path=str(args.get("project_path", "")),
    )


def tool_prepare_experiment(args: dict) -> dict:
    _prepare = _lazy_pipeline("pipeline_prepare_experiment")
    names = args.get("names") or args.get("param_names")
    values = args.get("values") or args.get("param_values")
    if isinstance(names, list) and isinstance(values, list):
        return _prepare(project_path=str(args.get("project_path", "")), names=names, values=values)
    return _prepare(
        project_path=str(args.get("project_path", "")),
        param_name=str(args.get("param_name", "")),
        param_value=float(args.get("param_value", 0)),
    )


def tool_list_materials(args: dict) -> dict:
    materials_path = Path(__file__).resolve().parents[3] / "references" / "materials_name_list.txt"
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


def tool_list_parameters(args: dict) -> dict:
    return _po.list_parameters(project_path_from_args(args))


def tool_list_entities(args: dict) -> dict:
    return _po.list_entities(
        project_path=project_path_from_args(args),
        component=str(args.get("component", "")),
    )


def tool_change_parameter(args: dict) -> dict:
    project_path = project_path_from_args(args)
    tool_args = {key: value for key, value in args.items() if key not in {"project_path", "fullpath", "working_project"}}
    return _po.change_parameter(project_path=project_path, **tool_args)


def tool_define_parameters(args: dict) -> dict:
    return _po.define_parameters(
        project_path=project_path_from_args(args),
        names=args.get("names", []),
        values=args.get("values", []),
    )


def tool_start_simulation(args: dict) -> dict:
    return _sim.start_simulation(project_path_from_args(args))


def tool_start_simulation_async(args: dict) -> dict:
    return _sim.start_simulation_async(project_path_from_args(args))


def tool_is_simulation_running(args: dict) -> dict:
    return _sim.is_simulation_running(project_path_from_args(args))


def tool_wait_simulation(args: dict) -> dict:
    project_path = project_path_from_args(args)
    timeout_seconds = float(args.get("timeout_seconds", 3600.0))
    poll_interval_seconds = float(args.get("poll_interval_seconds", 10.0))
    started = time.monotonic()
    polls = 0
    last_result = None
    while True:
        polls += 1
        last_result = _sim.is_simulation_running(project_path)
        if last_result.get("status") == "error":
            return {**last_result, "polls": polls, "waited_seconds": round(time.monotonic() - started, 3)}
        if not bool(last_result.get("running")):
            return {
                "status": "success",
                "project_path": last_result.get("project_path", project_path),
                "running": False,
                "polls": polls,
                "waited_seconds": round(time.monotonic() - started, 3),
                "runtime_module": "cst_runtime._tools.project_ops",
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
                "runtime_module": "cst_runtime._tools.project_ops",
            }
        time.sleep(poll_interval_seconds)


def tool_stop_simulation(args: dict) -> dict:
    return _sim.stop_simulation(project_path_from_args(args))


def tool_pause_simulation(args: dict) -> dict:
    return _sim.pause_simulation(project_path_from_args(args))


def tool_resume_simulation(args: dict) -> dict:
    return _sim.resume_simulation(project_path_from_args(args))


def tool_set_solver_acceleration(args: dict) -> dict:
    return _sim.set_solver_acceleration(**args)


def tool_set_fdsolver_extrude_open_bc(args: dict) -> dict:
    return _sim.set_fdsolver_extrude_open_bc(**args)


def tool_set_mesh_fpbavoid_nonreg_unite(args: dict) -> dict:
    return _sim.set_mesh_fpbavoid_nonreg_unite(**args)


def tool_set_mesh_minimum_step_number(args: dict) -> dict:
    return _sim.set_mesh_minimum_step_number(**args)


def tool_list_open_projects(args: dict) -> dict:
    return _pi.list_open_projects()


def tool_verify_project_identity(args: dict) -> dict:
    return _pi.verify_project_identity(project_path_from_args(args))


def tool_infer_run_dir(args: dict) -> dict:
    project_path = project_path_from_args(args)
    run_dir = _pi.infer_run_dir_from_project(project_path)
    return {
        "status": "success",
        "project_path": str(project_path),
        "run_dir": run_dir.as_posix() if run_dir else None,
        "runtime_module": "cst_runtime._tools.project_ops",
    }


def tool_wait_project_unlocked(args: dict) -> dict:
    project_path = project_path_from_args(args)
    return _pi.wait_project_unlocked(
        project_path=project_path,
        timeout_seconds=float(args.get("timeout_seconds", 10.0)),
        poll_interval_seconds=float(args.get("poll_interval_seconds", 0.5)),
    )


def tool_define_frequency_range(args: dict) -> dict:
    return _md.define_frequency_range(**args)


def tool_change_solver_type(args: dict) -> dict:
    return _md.change_solver_type(**args)


def tool_define_background(args: dict) -> dict:
    return _md.define_background(**args)


def tool_define_boundary(args: dict) -> dict:
    return _md.define_boundary(**args)


def tool_define_mesh(args: dict) -> dict:
    return _md.define_mesh(**args)


def tool_define_solver(args: dict) -> dict:
    return _md.define_solver(**args)


def tool_define_port(args: dict) -> dict:
    return _md.define_port(**args)


def tool_define_monitor(args: dict) -> dict:
    return _md.define_monitor(**args)


_register_tool_defs(TOOL_DEFS)
