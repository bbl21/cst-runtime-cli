from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _load_arguments(args: argparse.Namespace) -> dict[str, Any]:
    if args.arguments_json and args.arguments_file:
        raise ValueError("--arguments-json and --arguments-file are mutually exclusive")
    if args.arguments_json:
        return json.loads(args.arguments_json)
    if args.arguments_file:
        path = Path(args.arguments_file).resolve()
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _parse_json_text(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return None


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    tool_arguments = _load_arguments(args)
    timeout = httpx.Timeout(args.timeout_seconds, read=args.read_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as http_client:
        async with streamable_http_client(args.url, http_client=http_client) as (
            read_stream,
            write_stream,
            get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                initialize_result = await session.initialize()
                list_result = await session.list_tools()
                tool_names = [tool.name for tool in list_result.tools]

                response: dict[str, Any] = {
                    "status": "success",
                    "url": args.url,
                    "session_id": get_session_id(),
                    "server": initialize_result.model_dump(mode="json"),
                    "tool_count": len(tool_names),
                    "tool_names": tool_names if args.include_tool_names else None,
                    "listed": args.tool in tool_names if args.tool else None,
                }

                if args.list_only:
                    return response
                if not args.tool:
                    raise ValueError("--tool is required unless --list-only is set")
                if args.tool not in tool_names:
                    raise ValueError(f"Tool is not registered by server: {args.tool}")

                call_result = await session.call_tool(args.tool, tool_arguments)
                content = call_result.model_dump(mode="json")
                parsed_text = None
                if call_result.content:
                    first = call_result.content[0]
                    if getattr(first, "type", None) == "text":
                        parsed_text = _parse_json_text(getattr(first, "text", ""))

                response.update(
                    {
                        "tool": args.tool,
                        "arguments": tool_arguments,
                        "call_result": content,
                        "parsed_text_result": parsed_text,
                        "is_error": call_result.isError,
                    }
                )
                return response


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Call an MCP tool through a running streamable-http MCP server."
    )
    parser.add_argument("--url", required=True, help="MCP streamable-http URL, e.g. http://127.0.0.1:8124/mcp")
    parser.add_argument("--tool", help="MCP tool name to call")
    parser.add_argument("--arguments-json", help="Tool arguments as JSON")
    parser.add_argument("--arguments-file", help="Path to a JSON file containing tool arguments")
    parser.add_argument("--list-only", action="store_true", help="Only run initialize and tools/list")
    parser.add_argument("--include-tool-names", action="store_true", help="Include full tool name list in output")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--read-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--output-file", help="Optional path to write the JSON response")
    args = parser.parse_args()

    result = anyio.run(_run, args, backend="asyncio")
    output = json.dumps(result, ensure_ascii=False, indent=2, default=_json_default)
    if args.output_file:
        output_path = Path(args.output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
