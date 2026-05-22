"""Tool metadata: listing, describe, args-template, and error paths."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli"
PYTHON = sys.executable
_PYTHONPATH = str(SKILL_ROOT / "scripts")

_CST_REQUIRED_TOOLS = {
    "cst-session-open", "cst-session-close", "cst-session-reattach",
    "define-brick", "define-cylinder", "define-cone", "define-rectangle",
    "boolean-subtract", "boolean-add", "boolean-intersect", "boolean-insert",
    "delete-entity", "create-component", "change-material",
    "list-entities", "list-parameters", "change-parameter",
    "start-simulation-async", "is-simulation-running",
    "wait-simulation", "stop-simulation", "pause-simulation", "resume-simulation",
    "save-project", "verify-project-identity", "define-material-from-mtd",
    "list-open-projects", "open-results-project", "list-subprojects",
    "list-run-ids", "get-parameter-combination", "get-1d-result", "get-2d-result",
    "create-blank-project",
    "define-frequency-range", "change-solver-type",
    "define-background", "define-boundary", "define-mesh", "define-solver",
    "define-port", "define-monitor", "rename-entity", "set-entity-color",
    "define-units", "set-farfield-monitor", "set-efield-monitor",
    "set-field-monitor", "set-probe", "delete-probe", "delete-monitor",
    "set-background-with-space", "set-farfield-plot-cuts", "show-bounding-box",
    "activate-post-process", "create-mesh-group", "set-solver-acceleration",
    "set-fdsolver-extrude-open-bc", "set-mesh-fpbavoid-nonreg-unite",
    "set-mesh-minimum-step-number", "define-polygon-3d",
    "define-analytical-curve", "define-extrude-curve",
    "transform-shape", "transform-curve",
    "create-horn-segment", "create-loft-sweep", "create-hollow-sweep",
    "add-to-history", "pick-face", "define-loft",
    "export-e-field", "export-surface-current", "export-voltage",
    "define-parameters",
    "export-farfield-fresh-session", "export-existing-farfield-cut-fresh-session",
    "read-realized-gain-grid-fresh-session",
}


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": _PYTHONPATH}
    return subprocess.run(
        [PYTHON, "-m", "cst_runtime", *args],
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def get_all_tool_names() -> list[str]:
    result = run_cli("list-tools")
    payload = json.loads(result.stdout)
    return [t["name"] for t in payload["tools"]]


class TestToolsMetadata:
    """Every tool has valid metadata, args template, and consistent JSON output."""

    def test_all_tools_are_listed(self) -> None:
        names = get_all_tool_names()
        assert len(names) > 50, f"Only {len(names)} tools found"

    def test_every_tool_describe_returns_success(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            r = run_cli("describe-tool", "--tool", tool)
            assert r.returncode == 0, r.stderr[:200]
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            assert p["tool"]["name"] == tool
            assert "category" in p["tool"]
            assert "risk" in p["tool"]
            assert "description" in p["tool"]

    def test_every_tool_has_args_template(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            r = run_cli("args-template", "--tool", tool)
            assert r.returncode == 0, r.stderr[:200]
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            assert p["tool"] == tool
            assert isinstance(p["args_template"], dict)

    def test_args_template_writes_valid_json_file(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / f"{tool}_args.json"
                r = run_cli("args-template", "--tool", tool, "--output", str(out))
                assert r.returncode == 0, r.stderr[:200]
                p = json.loads(r.stdout)
                assert p["status"] == "success"
                assert Path(p["output_path"]) == out
                written = json.loads(out.read_text(encoding="utf-8"))
                assert isinstance(written, dict)

    def test_unknown_tool_returns_json_error(self) -> None:
        r = run_cli("describe-tool", "--tool", "nonexistent-tool-xyz")
        assert r.returncode == 1
        p = json.loads(r.stdout)
        assert p["status"] == "error"
        assert p["error_type"] == "unknown_tool"
        assert "available_tools" in p

    def test_unknown_arg_template_returns_json_error(self) -> None:
        r = run_cli("args-template", "--tool", "nonexistent-tool-xyz")
        assert r.returncode == 1
        p = json.loads(r.stdout)
        assert p["status"] == "error"
        assert p["error_type"] == "unknown_tool"
