from __future__ import annotations

from typing import Any

from ..core import optimizer as _opt
from . import _register_tool_defs


def _lazy_pipeline(name: str):
    import importlib
    mod = importlib.import_module("..cli.pipelines.impl", __package__)
    return getattr(mod, name)


_register_tool_defs({
    "create-study": {
        "category": "optimization",
        "risk": "filesystem-write",
        "description": "Create or load an Optuna optimization study. Supports single-objective, multi-objective (directions), and constraint-enabled studies.",
        "handler": "tool_create_study",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
            "parameters": '{"R": {"type": "float", "min": 0.1, "max": 0.5}}',
            "direction": "minimize",
            "directions": ["minimize", "maximize"],
            "value_names": ["S11_dB", "Gain_dBi"],
            "constraints": [{"name": "VSWR", "operator": "<=", "threshold": 2.0}],
            "sampler": "tpe",
            "n_startup_trials": 10,
        },
    },
    "ask-study": {
        "category": "optimization",
        "risk": "read",
        "description": "Ask the study for the next trial parameter suggestion.",
        "handler": "tool_ask_study",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
        },
    },
    "tell-study": {
        "category": "optimization",
        "risk": "filesystem-write",
        "description": "Report trial result. Supports single value, multi-objective values array, and optional constraints.",
        "handler": "tool_tell_study",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
            "trial_number": 3,
            "value": -35.5,
            "values": [-35.5, 12.3],
            "constraints": [-1.0, 0.5],
            "state": "complete",
        },
    },
    "best-study": {
        "category": "optimization",
        "risk": "read",
        "description": "Get current best result. For multi-objective returns Pareto front samples.",
        "handler": "tool_best_study",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
        },
    },
    "study-add-trials": {
        "category": "optimization",
        "risk": "filesystem-write",
        "description": "Inject pre-computed trials (e.g. from manual grid scan) into a study. Each trial: {params, values, constraints?}.",
        "handler": "tool_add_trials",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
            "trials": [{"params": {"R": 0.1}, "values": [-28.7]}, {"params": {"R": 0.2}, "values": [-39.9]}],
        },
    },
    "study-param-importances": {
        "category": "optimization",
        "risk": "read",
        "description": "Analyze which parameters most affect the objective. Requires at least 5 completed trials.",
        "handler": "tool_param_importances",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
        },
    },
    "study-terminate-check": {
        "category": "optimization",
        "risk": "read",
        "description": "Check if optimization has converged using Optuna's regret-bound evaluator. Returns should_terminate.",
        "handler": "tool_terminate_check",
        "direct_flags": True,
        "args_template": {
            "storage_path": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db",
            "study_name": "horn_matching",
        },
    },
    "run-probe-phase": {
        "category": "optimization",
        "risk": "long-running",
        "description": "Run the complete probe phase: design Plackett-Burman probes, simulate each, analyze main effects and interactions, then inject results into an Optuna study. The working.cst is copied to working_probe.cst for isolation; exports go to exports/probe/. Returns top_params, edge_hit, and suggested_algorithm. Supports objective parameter to customize the objective function (default: s11_min_db).",
        "handler": "tool_run_probe_phase",
        "direct_flags": True,
        "json_schema": {
            "$schema": "https://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["project_path", "parameters", "study_storage", "study_name"],
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to working.cst",
                    "default": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                },
                "parameters": {
                    "type": "object",
                    "description": "Parameter ranges for DOE screening, keyed by parameter name. Each value: {min, max, type?}",
                    "default": {"R": {"min": 0.1, "max": 0.5}, "g": {"min": 20, "max": 30}},
                    "additionalProperties": {
                        "type": "object",
                        "required": ["min", "max"],
                        "properties": {
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                            "type": {"type": "string", "enum": ["float", "int"]}
                        }
                    }
                },
                "study_storage": {
                    "type": "string",
                    "description": "Path to Optuna SQLite storage file",
                    "default": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db"
                },
                "study_name": {
                    "type": "string",
                    "description": "Name for the Optuna study",
                    "default": "horn_matching"
                },
                "max_probes": {
                    "type": "integer",
                    "default": 12,
                    "description": "Maximum number of probe points"
                },
                "include_center": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include center point in probe design"
                },
                "objective": {
                    "type": "object",
                    "default": {"type": "s11_min_db"},
                    "description": "Objective function spec. Default: {\"type\": \"s11_min_db\"}. Supports: s11_min_db, s11_at_freq, gain_max, bandwidth, expression"
                }
            }
        }
    },
    "run-optimization-step": {
        "category": "optimization",
        "risk": "long-running",
        "description": "Run one optimization iteration: ask Optuna for next parameters, apply them, simulate, read S11 objective, and report back. Agent inspects the s11_metric output to decide whether to stop or continue the loop.",
        "handler": "tool_run_optimization_step",
        "direct_flags": True,
        "json_schema": {
            "$schema": "https://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["project_path", "study_storage", "study_name"],
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to working.cst",
                    "default": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                },
                "study_storage": {
                    "type": "string",
                    "description": "Path to Optuna SQLite storage file",
                    "default": "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\studies\\optimization.db"
                },
                "study_name": {
                    "type": "string",
                    "description": "Name of the Optuna study",
                    "default": "horn_matching"
                }
            }
        }
    },
})


def tool_create_study(args: dict) -> dict:
    return _opt.create_study(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
        parameters=args.get("parameters", "{}"),
        direction=str(args.get("direction", "minimize")),
        directions=args.get("directions"),
        value_names=args.get("value_names"),
        constraints=args.get("constraints"),
        sampler=str(args.get("sampler", "tpe")),
        n_startup_trials=int(args.get("n_startup_trials", 10)),
    )


def tool_ask_study(args: dict) -> dict:
    return _opt.ask_study(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
    )


def tool_tell_study(args: dict) -> dict:
    return _opt.tell_study(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
        trial_number=int(args.get("trial_number", 0)),
        value=args.get("value"),
        values=args.get("values"),
        constraints=args.get("constraints"),
        state=str(args.get("state", "complete")),
    )


def tool_best_study(args: dict) -> dict:
    return _opt.best_study(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
    )


def tool_add_trials(args: dict) -> dict:
    return _opt.add_trials(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
        trials=args.get("trials", []),
    )


def tool_param_importances(args: dict) -> dict:
    return _opt.param_importances(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
    )


def tool_terminate_check(args: dict) -> dict:
    return _opt.terminate_check(
        storage_path=str(args.get("storage_path", "")),
        study_name=str(args.get("study_name", "")),
    )


def tool_run_probe_phase(args: dict) -> dict:
    _run = _lazy_pipeline("pipeline_run_probe_phase")
    return _run(
        project_path=str(args["project_path"]),
        parameters=args.get("parameters", {}),
        study_storage=str(args["study_storage"]),
        study_name=str(args["study_name"]),
        max_probes=int(args.get("max_probes", 12)),
        include_center=bool(args.get("include_center", True)),
        objective=args.get("objective"),
    )


def tool_run_optimization_step(args: dict) -> dict:
    _run = _lazy_pipeline("pipeline_run_optimization_step")
    return _run(
        project_path=str(args["project_path"]),
        study_storage=str(args["study_storage"]),
        study_name=str(args["study_name"]),
    )
