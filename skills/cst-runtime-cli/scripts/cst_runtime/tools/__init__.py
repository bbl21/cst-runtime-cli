"""tools/__init__.py — 工具注册表

收集所有域的 TOOL_DEFS，提供构建 TOOLS 字典的函数。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


# 各域 TOOL_DEFS 在此收集
_ALL_DEFS: dict[str, dict] = {}


def _register_tool_defs(defs: dict[str, dict]) -> None:
    """注册一个域的 TOOL_DEFS。"""
    conflicts = _ALL_DEFS.keys() & defs.keys()
    if conflicts:
        raise ValueError(f"Duplicate tool names: {conflicts}")
    _ALL_DEFS.update(defs)


def all_defs() -> dict[str, dict]:
    return dict(_ALL_DEFS)


def build_tools(handler_map: dict[str, Callable]) -> dict[str, dict]:
    """从 TOOL_DEFS + handler_map 生成 TOOLS dict。

    handler_map: {"tool_generate_report": <function>, ...}
    """
    from cst_runtime.cli.dispatch import _tool_governance

    tools: dict[str, dict] = {}
    for name, defn in _ALL_DEFS.items():
        h = handler_map.get(defn["handler"])
        if h is None:
            raise KeyError(f"Handler '{defn['handler']}' for tool '{name}' not found in handler_map")
        record = {
            "category": defn["category"],
            "risk": defn["risk"],
            "description": defn["description"],
            "function": h,
        }
        record.update(_tool_governance(name, record))
        tools[name] = record
    return tools


def _schema_to_template(schema: dict) -> dict:
    """从 JSON Schema 生成示例值模板，含语义路径推理。"""
    template: dict = {}
    for key, prop in schema.get("properties", {}).items():
        if "default" in prop:
            template[key] = prop["default"]
        elif "examples" in prop and prop["examples"]:
            template[key] = prop["examples"][0]
        else:
            ptype = prop.get("type", "string")
            if ptype == "string":
                kl = key.lower()
                if "project_path" in kl or ("path" in kl and "project" in kl):
                    template[key] = "C:\\path\\to\\tasks\\task_xxx\\runs\\run_001\\projects\\working.cst"
                elif "workspace" in kl:
                    template[key] = "C:\\path\\to\\workspace"
                elif key == "treepath":
                    template[key] = "1D Results\\S-Parameters\\S1,1"
                elif "output" in kl or "export" in kl or "file_path" in kl:
                    template[key] = ""
                else:
                    template[key] = ""
            elif ptype in ("number", "integer"):
                template[key] = prop.get("minimum", 0)
            elif ptype == "boolean":
                template[key] = False
            elif ptype == "array":
                template[key] = []
            elif ptype == "object":
                if "default" in prop:
                    template[key] = prop["default"]
                else:
                    template[key] = _schema_to_template(prop)
            else:
                template[key] = None
    return template


def build_args_templates() -> dict[str, dict]:
    """从 TOOL_DEFS 的 json_schema 生成 args 模板。"""
    result: dict[str, dict] = {}
    for name, defn in _ALL_DEFS.items():
        if "json_schema" in defn:
            result[name] = _schema_to_template(defn["json_schema"])
    return result


def build_json_schemas() -> dict[str, dict]:
    """从 TOOL_DEFS 提取 json_schema 子集。"""
    return {name: defn["json_schema"] for name, defn in _ALL_DEFS.items() if "json_schema" in defn}


def build_direct_arg_specs() -> dict[str, dict]:
    """从 json_schema 推导支持直接参数的工具。
    只要有 string/number/integer/boolean 类型属性即可。
    """
    result: dict[str, dict] = {}
    for name, defn in _ALL_DEFS.items():
        scalar_fields: dict[str, str] = {}
        schema = defn.get("json_schema", {})
        for key, prop in schema.get("properties", {}).items():
            ptype = prop.get("type", "string")
            if ptype in ("string", "number", "integer", "boolean"):
                example = ""
                if "examples" in prop and prop["examples"]:
                    example = str(prop["examples"][0])
                elif "default" in prop:
                    example = str(prop["default"])
                scalar_fields[key] = example
        if scalar_fields:
            result[name] = scalar_fields
    return result


def count() -> int:
    return len(_ALL_DEFS)


# === 自动导入所有域模块（触发 _register_tool_defs） ===
from . import simulation  # noqa: E402, F811
from . import modeling  # noqa: E402, F811
from . import project  # noqa: E402, F811
from . import results  # noqa: E402, F811
from . import farfield  # noqa: E402, F811
from . import session  # noqa: E402, F811
from . import audit  # noqa: E402, F811
from . import workspace  # noqa: E402, F811
from . import optimization  # noqa: E402, F811
from . import doe  # noqa: E402, F811


def _template_to_schema(template: dict) -> dict:
    """Convert args_template dict to json_schema format."""
    properties = {}
    required = []
    for key, val in template.items():
        if isinstance(val, bool):
            prop = {"type": "boolean", "examples": [val]}
        elif isinstance(val, int):
            prop = {"type": "integer", "examples": [val]}
        elif isinstance(val, float):
            prop = {"type": "number", "examples": [val]}
        elif isinstance(val, list):
            item_type = "number" if val and all(isinstance(x, (int, float)) for x in val) else "string"
            prop = {"type": "array", "items": {"type": item_type}, "examples": [val]}
        elif isinstance(val, dict):
            prop = {"type": "object", "examples": [val]}
        elif isinstance(val, str):
            prop = {"type": "string", "examples": [val]}
        else:
            prop = {"type": "string", "examples": [str(val)]}
        properties[key] = prop
        required.append(key)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _migrate_all_defs(dry_run: bool = True) -> dict:
    """Convert all args_template entries to json_schema. Returns migration report."""
    migrated = 0
    schema_only = 0
    for name, defn in _ALL_DEFS.items():
        if "json_schema" in defn:
            schema_only += 1
            continue
        if "args_template" in defn:
            if not dry_run:
                defn["json_schema"] = _template_to_schema(defn["args_template"])
                defn.pop("args_template", None)
                defn.pop("direct_flags", None)
            migrated += 1
    return {"migrated": migrated, "schema_only": schema_only, "dry_run": dry_run}
