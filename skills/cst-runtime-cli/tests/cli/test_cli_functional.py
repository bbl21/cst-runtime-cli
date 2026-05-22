"""Functional tests for CLI tools that work without CST or a workspace."""

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


class TestCliFunctional:
    """Functional tests for tools that work without CST."""

    def test_list_materials_returns_names(self) -> None:
        r = run_cli("list-materials")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert p["count"] > 0
        assert isinstance(p["material_names"], list)

    def test_install_cst_libraries_dry_run_scans(self) -> None:
        r = run_cli("install-cst-libraries", "--dry-run", "true")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert p["dry_run"]
        assert "target_path" in p
        assert "scan" in p

    def test_health_check_reports_status(self) -> None:
        r = run_cli("health-check", "--auto-fix", "true")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert "overall" in p
        assert "phases" in p
        assert "fixes_applied" in p
        assert "workspace" in p
        assert "platform" in p

    def test_health_check_without_auto_fix(self) -> None:
        r = run_cli("health-check", "--auto-fix", "false")
        assert r.returncode == 0, r.stderr
        p = json.loads(r.stdout)
        assert p["status"] == "success"
        assert "overall" in p

    def test_plot_exported_file_with_s11_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            s11 = d / "s11.json"
            s11.write_text(json.dumps({
                "run_id": 1, "xdata": [9.0, 10.0, 11.0],
                "ydata": [{"real": 0.3, "imag": 0.0}, {"real": 0.1, "imag": 0.0}, {"real": 0.2, "imag": 0.0}],
            }), encoding="utf-8")
            r = run_cli("plot-exported-file", "--file-path", str(s11), "--output-html", str(d / "preview.html"), "--page-title", "Test")
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            assert (d / "preview.html").exists()

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
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert p["status"] == "success"

    def test_record_and_update_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            run_cli("init-task", "--workspace", str(ws), "--task-id", "task_test", "--source-project", str(ws / "missing.cst"), "--goal", "test")
            task_json = ws / "tasks" / "task_test" / "task.json"
            assert task_json.exists()

            run_dir = ws / "tasks" / "task_test" / "runs" / "run_001"
            run_dir.mkdir(parents=True, exist_ok=True)

            stage = run_cli("record-stage", "--args-json", json.dumps({
                "task_path": str(task_json.parent), "run_id": "run_001",
                "stage": "test", "status": "completed", "message": "test",
            }), "--workspace", str(ws))
            assert stage.returncode == 0, stage.stderr
            sp = json.loads(stage.stdout)
            assert sp["status"] == "success"

            status = run_cli("update-status", "--args-json", json.dumps({
                "task_path": str(task_json.parent), "run_id": "run_001",
                "status": "validated", "stage": "test",
            }), "--workspace", str(ws))
            assert status.returncode == 0, status.stderr
            up = json.loads(status.stdout)
            assert up["status"] == "success"

    def test_wait_project_unlocked_no_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            fake_project = ws / "projects" / "working.cst"
            fake_project.parent.mkdir(parents=True, exist_ok=True)
            fake_project.write_text("fake", encoding="utf-8")
            r = run_cli("wait-project-unlocked", "--project-path", str(fake_project), "--timeout-seconds", "1", "--workspace", str(ws))
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert "locked" in p

    def test_infer_run_dir_no_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            run_cli("init-workspace", "--workspace", str(ws))
            fake = ws / "some" / "path" / "working.cst"
            fake.parent.mkdir(parents=True, exist_ok=True)
            fake.write_text("fake", encoding="utf-8")
            r = run_cli("infer-run-dir", "--project-path", str(fake), "--workspace", str(ws))
            assert r.returncode == 0, r.stderr
            p = json.loads(r.stdout)
            assert p["status"] == "success"
            assert p["run_dir"] is None
