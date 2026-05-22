from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def error_response(error_type: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "error", "error_type": error_type, "message": message, **extra}


def _try_import_optuna():
    try:
        import optuna
        return optuna, None
    except ImportError:
        return None, error_response(
            "optuna_not_installed",
            "optuna is required for optimization. Install with: pip install optuna",
            runtime_module="cst_runtime.core.optimizer",
        )


_parse_json = lambda v, d=None: json.loads(v) if isinstance(v, str) and v.strip() else (v or d)


def _make_constraints_func(constraint_defs: list[dict]) -> Any:
    """Return a constraints_func for create_study that reads from trial.user_attrs."""
    import optuna
    def constraints_func(trial: "optuna.trial.Trial") -> list[float]:
        vals = trial.user_attrs.get("constraints", [])
        if not vals:
            return [0.0] * len(constraint_defs)
        return vals
    return constraints_func


def create_study(
    storage_path: str,
    study_name: str,
    parameters: str | dict,
    direction: str = "minimize",
    directions: list[str] | None = None,
    value_names: list[str] | None = None,
    constraints: list[dict] | None = None,
    sampler: str = "tpe",
    n_startup_trials: int = 10,
) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    sp.parent.mkdir(parents=True, exist_ok=True)
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        params_dict = _parse_json(parameters, {})
    except (json.JSONDecodeError, TypeError) as e:
        return error_response("invalid_parameters", str(e))
    try:
        resolved_directions = directions or [direction]
        is_multi = len(resolved_directions) > 1
        cfunc = _make_constraints_func(constraints) if constraints else None
        kwargs: dict[str, Any] = dict(storage=storage, study_name=study_name, load_if_exists=True)
        if is_multi:
            dir_map = {"minimize": optuna.study.StudyDirection.MINIMIZE, "maximize": optuna.study.StudyDirection.MAXIMIZE}
            kwargs["directions"] = [dir_map[d] for d in resolved_directions]
        else:
            kwargs["direction"] = resolved_directions[0]
        if cfunc:
            kwargs["constraints_func"] = cfunc
        study = optuna.create_study(**kwargs)
        study.set_user_attr("parameters", json.dumps(params_dict, ensure_ascii=False))
        if value_names:
            study.set_user_attr("value_names", json.dumps(value_names, ensure_ascii=False))
        if is_multi:
            study.set_user_attr("multi_objective", "true")
        if constraints:
            study.set_user_attr("constraint_defs", json.dumps(constraints, ensure_ascii=False))
        return {
            "status": "success", "study_name": study_name, "storage": str(sp),
            "directions": resolved_directions, "sampler": sampler,
            "parameters": params_dict, "number_of_trials": len(study.trials),
            "multi_objective": is_multi, "constrained": bool(constraints),
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("create_study_failed", str(exc), study_name=study_name)


def ask_study(storage_path: str, study_name: str) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        param_raw = study.user_attrs.get("parameters", "{}")
        params_def = _parse_json(param_raw, {})
        trial = study.ask()
        params: dict[str, Any] = {}
        for pname, pdef in params_def.items():
            ptype = pdef.get("type", "float")
            low = pdef.get("min", pdef.get("low", 0))
            high = pdef.get("max", pdef.get("high", 1))
            if ptype == "int":
                params[pname] = trial.suggest_int(pname, int(low), int(high))
            elif ptype == "categorical":
                params[pname] = trial.suggest_categorical(pname, pdef.get("choices", []))
            else:
                params[pname] = trial.suggest_float(pname, float(low), float(high), log=pdef.get("log", False))
        return {
            "status": "success", "study_name": study_name,
            "trial_number": trial.number, "params": params,
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("ask_study_failed", str(exc), study_name=study_name)


def _trial_set_constraints(study, trial_number: int, constraints: list[float]) -> None:
    """Set constraint values on a trial using its internal trial_id."""
    for t in study.trials:
        if t.number == trial_number:
            trial_id = t._trial_id
            break
    else:
        raise ValueError(f"trial {trial_number} not found")
    import optuna.trial as tmod
    trial_obj = tmod.Trial(study, trial_id)
    trial_obj.set_user_attr("constraints", constraints)


def tell_study(
    storage_path: str, study_name: str, trial_number: int,
    value: float | None = None, values: list[float] | None = None,
    constraints: list[float] | None = None,
    state: str = "complete",
) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        state_obj = optuna.trial.TrialState.COMPLETE if state == "complete" else optuna.trial.TrialState.PRUNED
        resolved_values = values if values is not None else ([value] if value is not None else None)
        if resolved_values is None:
            return error_response("tell_no_value", "provide value or values")
        if constraints is not None:
            _trial_set_constraints(study, trial_number, [float(c) for c in constraints])
        study.tell(trial_number, resolved_values, state=state_obj)
        trials = study.trials
        completed = [t for t in trials if t.state == optuna.trial.TrialState.COMPLETE]
        result: dict[str, Any] = {
            "status": "success", "study_name": study_name,
            "trial_number": trial_number, "values": resolved_values, "state": state,
            "total_trials": len(trials),
            "runtime_module": "cst_runtime.core.optimizer",
        }
        if completed:
            try:
                best = study.best_trial
                result["best_value"] = best.values[0] if len(best.values) == 1 else best.values
                result["best_params"] = best.params
                result["best_trial_number"] = best.number
            except Exception:
                best_trials = study.best_trials[:10]
                result["best_values"] = [t.values for t in best_trials]
                result["best_params_list"] = [t.params for t in best_trials]
        return result
    except Exception as exc:
        return error_response("tell_study_failed", str(exc), study_name=study_name, trial_number=trial_number)


def best_study(storage_path: str, study_name: str) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        trials = study.trials
        completed = [t for t in trials if t.state == optuna.trial.TrialState.COMPLETE]
        result: dict[str, Any] = {
            "status": "success", "study_name": study_name,
            "total_trials": len(trials), "completed_trials": len(completed),
            "runtime_module": "cst_runtime.core.optimizer",
        }
        is_mo = study.user_attrs.get("multi_objective") == "true"
        if completed:
            if is_mo:
                result["best_values"] = [t.values for t in completed[:10]]
                result["n_objectives"] = len(completed[0].values)
            else:
                try:
                    best = study.best_trial
                    result["best_value"] = best.value
                    result["best_params"] = best.params
                    result["best_trial_number"] = best.number
                except Exception:
                    pass
        return result
    except Exception as exc:
        return error_response("best_study_failed", str(exc), study_name=study_name)


def param_importances(storage_path: str, study_name: str) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        try:
            from optuna.importance import get_param_importances
            importances = get_param_importances(study)
        except ImportError:
            return error_response("sklearn_missing", "scikit-learn is required for parameter importance. Install with: pip install scikit-learn", study_name=study_name)
        sorted_params = sorted(importances.items(), key=lambda x: -x[1])
        return {
            "status": "success", "study_name": study_name,
            "importances": {name: round(val, 4) for name, val in sorted_params},
            "top_param": sorted_params[0][0] if sorted_params else None,
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("param_importances_failed", str(exc), study_name=study_name)


def add_trials(
    storage_path: str, study_name: str,
    trials: list[dict],
) -> dict[str, Any]:
    """Inject pre-computed trials into a study (e.g. from manual grid scan).

    Each trial dict: {"params": {"R": 0.1}, "values": [-28.7], "constraints": [0.0]}
    """
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        param_raw = study.user_attrs.get("parameters", "{}")
        params_def = _parse_json(param_raw, {})
        distributions: dict[str, Any] = {}
        for pname, pdef in params_def.items():
            ptype = pdef.get("type", "float")
            low = pdef.get("min", pdef.get("low", 0))
            high = pdef.get("max", pdef.get("high", 1))
            if ptype == "int":
                distributions[pname] = optuna.distributions.IntDistribution(int(low), int(high))
            else:
                log = pdef.get("log", False)
                distributions[pname] = optuna.distributions.FloatDistribution(float(low), float(high), log=log)
        added = 0
        for td in trials:
            params = td.get("params", {})
            values = td.get("values", [td.get("value", 0)])
            constraints = td.get("constraints")
            trial = optuna.create_trial(
                params=params,
                distributions=distributions,
                values=values,
                state=optuna.trial.TrialState.COMPLETE,
            )
            if constraints is not None:
                trial.system_attrs["constraints"] = constraints
            study.add_trial(trial)
            added += 1
        return {
            "status": "success", "study_name": study_name,
            "trials_added": added, "total_trials": len(study.trials),
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("add_trials_failed", str(exc), study_name=study_name)


def switch_sampler(storage_path: str, study_name: str, new_sampler: str) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        trials = study.trials
        user_attrs = dict(study.user_attrs)
        completed = [t for t in trials if t.state == optuna.trial.TrialState.COMPLETE]
        direction = getattr(study, 'direction', None)
        directions = getattr(study, 'directions', None)
        sampler_map = {
            "tpe": optuna.samplers.TPESampler(seed=42),
            "cma-es": optuna.samplers.CmaEsSampler(seed=42),
            "random": optuna.samplers.RandomSampler(seed=42),
        }
        new_sampler_obj = sampler_map.get(new_sampler)
        if new_sampler_obj is None:
            return error_response("unknown_sampler", f"unknown sampler: {new_sampler}", study_name=study_name)
        optuna.delete_study(study_name=study_name, storage=storage)
        create_kwargs: dict = dict(storage=storage, study_name=study_name, sampler=new_sampler_obj, load_if_exists=False)
        if directions:
            dir_map = {"MINIMIZE": optuna.study.StudyDirection.MINIMIZE, "MAXIMIZE": optuna.study.StudyDirection.MAXIMIZE}
            create_kwargs["directions"] = [dir_map.get(str(d), d) for d in directions]
        elif direction:
            create_kwargs["direction"] = str(direction).lower()
        else:
            create_kwargs["direction"] = "minimize"
        new_study = optuna.create_study(**create_kwargs)
        for k, v in user_attrs.items():
            new_study.set_user_attr(k, v)
        migrated = 0
        for t in trials:
            if t.values is not None and t.state in (optuna.trial.TrialState.COMPLETE, optuna.trial.TrialState.PRUNED):
                try:
                    new_study.add_trial(t)
                    migrated += 1
                except Exception:
                    pass
        return {
            "status": "success", "study_name": study_name,
            "sampler": new_sampler, "total_trials": len(trials),
            "trials_migrated": migrated,
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("switch_sampler_failed", str(exc), study_name=study_name, sampler=new_sampler)


def terminate_check(storage_path: str, study_name: str) -> dict[str, Any]:
    optuna, err = _try_import_optuna()
    if err:
        return err
    sp = Path(storage_path).expanduser().resolve()
    storage = f"sqlite:///{sp.as_posix()}"
    try:
        study = optuna.load_study(storage=storage, study_name=study_name)
        from optuna.terminator import Terminator
        terminator = Terminator()
        should_terminate = terminator.should_terminate(study)
        return {
            "status": "success", "study_name": study_name,
            "should_terminate": should_terminate,
            "total_trials": len(study.trials),
            "runtime_module": "cst_runtime.core.optimizer",
        }
    except Exception as exc:
        return error_response("terminate_check_failed", str(exc), study_name=study_name)
