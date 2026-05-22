"""modeling.py — modeling 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"activate-post-process": {
    "category": "modeling",
    "risk": "write",
    "description": "Activate or deactivate a post-processing operation.",
    "handler": "tool_activate_post_process",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "operation": {
                "type": "string",
                "examples": [
                    "envelop"
                ]
            },
            "enable": {
                "type": "boolean",
                "examples": [
                    True
                ]
            }
        },
        "required": [
            "project_path",
            "operation",
            "enable"
        ]
    },
},

"add-to-history": {
    "category": "modeling",
    "risk": "write",
    "description": "Execute a raw VBA command via add_to_history for operations not covered by other tools.",
    "handler": "tool_add_to_history",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "command": {
                "type": "string",
                "examples": [
                    "Solid.Add \"Component1:solid1\", \"Component1:solid2\""
                ]
            },
            "history_name": {
                "type": "string",
                "examples": [
                    "custom boolean add"
                ]
            }
        },
        "required": [
            "project_path",
            "command",
            "history_name"
        ]
    },
},

"boolean-add": {
    "category": "modeling",
    "risk": "write",
    "description": "Unite two solids (boolean union).",
    "handler": "tool_boolean_add",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape1": {
                "type": "string",
                "examples": [
                    "Component1:part1"
                ]
            },
            "shape2": {
                "type": "string",
                "examples": [
                    "Component1:part2"
                ]
            }
        },
        "required": [
            "project_path",
            "shape1",
            "shape2"
        ]
    },
},

"boolean-insert": {
    "category": "modeling",
    "risk": "write",
    "description": "Insert one solid into another (boolean insert).",
    "handler": "tool_boolean_insert",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape1": {
                "type": "string",
                "examples": [
                    "Component1:outer"
                ]
            },
            "shape2": {
                "type": "string",
                "examples": [
                    "Component1:insert"
                ]
            }
        },
        "required": [
            "project_path",
            "shape1",
            "shape2"
        ]
    },
},

"boolean-intersect": {
    "category": "modeling",
    "risk": "write",
    "description": "Intersect two solids (boolean intersection).",
    "handler": "tool_boolean_intersect",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape1": {
                "type": "string",
                "examples": [
                    "Component1:part1"
                ]
            },
            "shape2": {
                "type": "string",
                "examples": [
                    "Component1:part2"
                ]
            }
        },
        "required": [
            "project_path",
            "shape1",
            "shape2"
        ]
    },
},

"boolean-subtract": {
    "category": "modeling",
    "risk": "write",
    "description": "Subtract one solid from another (boolean difference).",
    "handler": "tool_boolean_subtract",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "target": {
                "type": "string",
                "examples": [
                    "Component1:outer"
                ]
            },
            "tool": {
                "type": "string",
                "examples": [
                    "Component1:inner"
                ]
            }
        },
        "required": [
            "project_path",
            "target",
            "tool"
        ]
    },
},

"change-material": {
    "category": "modeling",
    "risk": "write",
    "description": "Change the material of a geometry entity. Use list-materials to see available names.",
    "handler": "tool_change_material",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape_name": {
                "type": "string",
                "examples": [
                    "Component1:my_brick"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "Copper (pure)"
                ]
            }
        },
        "required": [
            "project_path",
            "shape_name",
            "material"
        ]
    },
},

"create-component": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a new component in the CST project.",
    "handler": "tool_create_component",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "component_name": {
                "type": "string",
                "examples": [
                    "MyComponent"
                ]
            }
        },
        "required": [
            "project_path",
            "component_name"
        ]
    },
},

"create-hollow-sweep": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a hollow loft sweep with outer and inner walls.",
    "handler": "tool_create_hollow_sweep",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "horn"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "HornAntenna"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "x_min1": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "x_max1": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "y_min1": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "y_max1": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "z1": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "x_min2": {
                "type": "integer",
                "examples": [
                    -35
                ]
            },
            "x_max2": {
                "type": "integer",
                "examples": [
                    35
                ]
            },
            "y_min2": {
                "type": "integer",
                "examples": [
                    -35
                ]
            },
            "y_max2": {
                "type": "integer",
                "examples": [
                    35
                ]
            },
            "z2": {
                "type": "integer",
                "examples": [
                    50
                ]
            },
            "wall_thickness": {
                "type": "number",
                "examples": [
                    2.0
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "x_min1",
            "x_max1",
            "y_min1",
            "y_max1",
            "z1",
            "x_min2",
            "x_max2",
            "y_min2",
            "y_max2",
            "z2",
            "wall_thickness"
        ]
    },
},

"create-horn-segment": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a horn segment (outer cone - inner cone).",
    "handler": "tool_create_horn_segment",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "segment_id": {
                "type": "integer",
                "examples": [
                    1
                ]
            },
            "bottom_radius": {
                "type": "integer",
                "examples": [
                    8
                ]
            },
            "top_radius": {
                "type": "integer",
                "examples": [
                    25
                ]
            },
            "z_min": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "z_max": {
                "type": "integer",
                "examples": [
                    30
                ]
            }
        },
        "required": [
            "project_path",
            "segment_id",
            "bottom_radius",
            "top_radius",
            "z_min",
            "z_max"
        ]
    },
},

"create-loft-sweep": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a loft sweep between two 2D profiles in one step.",
    "handler": "tool_create_loft_sweep",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "horn_shell"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "HornAntenna"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "x_min1": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "x_max1": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "y_min1": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "y_max1": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "z1": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "x_min2": {
                "type": "integer",
                "examples": [
                    -35
                ]
            },
            "x_max2": {
                "type": "integer",
                "examples": [
                    35
                ]
            },
            "y_min2": {
                "type": "integer",
                "examples": [
                    -35
                ]
            },
            "y_max2": {
                "type": "integer",
                "examples": [
                    35
                ]
            },
            "z2": {
                "type": "integer",
                "examples": [
                    50
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "x_min1",
            "x_max1",
            "y_min1",
            "y_max1",
            "z1",
            "x_min2",
            "x_max2",
            "y_min2",
            "y_max2",
            "z2"
        ]
    },
},

"create-mesh-group": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a mesh group and add items.",
    "handler": "tool_create_mesh_group",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "group_name": {
                "type": "string",
                "examples": [
                    "fine_mesh"
                ]
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "examples": [
                    [
                        "solid1",
                        "solid2"
                    ]
                ]
            }
        },
        "required": [
            "project_path",
            "group_name",
            "items"
        ]
    },
},

"define-analytical-curve": {
    "category": "modeling",
    "risk": "write",
    "description": "Define an analytical curve using parametric equations.",
    "handler": "tool_define_analytical_curve",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "exp_curve"
                ]
            },
            "curve": {
                "type": "string",
                "examples": [
                    "curve1"
                ]
            },
            "law_x": {
                "type": "string",
                "examples": [
                    "C1*exp(R*t)+C2"
                ]
            },
            "law_y": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "law_z": {
                "type": "string",
                "examples": [
                    "t"
                ]
            },
            "param_start": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "param_end": {
                "type": "string",
                "examples": [
                    "10"
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "curve",
            "law_x",
            "law_y",
            "law_z",
            "param_start",
            "param_end"
        ]
    },
},

"define-brick": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a rectangular brick in the CST project.",
    "handler": "tool_define_brick",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "my_brick"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "x_min": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "x_max": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "y_min": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "y_max": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "z_min": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "z_max": {
                "type": "integer",
                "examples": [
                    20
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "x_min",
            "x_max",
            "y_min",
            "y_max",
            "z_min",
            "z_max"
        ]
    },
},

"define-cone": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a cone in the CST project.",
    "handler": "tool_define_cone",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "my_cone"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "bottom_radius": {
                "type": "integer",
                "examples": [
                    5
                ]
            },
            "top_radius": {
                "type": "integer",
                "examples": [
                    15
                ]
            },
            "axis": {
                "type": "string",
                "examples": [
                    "z"
                ]
            },
            "z_min": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "z_max": {
                "type": "integer",
                "examples": [
                    30
                ]
            },
            "x_center": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "y_center": {
                "type": "integer",
                "examples": [
                    0
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "bottom_radius",
            "top_radius",
            "axis",
            "z_min",
            "z_max",
            "x_center",
            "y_center"
        ]
    },
},

"define-cylinder": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a cylinder in the CST project.",
    "handler": "tool_define_cylinder",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "my_cylinder"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "outer_radius": {
                "type": "integer",
                "examples": [
                    5
                ]
            },
            "inner_radius": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "axis": {
                "type": "string",
                "examples": [
                    "z"
                ]
            },
            "z_min": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "z_max": {
                "type": "integer",
                "examples": [
                    20
                ]
            },
            "x_center": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "y_center": {
                "type": "integer",
                "examples": [
                    0
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "outer_radius",
            "inner_radius",
            "axis",
            "z_min",
            "z_max",
            "x_center",
            "y_center"
        ]
    },
},

"define-extrude-curve": {
    "category": "modeling",
    "risk": "write",
    "description": "Extrude a curve profile into a solid.",
    "handler": "tool_define_extrude_curve",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "extruded_part"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "curve": {
                "type": "string",
                "examples": [
                    "curve1:my_polygon"
                ]
            },
            "thickness": {
                "type": "integer",
                "examples": [
                    5
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "curve",
            "thickness"
        ]
    },
},

"define-loft": {
    "category": "modeling",
    "risk": "write",
    "description": "Execute a loft between pre-picked faces.",
    "handler": "tool_define_loft",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "loft_result"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "material": {
                "type": "string",
                "examples": [
                    "PEC"
                ]
            },
            "tangency": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "minimize_twist": {
                "type": "boolean",
                "examples": [
                    True
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "component",
            "material",
            "tangency",
            "minimize_twist"
        ]
    },
},

"define-material-from-mtd": {
    "category": "modeling",
    "risk": "write",
    "description": "Define a CST material from .mtd file by material name. Material must exist in references/Materials/. Use list-materials to see available names.",
    "handler": "tool_define_material_from_mtd",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "material_name": {
                "type": "string",
                "examples": [
                    "Copper (pure)"
                ]
            }
        },
        "required": [
            "project_path",
            "material_name"
        ]
    },
},

"define-polygon-3d": {
    "category": "modeling",
    "risk": "write",
    "description": "Define a 3D polygon curve from a list of points.",
    "handler": "tool_define_polygon_3d",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "my_polygon"
                ]
            },
            "curve": {
                "type": "string",
                "examples": [
                    "curve1"
                ]
            },
            "points": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "examples": [
                    [
                        [
                            "-10",
                            "0",
                            "0"
                        ],
                        [
                            "10",
                            "0",
                            "0"
                        ],
                        [
                            "10",
                            "0",
                            "10"
                        ],
                        [
                            "-10",
                            "0",
                            "10"
                        ],
                        [
                            "-10",
                            "0",
                            "0"
                        ]
                    ]
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "curve",
            "points"
        ]
    },
},

"define-rectangle": {
    "category": "modeling",
    "risk": "write",
    "description": "Create a 2D rectangle on a curve in the CST project.",
    "handler": "tool_define_rectangle",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "my_rect"
                ]
            },
            "curve": {
                "type": "string",
                "examples": [
                    "curve1"
                ]
            },
            "x_min": {
                "type": "integer",
                "examples": [
                    -10
                ]
            },
            "x_max": {
                "type": "integer",
                "examples": [
                    10
                ]
            },
            "y_min": {
                "type": "integer",
                "examples": [
                    -5
                ]
            },
            "y_max": {
                "type": "integer",
                "examples": [
                    5
                ]
            }
        },
        "required": [
            "project_path",
            "name",
            "curve",
            "x_min",
            "x_max",
            "y_min",
            "y_max"
        ]
    },
},

"define-units": {
    "category": "modeling",
    "risk": "write",
    "description": "Set the CST project unit system.",
    "handler": "tool_define_units",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "length": {
                "type": "string",
                "examples": [
                    "mm"
                ]
            },
            "frequency": {
                "type": "string",
                "examples": [
                    "GHz"
                ]
            }
        },
        "required": [
            "project_path",
            "length",
            "frequency"
        ]
    },
},

"delete-entity": {
    "category": "modeling",
    "risk": "write",
    "description": "Delete a geometry entity from the CST project.",
    "handler": "tool_delete_entity",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "temp_shape"
                ]
            }
        },
        "required": [
            "project_path",
            "component",
            "name"
        ]
    },
},

"delete-monitor": {
    "category": "modeling",
    "risk": "write",
    "description": "Delete a monitor by name.",
    "handler": "tool_delete_monitor",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "monitor_name": {
                "type": "string",
                "examples": [
                    "farfield (f=10)"
                ]
            }
        },
        "required": [
            "project_path",
            "monitor_name"
        ]
    },
},

"delete-probe": {
    "category": "modeling",
    "risk": "write",
    "description": "Delete a probe by its ID.",
    "handler": "tool_delete_probe",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "probe_id": {
                "type": "string",
                "examples": [
                    "1"
                ]
            }
        },
        "required": [
            "project_path",
            "probe_id"
        ]
    },
},

"export-e-field": {
    "category": "modeling",
    "risk": "filesystem-write",
    "description": "Export E-field data at a given frequency to ASCII.",
    "handler": "tool_export_e_field",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "frequency": {
                "type": "string",
                "examples": [
                    "10"
                ]
            },
            "file_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\run\\exports"
                ]
            }
        },
        "required": [
            "project_path",
            "frequency",
            "file_path"
        ]
    },
},

"export-surface-current": {
    "category": "modeling",
    "risk": "filesystem-write",
    "description": "Export surface current data at a given frequency to ASCII.",
    "handler": "tool_export_surface_current",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "frequency": {
                "type": "string",
                "examples": [
                    "10"
                ]
            },
            "file_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\run\\exports"
                ]
            }
        },
        "required": [
            "project_path",
            "frequency",
            "file_path"
        ]
    },
},

"export-voltage": {
    "category": "modeling",
    "risk": "filesystem-write",
    "description": "Export voltage monitor data to ASCII.",
    "handler": "tool_export_voltage",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "voltage_index": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "file_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\run\\exports"
                ]
            }
        },
        "required": [
            "project_path",
            "voltage_index",
            "file_path"
        ]
    },
},

"list-entities": {
    "category": "modeling",
    "risk": "read",
    "description": "List geometry entities from the verified CST working project.",
    "handler": "tool_list_entities",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    ""
                ]
            }
        },
        "required": [
            "project_path",
            "component"
        ]
    },
},

"list-materials": {
    "category": "modeling",
    "risk": "read",
    "description": "List available CST material names from the Materials library.",
    "handler": "tool_list_materials",
    "json_schema": {
        "type": "object",
        "properties": {},
        "required": []
    },
},

"pick-face": {
    "category": "modeling",
    "risk": "write",
    "description": "Select a face by ID for loft operations (zero-thickness entities only).",
    "handler": "tool_pick_face",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "component": {
                "type": "string",
                "examples": [
                    "Component1"
                ]
            },
            "name": {
                "type": "string",
                "examples": [
                    "profile_wall"
                ]
            },
            "face_id": {
                "type": "string",
                "examples": [
                    "1"
                ]
            }
        },
        "required": [
            "project_path",
            "component",
            "name",
            "face_id"
        ]
    },
},

"rename-entity": {
    "category": "modeling",
    "risk": "write",
    "description": "Rename a geometry entity.",
    "handler": "tool_rename_entity",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "old_name": {
                "type": "string",
                "examples": [
                    "Component1:old_name"
                ]
            },
            "new_name": {
                "type": "string",
                "examples": [
                    "Component1:new_name"
                ]
            }
        },
        "required": [
            "project_path",
            "old_name",
            "new_name"
        ]
    },
},

"set-background-with-space": {
    "category": "modeling",
    "risk": "write",
    "description": "Set background space distances.",
    "handler": "tool_set_background_with_space",
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

"set-efield-monitor": {
    "category": "modeling",
    "risk": "write",
    "description": "Set an E-field monitor over a frequency range.",
    "handler": "tool_set_efield_monitor",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "start_freq": {
                "type": "number",
                "examples": [
                    2.0
                ]
            },
            "end_freq": {
                "type": "number",
                "examples": [
                    18.0
                ]
            },
            "step": {
                "type": "integer",
                "examples": [
                    1
                ]
            }
        },
        "required": [
            "project_path",
            "start_freq",
            "end_freq",
            "step"
        ]
    },
},

"set-entity-color": {
    "category": "modeling",
    "risk": "write",
    "description": "Set the display color of a geometry entity.",
    "handler": "tool_set_entity_color",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape_name": {
                "type": "string",
                "examples": [
                    "Component1:my_brick"
                ]
            },
            "r": {
                "type": "integer",
                "examples": [
                    255
                ]
            },
            "g": {
                "type": "integer",
                "examples": [
                    0
                ]
            },
            "b": {
                "type": "integer",
                "examples": [
                    0
                ]
            }
        },
        "required": [
            "project_path",
            "shape_name",
            "r",
            "g",
            "b"
        ]
    },
},

"set-farfield-monitor": {
    "category": "modeling",
    "risk": "write",
    "description": "Set a farfield monitor over a frequency range.",
    "handler": "tool_set_farfield_monitor",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "start_freq": {
                "type": "number",
                "examples": [
                    2.0
                ]
            },
            "end_freq": {
                "type": "number",
                "examples": [
                    18.0
                ]
            },
            "step": {
                "type": "integer",
                "examples": [
                    1
                ]
            }
        },
        "required": [
            "project_path",
            "start_freq",
            "end_freq",
            "step"
        ]
    },
},

"set-farfield-plot-cuts": {
    "category": "modeling",
    "risk": "write",
    "description": "Set farfield plot cut angles.",
    "handler": "tool_set_farfield_plot_cuts",
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

"set-field-monitor": {
    "category": "modeling",
    "risk": "write",
    "description": "Set a field monitor (e.g. H-field) over a frequency range.",
    "handler": "tool_set_field_monitor",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "field_type": {
                "type": "string",
                "examples": [
                    "H"
                ]
            },
            "start_frequency": {
                "type": "string",
                "examples": [
                    "2"
                ]
            },
            "end_frequency": {
                "type": "string",
                "examples": [
                    "18"
                ]
            },
            "num_samples": {
                "type": "string",
                "examples": [
                    "10"
                ]
            }
        },
        "required": [
            "project_path",
            "field_type",
            "start_frequency",
            "end_frequency",
            "num_samples"
        ]
    },
},

"set-probe": {
    "category": "modeling",
    "risk": "write",
    "description": "Set a field probe at a specified position.",
    "handler": "tool_set_probe",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "field_type": {
                "type": "string",
                "examples": [
                    "E"
                ]
            },
            "x_pos": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "y_pos": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "z_pos": {
                "type": "string",
                "examples": [
                    "5"
                ]
            }
        },
        "required": [
            "project_path",
            "field_type",
            "x_pos",
            "y_pos",
            "z_pos"
        ]
    },
},

"show-bounding-box": {
    "category": "modeling",
    "risk": "write",
    "description": "Toggle bounding box display.",
    "handler": "tool_show_bounding_box",
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

"transform-curve": {
    "category": "modeling",
    "risk": "write",
    "description": "Mirror a curve.",
    "handler": "tool_transform_curve",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "curve_name": {
                "type": "string",
                "examples": [
                    "curve1:my_curve"
                ]
            },
            "center_x": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "center_y": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "center_z": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "plane_normal_x": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "plane_normal_y": {
                "type": "string",
                "examples": [
                    "1"
                ]
            },
            "plane_normal_z": {
                "type": "string",
                "examples": [
                    "0"
                ]
            }
        },
        "required": [
            "project_path",
            "curve_name",
            "center_x",
            "center_y",
            "center_z",
            "plane_normal_x",
            "plane_normal_y",
            "plane_normal_z"
        ]
    },
},

"transform-shape": {
    "category": "modeling",
    "risk": "write",
    "description": "Mirror or rotate a geometry shape.",
    "handler": "tool_transform_shape",
    "json_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                ]
            },
            "shape_name": {
                "type": "string",
                "examples": [
                    "Component1:my_shape"
                ]
            },
            "transform_type": {
                "type": "string",
                "examples": [
                    "mirror"
                ]
            },
            "center_x": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "center_y": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "center_z": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "plane_normal_x": {
                "type": "string",
                "examples": [
                    "0"
                ]
            },
            "plane_normal_y": {
                "type": "string",
                "examples": [
                    "1"
                ]
            },
            "plane_normal_z": {
                "type": "string",
                "examples": [
                    "0"
                ]
            }
        },
        "required": [
            "project_path",
            "shape_name",
            "transform_type",
            "center_x",
            "center_y",
            "center_z",
            "plane_normal_x",
            "plane_normal_y",
            "plane_normal_z"
        ]
    },
},
}


# --- Handlers ---

from ..core import modeling as _md
from ..core.utils import project_path_from_args


def tool_define_material_from_mtd(args: dict) -> dict:
    return _md.define_material_from_mtd(
        project_path=project_path_from_args(args),
        material_name=str(args.get("material_name", "")),
    )


def tool_define_brick(args: dict) -> dict: return _md.define_brick(**args)
def tool_define_cylinder(args: dict) -> dict: return _md.define_cylinder(**args)
def tool_define_cone(args: dict) -> dict: return _md.define_cone(**args)
def tool_define_rectangle(args: dict) -> dict: return _md.define_rectangle(**args)
def tool_boolean_subtract(args: dict) -> dict: return _md.boolean_subtract(**args)
def tool_boolean_add(args: dict) -> dict: return _md.boolean_add(**args)
def tool_boolean_intersect(args: dict) -> dict: return _md.boolean_intersect(**args)
def tool_boolean_insert(args: dict) -> dict: return _md.boolean_insert(**args)
def tool_delete_entity(args: dict) -> dict: return _md.delete_entity(**args)
def tool_create_component(args: dict) -> dict: return _md.create_component(**args)
def tool_change_material(args: dict) -> dict: return _md.change_material(**args)
def tool_rename_entity(args: dict) -> dict: return _md.rename_entity(**args)
def tool_set_entity_color(args: dict) -> dict: return _md.set_entity_color(**args)
def tool_define_units(args: dict) -> dict: return _md.define_units(**args)
def tool_set_farfield_monitor(args: dict) -> dict: return _md.set_farfield_monitor(**args)
def tool_set_efield_monitor(args: dict) -> dict: return _md.set_efield_monitor(**args)
def tool_set_field_monitor(args: dict) -> dict: return _md.set_field_monitor(**args)
def tool_set_probe(args: dict) -> dict: return _md.set_probe(**args)
def tool_delete_probe(args: dict) -> dict: return _md.delete_probe_by_id(**args)
def tool_delete_monitor(args: dict) -> dict: return _md.delete_monitor(**args)
def tool_set_background_with_space(args: dict) -> dict: return _md.set_background_with_space(**args)
def tool_set_farfield_plot_cuts(args: dict) -> dict: return _md.set_farfield_plot_cuts(**args)
def tool_show_bounding_box(args: dict) -> dict: return _md.show_bounding_box(**args)
def tool_activate_post_process(args: dict) -> dict: return _md.activate_post_process_operation(**args)
def tool_create_mesh_group(args: dict) -> dict: return _md.create_mesh_group(**args)
def tool_define_polygon_3d(args: dict) -> dict: return _md.define_polygon_3d(**args)
def tool_define_analytical_curve(args: dict) -> dict: return _md.define_analytical_curve(**args)
def tool_define_extrude_curve(args: dict) -> dict: return _md.define_extrude_curve(**args)
def tool_transform_shape(args: dict) -> dict: return _md.transform_shape(**args)
def tool_transform_curve(args: dict) -> dict: return _md.transform_curve(**args)
def tool_create_horn_segment(args: dict) -> dict: return _md.create_horn_segment(**args)
def tool_create_loft_sweep(args: dict) -> dict: return _md.create_loft_sweep(**args)
def tool_create_hollow_sweep(args: dict) -> dict: return _md.create_hollow_sweep(**args)
def tool_add_to_history(args: dict) -> dict: return _md.add_to_history(**args)
def tool_pick_face(args: dict) -> dict: return _md.pick_face(**args)
def tool_define_loft(args: dict) -> dict: return _md.define_loft(**args)
def tool_export_e_field(args: dict) -> dict: return _md.export_e_field(**args)
def tool_export_surface_current(args: dict) -> dict: return _md.export_surface_current(**args)
def tool_export_voltage(args: dict) -> dict: return _md.export_voltage(**args)


_register_tool_defs(TOOL_DEFS)
