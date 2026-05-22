"""Governance rules embedded in tool metadata."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli"
PYTHON = sys.executable
_PYTHONPATH = str(SKILL_ROOT / "scripts")


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


class TestGovernance:
    """Governance rules embedded in tool metadata."""

    def test_modeling_write_tools_have_governance(self) -> None:
        modeling_writes = {
            "define-brick", "define-cylinder", "define-cone", "define-rectangle",
            "boolean-subtract", "boolean-add", "boolean-intersect", "boolean-insert",
            "delete-entity", "create-component", "change-material",
        }
        for tool in modeling_writes:
            r = run_cli("describe-tool", "--tool", tool)
            if r.returncode != 0:
                continue
            p = json.loads(r.stdout)
            meta = p.get("tool", {})
            assert "pipeline_mode" in meta
            assert "requires_run_context" in meta
            assert "requires_check_solid" in meta

    def test_read_tools_do_not_require_check_solid(self) -> None:
        read_tools = {"list-parameters", "list-entities", "list-materials",
                       "cst-session-inspect"}
        for tool in read_tools:
            r = run_cli("describe-tool", "--tool", tool)
            if r.returncode != 0:
                continue
            p = json.loads(r.stdout)
            meta = p.get("tool", {})
            if meta.get("requires_check_solid"):
                assert meta.get("pipeline_mode") == "read_only"

    def test_session_tools_have_correct_risk_labels(self) -> None:
        session_risks = {
            "cst-session-open": "session",
            "cst-session-close": "session",
            "cst-session-quit": "process-control",
            "cst-session-inspect": "read",
            "cst-session-reattach": "read",
        }
        for tool, expected_risk in session_risks.items():
            r = run_cli("describe-tool", "--tool", tool)
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert p["tool"]["risk"] == expected_risk
