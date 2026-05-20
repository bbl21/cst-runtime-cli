from __future__ import annotations

from typing import Any

from ..core import optimizer as _opt
from . import _register_tool_defs


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
