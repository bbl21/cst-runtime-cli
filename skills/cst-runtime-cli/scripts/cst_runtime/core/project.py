from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import error_response
from . import gateway
from .identity import attach_expected_project
from .utils import abs_project_path as _abs_project_path


def _connect_new_design_environment():
    import cst.interface
    return cst.interface.DesignEnvironment()


def save_project(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        fp = Path(normalized_project)
        mtime_before = fp.stat().st_mtime if fp.exists() else 0
        project.save()
        import time
        for _ in range(10):
            time.sleep(0.1)
            if fp.exists() and fp.stat().st_mtime > mtime_before:
                break
        return {
            "status": "success",
            "project_path": normalized_project,
            "file_mtime_verified": fp.exists() and fp.stat().st_mtime > mtime_before,
            "runtime_module": "cst_runtime.modeler",
        }
    except Exception as exc:
        return error_response(
            "save_project_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.modeler",
        )


_PARAM_CATEGORY_RULES = [
    ("mesh", ["mesh", "step", "cell", "refinement", "accuracy"]),
    ("solver", ["solver", "tolerance", "maxpasses", "maxiter", "minfrequency", "maxfrequency"]),
    ("material", ["material", "epsilon", "mue", "conductivity", "dielectric", "substrate", "permittivity", "permeability", "loss", "tangent"]),
    ("frequency", ["frequency", "freq", "bandwidth", "centerfreq"]),
    ("geometry", ["length", "width", "height", "radius", "thickness", "spacing", "gap", "offset", "depth",
                   "angle", "rotation", "scale", "position", "x", "y", "z", "r", "l", "w", "h", "d", "g",
                   "diameter", "inner", "outer", "pitch", "taper", "flare", "ridge"]),
]


def _infer_category(name: str) -> str:
    nl = name.lower()
    for cat, keywords in _PARAM_CATEGORY_RULES:
        if any(kw in nl for kw in keywords):
            return cat
    return "geometry"


def list_parameters(project_path: str) -> dict[str, Any]:
    normalized_project = _abs_project_path(project_path)
    project, status = attach_expected_project(normalized_project)
    if project is None:
        return status
    try:
        m3d = project.model3d
        params: dict[str, Any] = {}
        # Try to load descriptions from Model/Parameters.json
        desc_map: dict[str, str] = {}
        pdir = Path(normalized_project).with_suffix("")
        params_json = pdir / "Model" / "Parameters.json"
        if params_json.is_file():
            try:
                pdata = json.loads(params_json.read_text(encoding="utf-8"))
                for entry in pdata.get("parameters", []):
                    name = entry.get("name", "")
                    descr = entry.get("descr", "")
                    if name and descr:
                        desc_map[name] = descr
            except Exception:
                pass
        for index in range(int(m3d.GetNumberOfParameters())):
            name = m3d.GetParameterName(index)
            try:
                value = m3d.RestoreDoubleParameter(name)
            except Exception:
                value = None
            desc = desc_map.get(name, "")
            params[name] = {
                "value": round(value, 6) if isinstance(value, float) else value,
                "description": desc,
                "category": _infer_category(name),
            }
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
        gateway.mark_params_dirty(normalized_project)
        result = {
            "status": "success",
            "project_path": normalized_project,
            "changed": {str(parameter_name): parameter_value},
            "runtime_module": "cst_runtime.modeler",
        }
        return gateway.annotate_change_param_result(result)
    except Exception as exc:
        return error_response(
            "change_parameter_failed",
            str(exc),
            project_path=normalized_project,
            parameter=str(parameter_name),
            runtime_module="cst_runtime.modeler",
        )


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
        return {"status": "success", "project_path": normalized_project, "count": dim, "runtime_module": "cst_runtime.core.project"}
    except Exception as exc:
        return error_response("define_parameters_failed", str(exc), project_path=normalized_project, runtime_module="cst_runtime.core.project")
