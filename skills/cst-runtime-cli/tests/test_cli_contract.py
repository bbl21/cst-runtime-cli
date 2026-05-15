"""No-CST-start CLI contract checks for cst_runtime.

Covers every tool, pipeline, args template, JSON contract, and error path
that can be validated without starting CST Studio Suite.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli"
CLI = SKILL_ROOT / "scripts" / "cst_runtime_cli.py"
PYTHON = sys.executable

# Tools that require CST session — cannot test without real CST
_CST_REQUIRED_TOOLS = {
    "cst-session-open", "cst-session-close", "cst-session-reattach",
    "define-brick", "define-cylinder", "define-cone", "define-rectangle",
    "boolean-subtract", "boolean-add", "boolean-intersect", "boolean-insert",
    "delete-entity", "create-component", "change-material",
    "list-entities", "list-parameters", "change-parameter",
    "start-simulation", "start-simulation-async", "is-simulation-running",
    "wait-simulation", "stop-simulation", "pause-simulation", "resume-simulation",
    "save-project", "verify-project-identity", "define-material-from-mtd",
    "list-open-projects", "open-results-project", "list-subprojects",
    "list-run-ids", "get-parameter-combination", "get-1d-result", "get-2d-result",
    "plot-project-result", "create-blank-project",
    "define-frequency-range", "change-frequency-range", "change-solver-type",
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

# Tools that can be tested without any workspace
_NO_WORKSPACE_TOOLS = {
    "doctor", "usage-guide", "list-tools", "list-pipelines",
    "describe-tool", "describe-pipeline", "args-template", "pipeline-template",
    "init-workspace", "init-task",
    "inspect-cst-environment", "cleanup-cst-processes",
    "cst-session-inspect", "cst-session-quit",
    "generate-s11-comparison", "generate-s11-farfield-dashboard",
    "plot-exported-file", "inspect-farfield-ascii", "plot-farfield-multi",
    "calculate-farfield-neighborhood-flatness",
    "list-materials", "install-cst-libraries", "health-check",
}

# All tools that don't need CST but still need a workspace:
_NO_CST_TOOLS = _NO_WORKSPACE_TOOLS | {
    "prepare-run", "get-run-context",
    "record-stage", "update-status",
    "infer-run-dir", "wait-project-unlocked",
}


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(CLI), *args],
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def get_all_tool_names() -> list[str]:
    result = run_cli("list-tools")
    payload = json.loads(result.stdout)
    return [t["name"] for t in payload["tools"]]


def get_all_pipeline_names() -> list[str]:
    result = run_cli("list-pipelines")
    payload = json.loads(result.stdout)
    return [p["name"] for p in payload["pipelines"]]


def _run_in_workspace(args: list[str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        init = run_cli("init-workspace", "--workspace", str(ws))
        assert init.returncode == 0
        return run_cli(*args, "--workspace", str(ws))


class CliContractAllToolsTests(unittest.TestCase):
    """Every tool has valid metadata, args template, and consistent JSON output."""

    def test_all_tools_are_listed(self) -> None:
        names = get_all_tool_names()
        self.assertGreater(len(names), 50, f"Only {len(names)} tools found")

    def test_every_tool_describe_returns_success(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            with self.subTest(tool=tool):
                r = run_cli("describe-tool", "--tool", tool)
                self.assertEqual(r.returncode, 0, r.stderr[:200])
                p = json.loads(r.stdout)
                self.assertEqual(p["status"], "success")
                self.assertEqual(p["tool"]["name"], tool)
                self.assertIn("category", p["tool"])
                self.assertIn("risk", p["tool"])
                self.assertIn("description", p["tool"])

    def test_every_tool_has_args_template(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            with self.subTest(tool=tool):
                r = run_cli("args-template", "--tool", tool)
                self.assertEqual(r.returncode, 0, r.stderr[:200])
                p = json.loads(r.stdout)
                self.assertEqual(p["status"], "success")
                self.assertEqual(p["tool"], tool)
                self.assertIsInstance(p["args_template"], dict)

    def test_args_template_writes_valid_json_file(self) -> None:
        for tool in get_all_tool_names():
            if tool in _CST_REQUIRED_TOOLS:
                continue
            with self.subTest(tool=tool):
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / f"{tool}_args.json"
                    r = run_cli("args-template", "--tool", tool, "--output", str(out))
                    self.assertEqual(r.returncode, 0, r.stderr[:200])
                    p = json.loads(r.stdout)
                    self.assertEqual(p["status"], "success")
                    self.assertEqual(Path(p["output_path"]), out)
                    written = json.loads(out.read_text(encoding="utf-8"))
                    self.assertIsInstance(written, dict)

    def test_unknown_tool_returns_json_error(self) -> None:
        r = run_cli("describe-tool", "--tool", "nonexistent-tool-xyz")
        self.assertEqual(r.returncode, 1)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "error")
        self.assertEqual(p["error_type"], "unknown_tool")
        self.assertIn("available_tools", p)

    def test_unknown_arg_template_returns_json_error(self) -> None:
        r = run_cli("args-template", "--tool", "nonexistent-tool-xyz")
        self.assertEqual(r.returncode, 1)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "error")
        self.assertEqual(p["error_type"], "unknown_tool")


class CliContractAllPipelinesTests(unittest.TestCase):
    """Every pipeline has valid metadata and is documented."""

    def test_all_pipelines_are_listed(self) -> None:
        names = get_all_pipeline_names()
        self.assertGreater(len(names), 5, f"Only {len(names)} pipelines found")

    def test_every_pipeline_describe_returns_success(self) -> None:
        for pipe in get_all_pipeline_names():
            with self.subTest(pipeline=pipe):
                r = run_cli("describe-pipeline", "--pipeline", pipe)
                self.assertEqual(r.returncode, 0, r.stderr[:200])
                p = json.loads(r.stdout)
                self.assertEqual(p["status"], "success")
                self.assertEqual(p["pipeline"], pipe)
                self.assertIn("category", p["recipe"])
                self.assertIn("risk", p["recipe"])
                self.assertIn("steps", p["recipe"])

    def test_every_pipeline_template_generates_plan(self) -> None:
        for pipe in get_all_pipeline_names():
            with self.subTest(pipeline=pipe):
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / f"{pipe}_plan.json"
                    r = run_cli("pipeline-template", "--pipeline", pipe, "--output", str(out))
                    self.assertEqual(r.returncode, 0, r.stderr[:200])
                    self.assertTrue(out.exists())
                    plan = json.loads(out.read_text(encoding="utf-8"))
                    self.assertEqual(plan["pipeline"], pipe)

    def test_unknown_pipeline_returns_json_error(self) -> None:
        r = run_cli("describe-pipeline", "--pipeline", "nonexistent-pipeline-xyz")
        self.assertEqual(r.returncode, 1)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "error")
        self.assertEqual(p["error_type"], "unknown_pipeline")
        self.assertIn("available_pipelines", p)


class CliContractOutputFormatTests(unittest.TestCase):
    """All CLI output follows the JSON contract."""

    def test_all_outputs_have_required_fields(self) -> None:
        for cmd in ("doctor", "usage-guide", "list-tools", "list-pipelines"):
            with self.subTest(command=cmd):
                r = run_cli(cmd)
                self.assertEqual(r.returncode, 0, r.stderr)
                p = json.loads(r.stdout)
                self.assertIn("status", p)
                self.assertIn("adapter", p)
                self.assertEqual(p["adapter"], "cst_runtime_cli")

    def test_error_outputs_have_error_type(self) -> None:
        r = run_cli("prepare-run")
        self.assertIn(r.returncode, {1, 2})
        p = json.loads(r.stdout)
        self.assertIn("error_type", p)
        self.assertIn("adapter", p)

    def test_stdout_is_always_json(self) -> None:
        for cmd in ("--version", "--help"):
            with self.subTest(command=cmd):
                r = run_cli(cmd)
                self.assertEqual(r.returncode, 0, r.stderr)
                # version/help are plain text, ok

    def test_pipeline_template_is_serializable(self) -> None:
        for pipe in get_all_pipeline_names():
            with self.subTest(pipeline=pipe):
                r = run_cli("pipeline-template", "--pipeline", pipe)
                self.assertEqual(r.returncode, 0, r.stderr[:200])
                json.loads(r.stdout)


class CliContractNoCstFunctionalTests(unittest.TestCase):
    """Functional tests for tools that work without CST."""

    def test_inspect_cst_environment_returns_structure(self) -> None:
        r = run_cli("inspect-cst-environment")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertIn("process_count", p)
        self.assertIn("lock_count", p)
        self.assertIn("project_path", p)
        self.assertIn("readiness", p)

    def test_cleanup_cst_processes_dry_run_does_not_kill(self) -> None:
        r = run_cli("cleanup-cst-processes", "--dry-run", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertEqual(p["cleanup_status"], "dry_run")

    def test_list_materials_returns_names(self) -> None:
        r = run_cli("list-materials")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertGreater(p["count"], 0)
        self.assertIsInstance(p["material_names"], list)

    def test_install_cst_libraries_dry_run_scans(self) -> None:
        r = run_cli("install-cst-libraries", "--dry-run", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertTrue(p["dry_run"])
        self.assertIn("target_path", p)
        self.assertIn("scan", p)

    def test_health_check_reports_status(self) -> None:
        r = run_cli("health-check", "--auto-fix", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertIn("overall", p)
        self.assertIn("checks", p)
        self.assertIn("fixes_applied", p)
        self.assertIn("remaining_issues", p)
        self.assertIn("readiness_summary", p)

    def test_health_check_without_auto_fix(self) -> None:
        r = run_cli("health-check", "--auto-fix", "false")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertIn("overall", p)

    def test_generate_s11_comparison_with_stub_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            s11 = d / "s11.json"
            s11.write_text(json.dumps({
                "run_id": 1, "xdata": [9.0, 10.0, 11.0],
                "ydata": [{"real": 0.3, "imag": 0.0}, {"real": 0.1, "imag": 0.0}, {"real": 0.2, "imag": 0.0}],
            }), encoding="utf-8")
            args = {"file_paths": [str(s11)], "output_html": str(d / "out.html"), "page_title": "S11 Test"}
            r = run_cli("generate-s11-comparison", "--args-json", json.dumps(args))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            self.assertTrue((d / "out.html").exists())

    def test_plot_exported_file_with_s11_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            s11 = d / "s11.json"
            s11.write_text(json.dumps({
                "run_id": 1, "xdata": [9.0, 10.0, 11.0],
                "ydata": [{"real": 0.3, "imag": 0.0}, {"real": 0.1, "imag": 0.0}, {"real": 0.2, "imag": 0.0}],
            }), encoding="utf-8")
            r = run_cli("plot-exported-file", "--file-path", str(s11), "--output-html", str(d / "preview.html"), "--page-title", "Test")
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            self.assertTrue((d / "preview.html").exists())

    def test_inspect_farfield_ascii_with_stub_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            ff = d / "farfield.txt"
            lines = ["Theta Phi Abs(Realized Gain)[dBi]", "0 0 14.5", "0 180 14.3", "10 0 13.8", "10 180 13.6"]
            ff.write_text("\n".join(lines), encoding="utf-8")
            args = {"file_path": str(ff)}
            r = run_cli("inspect-farfield-ascii", "--args-json", json.dumps(args))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            self.assertEqual(p["grid"]["row_count"], 4)

    def test_plot_farfield_multi_with_stub_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            ff = d / "farfield.txt"
            lines = ["Theta Phi Abs(Realized Gain)[dBi]", "0 0 14.5", "0 180 14.3", "10 0 13.8", "10 180 13.6"]
            ff.write_text("\n".join(lines), encoding="utf-8")
            r = run_cli("plot-farfield-multi", "--args-json", json.dumps({
                "file_paths": [str(ff)], "output_html": str(d / "ff.html"), "page_title": "FF Test"
            }))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            self.assertTrue((d / "ff.html").exists())

    def test_calculate_farfield_flatness_with_stub_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            for fn in ("cut0.json", "cut90.json"):
                angles = list(range(-15, 16))
                gains = [14.0 - abs(t) * 0.1 for t in angles]
                (d / fn).write_text(json.dumps({
                    "angle_deg": angles,
                    "primary_db": gains,
                }), encoding="utf-8")
            r = run_cli("calculate-farfield-neighborhood-flatness", "--args-json", json.dumps({
                "file_paths": [str(d / "cut0.json"), str(d / "cut90.json")],
                "theta_max_deg": 15.0, "output_json": str(d / "flatness.json")
            }))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")

    def test_record_and_update_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            run_cli("init-task", "--workspace", str(ws), "--task-id", "task_test", "--source-project", str(ws / "missing.cst"), "--goal", "test")
            task_json = ws / "tasks" / "task_test" / "task.json"
            self.assertTrue(task_json.exists())

            run_dir = ws / "tasks" / "task_test" / "runs" / "run_001"
            run_dir.mkdir(parents=True, exist_ok=True)

            stage = run_cli("record-stage", "--args-json", json.dumps({
                "task_path": str(task_json.parent), "run_id": "run_001",
                "stage": "test", "status": "completed", "message": "test",
            }), "--workspace", str(ws))
            self.assertEqual(stage.returncode, 0, stage.stderr)
            sp = json.loads(stage.stdout)
            self.assertEqual(sp["status"], "success")

            status = run_cli("update-status", "--args-json", json.dumps({
                "task_path": str(task_json.parent), "run_id": "run_001",
                "status": "validated", "stage": "test",
            }), "--workspace", str(ws))
            self.assertEqual(status.returncode, 0, status.stderr)
            up = json.loads(status.stdout)
            self.assertEqual(up["status"], "success")

    def test_wait_project_unlocked_no_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            fake_project = ws / "projects" / "working.cst"
            fake_project.parent.mkdir(parents=True, exist_ok=True)
            fake_project.write_text("fake", encoding="utf-8")
            r = run_cli("wait-project-unlocked", "--project-path", str(fake_project), "--timeout-seconds", "1", "--workspace", str(ws))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertIn("locked", p)

    def test_infer_run_dir_no_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            fake = ws / "some" / "path" / "working.cst"
            fake.parent.mkdir(parents=True, exist_ok=True)
            fake.write_text("fake", encoding="utf-8")
            r = run_cli("infer-run-dir", "--project-path", str(fake), "--workspace", str(ws))
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            self.assertIsNone(p["run_dir"])

    def test_prepare_run_missing_source_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            run_cli("init-task", "--workspace", str(ws), "--task-id", "task_test", "--source-project", str(ws / "missing.cst"), "--goal", "test")
            task_path = ws / "tasks" / "task_test"
            r = run_cli("prepare-run", "--args-json", json.dumps({"task_path": str(task_path)}), "--workspace", str(ws))
            self.assertEqual(r.returncode, 1)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "error")
            self.assertEqual(p["error_type"], "source_project_missing")

    def test_production_tool_requires_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            r = run_cli("prepare-run", "--workspace", tmpdir, "--args-json", json.dumps({"task_path": str(Path(tmpdir) / "tasks" / "task_001")}))
            self.assertEqual(r.returncode, 1)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "error")
            self.assertEqual(p["error_type"], "workspace_not_initialized")


class CliContractGovernanceTests(unittest.TestCase):
    """Governance rules embedded in tool metadata."""

    def test_modeling_write_tools_have_governance(self) -> None:
        modeling_writes = {
            "define-brick", "define-cylinder", "define-cone", "define-rectangle",
            "boolean-subtract", "boolean-add", "boolean-intersect", "boolean-insert",
            "delete-entity", "create-component", "change-material",
        }
        for tool in modeling_writes:
            with self.subTest(tool=tool):
                r = run_cli("describe-tool", "--tool", tool)
                if r.returncode != 0:
                    continue
                p = json.loads(r.stdout)
                meta = p.get("tool", {})
                self.assertIn("pipeline_mode", meta)
                self.assertIn("requires_run_context", meta)
                self.assertIn("requires_check_solid", meta)

    def test_read_tools_do_not_require_check_solid(self) -> None:
        read_tools = {"list-parameters", "list-entities", "list-materials",
                       "inspect-cst-environment", "cst-session-inspect"}
        for tool in read_tools:
            with self.subTest(tool=tool):
                r = run_cli("describe-tool", "--tool", tool)
                if r.returncode != 0:
                    continue
                p = json.loads(r.stdout)
                meta = p.get("tool", {})
                if meta.get("requires_check_solid"):
                    self.assertEqual(meta.get("pipeline_mode"), "read_only")

    def test_session_tools_have_correct_risk_labels(self) -> None:
        session_risks = {
            "cst-session-open": "session",
            "cst-session-close": "session",
            "cst-session-quit": "process-control",
            "cst-session-inspect": "read",
            "cst-session-reattach": "read",
        }
        for tool, expected_risk in session_risks.items():
            with self.subTest(tool=tool):
                r = run_cli("describe-tool", "--tool", tool)
                self.assertEqual(r.returncode, 0, r.stderr)
                p = json.loads(r.stdout)
                self.assertEqual(p["tool"]["risk"], expected_risk)


class CliContractSessionTests(unittest.TestCase):
    """Session/process management tools (no CST needed for dry-runs)."""

    def test_session_inspect_no_project_safe_json(self) -> None:
        r = run_cli("cst-session-inspect")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertIn("force_kill_allowlist", p)
        self.assertIn("process_count", p)
        self.assertIn("lock_count", p)
        self.assertIn("readiness", p)
        self.assertIn(p["readiness"], {"clear", "attention_required", "blocked"})

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
            self.assertEqual(r.returncode, 0, r.stderr)
            p = json.loads(r.stdout)
            self.assertEqual(p["status"], "success")
            report = (d / "report.html").read_text(encoding="utf-8")
            self.assertIn("Parameters", report)
            self.assertIn("Entities", report)
            self.assertIn("changed", report)
            self.assertIn("added", report)
            self.assertIn("ev_brick", report)

    def test_session_quit_dry_run_safe(self) -> None:
        r = run_cli("cst-session-quit", "--dry-run", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["status"], "success")
        self.assertTrue(p["dry_run"])


if __name__ == "__main__":
    unittest.main()
