"""results.py — results 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"export-run-results": {
    "category": "results",
    "risk": "filesystem-write",
    "description": "Export S11, 2D, and farfield results to the exports directory after simulation.",
    "handler": "tool_export_run_results",
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
                    [
                        "farfield (f=10) [1]"
                    ]
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
            }
        },
        "required": [
            "project_path",
            "farfield_names",
            "farfield_plot_mode",
            "farfield_theta_step",
            "farfield_phi_step"
        ]
    },
},

"generate-report": {
    "category": "results",
    "risk": "filesystem-write",
    "description": "Generate a modular HTML report from exported S11, farfield, and audit files. Supports --modules and --split.",
    "handler": "tool_generate_report",
    "json_schema": {
        "type": "object",
        "properties": {
            "data_dir": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001"
                ]
            },
            "output_html": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\report.html"
                ]
            },
            "page_title": {
                "type": "string",
                "examples": [
                    "电磁仿真报告"
                ]
            },
            "modules": {
                "type": "string",
                "examples": [
                    "s11,farfield3d,timeline"
                ]
            },
            "split": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "data_dir",
            "output_html",
            "page_title",
            "modules",
            "split"
        ]
    },
},

"get-1d-result": {
    "category": "results",
    "risk": "filesystem-write",
    "description": "Export a 0D/1D result item to JSON from a project path.",
    "handler": "tool_get_1d_result",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "treepath": {
                "type": "string",
                "examples": [
                    "1D Results\\S-Parameters\\S1,1"
                ]
            },
            "module_type": {
                "type": "string",
                "examples": [
                    "3d"
                ]
            },
            "run_id": {
                "type": "integer",
                "examples": [
                    1
                ]
            },
            "load_impedances": {
                "type": "boolean",
                "examples": [
                    True
                ]
            },
            "export_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run1.json"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "treepath",
            "module_type",
            "run_id",
            "load_impedances",
            "export_path",
            "allow_interactive"
        ]
    },
},

"get-2d-result": {
    "category": "results",
    "risk": "filesystem-write",
    "description": "Export a 2D result item to JSON from a project path.",
    "handler": "tool_get_2d_result",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "treepath": {
                "type": "string",
                "examples": [
                    "2D/3D Results\\example"
                ]
            },
            "module_type": {
                "type": "string",
                "examples": [
                    "3d"
                ]
            },
            "export_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\result_2d.json"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            },
            "subproject_treepath": {
                "type": "string",
                "examples": [
                    ""
                ]
            },
            "include_data": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "treepath",
            "module_type",
            "export_path",
            "allow_interactive",
            "subproject_treepath",
            "include_data"
        ]
    },
},

"get-parameter-combination": {
    "category": "results",
    "risk": "read",
    "description": "Read the parameter combination for a result run ID.",
    "handler": "tool_get_parameter_combination",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "run_id": {
                "type": "integer",
                "examples": [
                    1
                ]
            },
            "module_type": {
                "type": "string",
                "examples": [
                    "3d"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "run_id",
            "module_type",
            "allow_interactive"
        ]
    },
},

"get-version-info": {
    "category": "results",
    "risk": "read",
    "description": "Read cst.results version information.",
    "handler": "tool_get_version_info",
    "json_schema": {
        "type": "object",
        "properties": {},
        "required": []
    },
},

"list-result-items": {
    "category": "results",
    "risk": "read",
    "description": "List result tree items from a project path.",
    "handler": "tool_list_result_items",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "module_type": {
                "type": "string",
                "examples": [
                    "3d"
                ]
            },
            "filter_type": {
                "type": "string",
                "examples": [
                    "0D/1D"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            },
            "subproject_treepath": {
                "type": "string",
                "examples": [
                    ""
                ]
            }
        },
        "required": [
            "project_path",
            "module_type",
            "filter_type",
            "allow_interactive",
            "subproject_treepath"
        ]
    },
},

"list-run-ids": {
    "category": "results",
    "risk": "read",
    "description": "List CST result run IDs from a project path.",
    "handler": "tool_list_run_ids",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "treepath": {
                "type": "string",
                "examples": [
                    "1D Results\\S-Parameters\\S1,1"
                ]
            },
            "module_type": {
                "type": "string",
                "examples": [
                    "3d"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            },
            "skip_nonparametric": {
                "type": "boolean",
                "examples": [
                    False
                ]
            },
            "max_mesh_passes_only": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "treepath",
            "module_type",
            "allow_interactive",
            "skip_nonparametric",
            "max_mesh_passes_only"
        ]
    },
},

"list-subprojects": {
    "category": "results",
    "risk": "read",
    "description": "List subprojects from a CST results project by explicit project_path.",
    "handler": "tool_list_subprojects",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "project_path",
            "allow_interactive"
        ]
    },
},

"open-results-project": {
    "category": "results",
    "risk": "read",
    "description": "Validate that cst.results can open a project path.",
    "handler": "tool_open_results_project",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "allow_interactive": {
                "type": "boolean",
                "examples": [
                    False
                ]
            },
            "subproject_treepath": {
                "type": "string",
                "examples": [
                    ""
                ]
            }
        },
        "required": [
            "project_path",
            "allow_interactive",
            "subproject_treepath"
        ]
    },
},

"plot-exported-file": {
    "category": "results",
    "risk": "filesystem-write",
    "description": "Render an exported JSON result or CST farfield ASCII/TXT file to an HTML preview.",
    "handler": "tool_plot_exported_file",
    "json_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\s11_run1.json"
                ]
            },
            "output_html": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\exports\\result_preview.html"
                ]
            },
            "page_title": {
                "type": "string",
                "examples": [
                    "CST Result Preview"
                ]
            }
        },
        "required": [
            "file_path",
            "output_html",
            "page_title"
        ]
    },
},
}


# --- Handlers ---

from ..core import results as _res
from ..core.utils import project_path_from_args, run_id_from_args


def tool_open_results_project(args: dict) -> dict:
    return _res.open_project(
        project_path=project_path_from_args(args),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_list_subprojects(args: dict) -> dict:
    return _res.list_subprojects(
        project_path=project_path_from_args(args),
        allow_interactive=bool(args.get("allow_interactive", False)),
    )


def tool_get_version_info(args: dict) -> dict:
    return _res.get_version_info()


def tool_list_result_items(args: dict) -> dict:
    return _res.list_result_items(
        project_path=project_path_from_args(args),
        module_type=str(args.get("module_type", "3d")),
        filter_type=str(args.get("filter_type", "0D/1D")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_list_run_ids(args: dict) -> dict:
    return _res.list_run_ids(
        project_path=project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
        skip_nonparametric=bool(args.get("skip_nonparametric", False)),
        max_mesh_passes_only=bool(args.get("max_mesh_passes_only", True)),
    )


def tool_get_parameter_combination(args: dict) -> dict:
    return _res.get_parameter_combination(
        project_path=project_path_from_args(args),
        run_id=run_id_from_args(args),
        module_type=str(args.get("module_type", "3d")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_get_1d_result(args: dict) -> dict:
    return _res.get_1d_result(
        project_path=project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        run_id=run_id_from_args(args),
        load_impedances=bool(args.get("load_impedances", True)),
        export_path=str(args.get("export_path", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
    )


def tool_get_2d_result(args: dict) -> dict:
    return _res.get_2d_result(
        project_path=project_path_from_args(args),
        treepath=str(args.get("treepath", "")),
        module_type=str(args.get("module_type", "3d")),
        export_path=str(args.get("export_path", "")),
        allow_interactive=bool(args.get("allow_interactive", False)),
        subproject_treepath=str(args.get("subproject_treepath", "")),
        include_data=bool(args.get("include_data", False)),
    )


def tool_export_run_results(args: dict) -> dict:
    return _res.export_run_results(
        project_path=project_path_from_args(args),
        farfield_names=args.get("farfield_names"),
        farfield_plot_mode=str(args.get("farfield_plot_mode", "Realized Gain")),
        farfield_theta_step=float(args.get("farfield_theta_step", 2.0)),
        farfield_phi_step=float(args.get("farfield_phi_step", 2.0)),
        run_id=args.get("run_id"),
    )


def tool_generate_report(args: dict) -> dict:
    return _res.generate_report(
        data_dir=str(args.get("data_dir", "")),
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
        modules=str(args.get("modules", "")),
        split=bool(args.get("split", False)),
    )


def tool_plot_exported_file(args: dict) -> dict:
    file_path = args.get("file_path") or args.get("export_path") or args.get("output_file")
    return _res.plot_exported_file(
        file_path=str(file_path or ""),
        output_html=str(args.get("output_html", "")),
        page_title=str(args.get("page_title", "")),
    )


_register_tool_defs(TOOL_DEFS)
