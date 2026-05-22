"""farfield.py — farfield 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"calculate-farfield-neighborhood-flatness": {
    "category": "farfield",
    "risk": "filesystem-write",
    "description": "Calculate near-boresight farfield cut flatness from exported cut JSON payloads.",
    "handler": "tool_calculate_farfield_neighborhood_flatness",
    "json_schema": {
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "examples": [
                    [
                        "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_cut_phi0_port1.json",
                        "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_cut_phi90_port1.json"
                    ]
                ]
            },
            "theta_max_deg": {
                "type": "number",
                "examples": [
                    15.0
                ]
            },
            "output_json": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\analysis\\farfield_flatness.json"
                ]
            }
        },
        "required": [
            "file_paths",
            "theta_max_deg",
            "output_json"
        ]
    },
},

"export-farfield-cut": {
    "category": "farfield",
    "risk": "long-running",
    "description": "Export an existing CST Farfield Cut tree item to JSON under {export_dir}/farfield/cuts/.",
    "handler": "tool_export_farfield_cut",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "tree_path": {
                "type": "string",
                "examples": [
                    "Farfields\\Farfield Cuts\\Excitation [1]\\Phi=0\\farfield (f=13)"
                ]
            },
            "export_dir": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports"
                ]
            },
            "fresh_session": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "tree_path",
            "export_dir",
            "fresh_session"
        ]
    },
},

"export-farfield-grid": {
    "category": "farfield",
    "risk": "long-running",
    "description": "Compute a FarfieldCalculator scalar grid and export as JSON under {export_dir}/farfield/. Supports fresh_session reuse.",
    "handler": "tool_export_farfield_grid",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "farfield_name": {
                "type": "string",
                "examples": [
                    "farfield (f=13) [1]"
                ]
            },
            "export_dir": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports"
                ]
            },
            "quantity": {
                "type": "string",
                "examples": [
                    "Realized Gain"
                ]
            },
            "theta_step_deg": {
                "type": "number",
                "examples": [
                    1.0
                ]
            },
            "phi_step_deg": {
                "type": "number",
                "examples": [
                    2.0
                ]
            },
            "theta_min_deg": {
                "type": "number",
                "examples": [
                    0.0
                ]
            },
            "theta_max_deg": {
                "type": "number",
                "examples": [
                    15.0
                ]
            },
            "phi_min_deg": {
                "type": "number",
                "examples": [
                    0.0
                ]
            },
            "phi_max_deg": {
                "type": "number",
                "examples": [
                    360.0
                ]
            },
            "run_id": {
                "type": "string",
                "examples": [
                    ""
                ]
            },
            "fresh_session": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "farfield_name",
            "export_dir",
            "quantity",
            "theta_step_deg",
            "phi_step_deg",
            "theta_min_deg",
            "theta_max_deg",
            "phi_min_deg",
            "phi_max_deg",
            "run_id",
            "fresh_session"
        ]
    },
},

"inspect-farfield-monitors": {
    "category": "farfield",
    "risk": "read",
    "description": "Discover farfield monitors from a CST project by scanning the result tree.",
    "handler": "tool_inspect_farfield_monitors",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            }
        },
        "required": [
            "project_path"
        ]
    },
},
}


# --- Handlers ---

from ..core import farfield as _ff
from ..core.utils import project_path_from_args


def tool_inspect_farfield_monitors(args: dict) -> dict:
    project_path = args.get("project_path") or args.get("project")
    if not project_path:
        return {
            "status": "error",
            "error_code": "project_path_missing",
            "message": "project_path is required",
            "runtime_module": "cst_runtime._tools.farfield",
        }
    return _ff.discover_farfield_monitors(str(project_path))


def tool_export_farfield_grid(args: dict) -> dict:
    run_id = args.get("run_id")
    return _ff.export_farfield_grid(
        project_path=project_path_from_args(args),
        farfield_name=str(args.get("farfield_name", "")),
        export_dir=str(args.get("export_dir", "")),
        quantity=str(args.get("quantity", "Realized Gain")),
        theta_step_deg=float(args.get("theta_step_deg", 1.0)),
        phi_step_deg=float(args.get("phi_step_deg", 2.0)),
        theta_min_deg=args.get("theta_min_deg"),
        theta_max_deg=args.get("theta_max_deg"),
        phi_min_deg=args.get("phi_min_deg"),
        phi_max_deg=args.get("phi_max_deg"),
        run_id=None if run_id in (None, "") else int(run_id),
        fresh_session=bool(args.get("fresh_session", False)),
        selection_tree_path=str(args.get("selection_tree_path", "1D Results\\S-Parameters")),
    )


def tool_export_farfield_cut(args: dict) -> dict:
    return _ff.export_farfield_cut(
        project_path=project_path_from_args(args),
        tree_path=str(args.get("tree_path", "")),
        export_dir=str(args.get("export_dir", "")),
        fresh_session=bool(args.get("fresh_session", False)),
    )


def tool_calculate_farfield_neighborhood_flatness(args: dict) -> dict:
    file_paths = args.get("file_paths") or []
    if isinstance(file_paths, str):
        import json as _json
        file_paths = _json.loads(file_paths)
    if not file_paths and args.get("file_path"):
        file_paths = [str(args["file_path"])]
    return _ff.calculate_farfield_neighborhood_flatness(
        file_paths=[str(path) for path in file_paths],
        theta_max_deg=float(args.get("theta_max_deg", 15.0)),
        output_json=str(args.get("output_json", "")),
    )


_register_tool_defs(TOOL_DEFS)
