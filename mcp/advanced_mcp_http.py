# -*- coding: utf-8 -*-
"""
HTTP 包装入口：复用 advanced_mcp 中已注册的工具，以 streamable-http 模式启动。
保留原 stdio 版本，便于 Codex 并行挂载两个 MCP 服务。
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def _load_base_module():
    module_path = Path(__file__).with_name("advanced_mcp.py")
    spec = importlib.util.spec_from_file_location("advanced_mcp_base", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载基础建模服务模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run CST modeler MCP over streamable HTTP."
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8123, help="监听端口")
    parser.add_argument("--path", default="/mcp", help="HTTP 挂载路径")
    parser.add_argument(
        "--log-level",
        default="ERROR",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base_module = _load_base_module()
    mcp = base_module.mcp
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = args.path
    mcp.settings.log_level = args.log_level
    mcp.run(transport="streamable-http")
