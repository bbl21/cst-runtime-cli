"""simulation.py — simulation 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"run-experiment": {
    "category": "simulation",
    "risk": "long-running",
    "description": "Run a simulation, wait for completion, and export S11 + farfield results. Returns s11_metric with min_db and best_freq.",
    "handler": "tool_run_experiment",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "farfield_names": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "examples": [
                    []
                ]
            },
            "farfield_plot_mode": {
                "type": "string",
                "examples": [
                    "Realized Gain"
                ]
            },
            "farfield_theta_step": {
                "type": "number",
                "examples": [
                    2.0
                ]
            },
            "farfield_phi_step": {
                "type": "number",
                "examples": [
                    2.0
                ]
            },
            "timeout_seconds": {
                "type": "integer",
                "examples": [
                    3600
                ]
            }
        },
        "required": [
            "project_path",
            "farfield_names",
            "farfield_plot_mode",
            "farfield_theta_step",
            "farfield_phi_step",
            "timeout_seconds"
        ]
    },
},
}


# --- Handlers ---

from ..core.utils import project_path_from_args


def tool_run_experiment(args: dict) -> dict:
    from ..cli.pipelines.impl import pipeline_run_experiment as _run
    ff_names = args.get("farfield_names")
    if isinstance(ff_names, str):
        import json as _json
        try:
            ff_names = _json.loads(ff_names)
        except Exception:
            ff_names = None
    return _run(
        project_path=str(args.get("project_path", "")),
        farfield_names=ff_names if isinstance(ff_names, list) else None,
        farfield_plot_mode=str(args.get("farfield_plot_mode", "Realized Gain")),
        farfield_theta_step=float(args.get("farfield_theta_step", 2.0)),
        farfield_phi_step=float(args.get("farfield_phi_step", 2.0)),
        timeout_seconds=int(args.get("timeout_seconds", 3600)),
    )


_register_tool_defs(TOOL_DEFS)
