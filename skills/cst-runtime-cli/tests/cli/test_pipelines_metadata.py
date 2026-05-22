"""Pipeline metadata, registration, and error-path tests (merged)."""

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


class TestPipelinesMetadata:
    """Every pipeline has valid metadata and is documented (CLI-based)."""

    def test_all_pipelines_are_listed(self) -> None:
        names = get_all_pipeline_names()
        assert len(names) > 5, f"Only {len(names)} pipelines found"

    def test_every_pipeline_describe_returns_success(self) -> None:
        for pipe in get_all_pipeline_names():
            r = run_cli("describe-pipeline", "--pipeline", pipe)
            assert r.returncode == 0, r.stderr[:200]
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            assert p["pipeline"] == pipe
            assert "category" in p["recipe"]
            assert "risk" in p["recipe"]
            assert "steps" in p["recipe"]

    def test_every_pipeline_template_generates_plan(self) -> None:
        for pipe in get_all_pipeline_names():
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / f"{pipe}_plan.json"
                r = run_cli("pipeline-template", "--pipeline", pipe, "--output", str(out))
                assert r.returncode == 0, r.stderr[:200]
                assert out.exists()
                plan = json.loads(out.read_text(encoding="utf-8"))
                assert plan["pipeline"] == pipe

    def test_unknown_pipeline_returns_json_error(self) -> None:
        r = run_cli("describe-pipeline", "--pipeline", "nonexistent-pipeline-xyz")
        assert r.returncode == 1
        p = json.loads(r.stdout)
        assert p["status"] == "error"
        assert p["error_type"] == "unknown_pipeline"
        assert "available_pipelines" in p

    def test_every_pipeline_step_tool_exists(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.dispatch import TOOLS
        from cst_runtime.cli.pipelines.registry import PIPELINES

        known_tools = set(TOOLS) | {
            "help", "list-tools", "list-pipelines", "describe-tool",
            "describe-pipeline", "args-template", "pipeline-template",
            "usage-guide", "invoke",
        }
        placeholders = {"<tool>", "--help"}
        missing: list[str] = []
        for pipe_name, pipe_def in PIPELINES.items():
            for step in pipe_def.get("steps", []):
                tool = step.get("tool", "")
                if tool in placeholders:
                    continue
                if tool not in known_tools:
                    missing.append(f"{pipe_name}: unknown tool {tool!r}")
        assert not missing, "\n".join(missing)


class TestPipelineToolRegistration:
    """Pipeline tools are registered in TOOLS, have correct metadata and templates."""

    def test_pipeline_tools_registered(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.dispatch import TOOLS
        for name in ("inspect-project", "prepare-experiment", "run-experiment"):
            assert name in TOOLS, f"Missing tool: {name}"

    def test_pipeline_metadata(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.dispatch import TOOLS
        assert TOOLS["inspect-project"]["category"] == "project_ops"
        assert TOOLS["inspect-project"]["risk"] == "read"
        assert TOOLS["prepare-experiment"]["category"] == "project_ops"
        assert TOOLS["prepare-experiment"]["risk"] == "write"
        assert TOOLS["run-experiment"]["category"] == "simulation"
        assert TOOLS["run-experiment"]["risk"] == "long-running"

    def test_pipeline_args_templates(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.tools import build_args_templates
        templates = build_args_templates()
        for name in ("inspect-project", "prepare-experiment", "run-experiment"):
            assert name in templates, f"Missing args template: {name}"

    def test_pipeline_descriptions(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.pipelines.registry import PIPELINES
        for name in ("inspect-project", "prepare-experiment", "run-experiment"):
            assert name in PIPELINES, f"Missing pipeline: {name}"


class TestPipelineErrorPaths:
    """Pipeline implementation error paths (pure Python, no CST)."""

    def test_inspect_project_missing_path(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.pipelines.impl import pipeline_inspect_project
        result = pipeline_inspect_project("/nonexistent/path.cst")
        assert result["status"] == "error"
        assert "pipeline_open_failed" in result.get("error_type", "")

    def test_prepare_experiment_missing_param_name(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.pipelines.impl import pipeline_prepare_experiment
        result = pipeline_prepare_experiment(
            project_path="/nonexistent/path.cst",
            param_name="",
            param_value=23.5,
        )
        assert result["status"] == "error"
        assert result["error_type"] == "pipeline_param_missing"

    def test_prepare_experiment_missing_project(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.pipelines.impl import pipeline_prepare_experiment
        result = pipeline_prepare_experiment(
            project_path="/nonexistent/p.cst",
            param_name="g",
            param_value=23.5,
        )
        assert result["status"] == "error"

    def test_run_experiment_missing_project(self) -> None:
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from cst_runtime.cli.pipelines.impl import pipeline_run_experiment
        result = pipeline_run_experiment(project_path="/nonexistent/p.cst")
        assert result["status"] == "error"
