from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_local_module(module_name: str):
    repo_root = Path(__file__).resolve().parent.parent
    module_path = repo_root / "mcp" / f"{module_name}.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Local module does not exist: {module_path}")

    spec = importlib.util.spec_from_file_location(f"local_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module by file path: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module_path


def _load_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    if args.kwargs_json and args.kwargs_file:
        raise ValueError("--kwargs-json and --kwargs-file are mutually exclusive")
    if args.kwargs_json:
        return json.loads(args.kwargs_json)
    if args.kwargs_file:
        kwargs_path = Path(args.kwargs_file).resolve()
        return json.loads(kwargs_path.read_text(encoding="utf-8-sig"))
    return {}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Debug helper only: load repository mcp/*.py by file path and call a Python function directly. "
            "Final MCP tool acceptance must use tools/call through a running MCP server."
        )
    )
    parser.add_argument("--module", required=True, help="Local module name, e.g. cst_results_mcp")
    parser.add_argument("--function", required=True, help="Function name to call")
    parser.add_argument("--kwargs-json", help="Function kwargs as JSON")
    parser.add_argument("--kwargs-file", help="Path to a JSON file containing function kwargs")
    args = parser.parse_args()

    kwargs = _load_kwargs(args)
    module, module_path = _load_local_module(args.module)
    function = getattr(module, args.function, None)
    if function is None or not callable(function):
        raise AttributeError(f"{module_path} does not expose callable function: {args.function}")

    result = function(**kwargs)
    print(
        json.dumps(
            {
                "status": "success",
                "debug_only": True,
                "acceptance_note": "This is a direct Python function call, not MCP tools/call.",
                "module": str(module_path),
                "function": args.function,
                "kwargs": kwargs,
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
