"""Remaining CLI contract tests: output format and session management."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
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


def get_all_pipeline_names() -> list[str]:
    result = run_cli("list-pipelines")
    payload = json.loads(result.stdout)
    return [p["name"] for p in payload["pipelines"]]


class CliContractOutputFormatTests:
    """All CLI output follows the JSON contract."""

    def test_all_outputs_have_required_fields(self) -> None:
        for cmd in ("usage-guide", "list-tools", "list-pipelines"):
            r = run_cli(cmd)
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert "status" in p
            assert "adapter" in p
            assert p["adapter"] in ("cst_runtime_cli", "cst_runtime")

    def test_stdout_is_always_json(self) -> None:
        for cmd in ("--version", "--help"):
            r = run_cli(cmd)
            assert r.returncode == 0, r.stderr

    def test_pipeline_template_is_serializable(self) -> None:
        for pipe in get_all_pipeline_names():
            r = run_cli("pipeline-template", "--pipeline", pipe)
            assert r.returncode == 0, r.stderr[:200]
            json.loads(r.stdout)


class CliContractSessionTests:
    """Session/process management tools (no CST needed for dry-runs)."""

    def test_session_inspect_no_project_safe_json(self) -> None:
        r = run_cli("cst-session-inspect")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert "force_kill_allowlist" in p
        assert "process_count" in p
        assert "lock_count" in p
        assert "readiness" in p
        assert p["readiness"] in {"clear", "attention_required", "blocked"}

    def test_stage_evidence_capture_and_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            before = d / "before.json"
            after = d / "after.json"

            before_data = {
                "stage_name": "before", "project_path": "/dummy",
                "captured_at": "2026-01-01T00:00:00",
                "evidence": [
                    {"type": "parameters",
                     "data": {"g": 25.0, "thr": 12.5}},
                    {"type": "entities",
                     "data": [{"component": "C1", "name": "horn"}]},
                    {"type": "file_info",
                     "data": {"exists": True, "size_bytes": 1000}},
                ]
            }
            after_data = {
                "stage_name": "after", "project_path": "/dummy",
                "captured_at": "2026-01-01T00:01:00",
                "evidence": [
                    {"type": "parameters",
                     "data": {"g": 24.5, "thr": 12.5, "test_a": 15.0}},
                    {"type": "entities",
                     "data": [{"component": "C1", "name": "horn"},
                              {"component": "C1", "name": "ev_brick"}]},
                    {"type": "file_info",
                     "data": {"exists": True, "size_bytes": 1001}},
                ]
            }
            before.write_text(json.dumps(before_data), encoding="utf-8")
            after.write_text(json.dumps(after_data), encoding="utf-8")

            r = run_cli("stage-evidence", "--args-json", json.dumps({
                "compare": [str(before), str(after)],
                "output_html": str(d / "report.html"),
            }))
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            report = (d / "report.html").read_text(encoding="utf-8")
            assert "参数对比" in report
            assert "Entities" in report
            assert "changed" in report
            assert "added" in report
            assert "ev_brick" in report

    def test_session_quit_dry_run_safe(self) -> None:
        r = run_cli("cst-session-quit", "--dry-run", "true")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert p["dry_run"]
