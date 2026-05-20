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


def build_args_templates() -> dict[str, dict]:
    """从 TOOL_DEFS 提取 args_template 子集。"""
    return {name: defn["args_template"] for name, defn in _ALL_DEFS.items()}


def build_direct_arg_specs() -> dict[str, dict]:
    """从 TOOL_DEFS 中提取 direct_flags=True 的 args_template 标量字段。

    只暴露字符串、数字、布尔值字段作为直接参数 `--flag value`。
    数组/对象/None 字段必须通过 `--args-file` 传入。
    """
    result: dict[str, dict] = {}
    for name, defn in _ALL_DEFS.items():
        if not defn.get("direct_flags", False):
            continue
        scalar_fields: dict[str, str] = {}
        for key, val in defn["args_template"].items():
            if isinstance(val, (str, int, float, bool)):
                scalar_fields[key] = str(val) if not isinstance(val, str) else val
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
