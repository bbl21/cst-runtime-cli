"""No-CST-start CLI contract checks for cst_runtime."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli-optimization"
CLI = SKILL_ROOT / "scripts" / "cst_runtime_cli.py"
PYTHON = sys.executable


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(CLI), *args],
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


class RuntimeCliContractTests(unittest.TestCase):
    def test_version_and_help_are_available(self) -> None:
        version = run_cli("--version")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("cst_runtime", version.stdout)

        help_result = run_cli("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("Exit codes:", help_result.stdout)
        self.assertIn("Examples:", help_result.stdout)

    def test_usage_errors_are_json(self) -> None:
        result = run_cli("describe-tool")
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "cli_usage_error")
        self.assertIn("available_tools", payload)

    def test_discovery_commands_return_json(self) -> None:
        for command in ("doctor", "usage-guide", "list-tools", "list-pipelines"):
            with self.subTest(command=command):
                result = run_cli(command)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "success")
                self.assertEqual(payload["adapter"], "cst_runtime_cli")

    def test_doctor_reports_skill_and_workspace_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cli("doctor", "--workspace", tmpdir)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["skill_ready"])
            self.assertFalse(payload["workspace_ready"])
            self.assertFalse(payload["production_ready"])
            self.assertEqual(Path(payload["workspace"]["workspace_root"]), Path(tmpdir))

    def test_init_workspace_and_task_create_minimal_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)
            init = run_cli("init-workspace", "--workspace", str(workspace_dir))
            self.assertEqual(init.returncode, 0, init.stderr)
            init_payload = json.loads(init.stdout)
            self.assertEqual(init_payload["status"], "success")
            self.assertTrue((workspace_dir / ".cst_mcp_runtime" / "workspace.json").exists())
            self.assertTrue((workspace_dir / "tasks").is_dir())
            self.assertTrue((workspace_dir / "refs").is_dir())
            self.assertTrue((workspace_dir / "docs").is_dir())

            source_project = workspace_dir / "missing" / "model.cst"
            task = run_cli(
                "init-task",
                "--workspace",
                str(workspace_dir),
                "--task-id",
                "task_001_demo",
                "--source-project",
                str(source_project),
                "--goal",
                "demo",
            )
            self.assertEqual(task.returncode, 0, task.stderr)
            task_payload = json.loads(task.stdout)
            self.assertEqual(task_payload["status"], "success")
            task_json = workspace_dir / "tasks" / "task_001_demo" / "task.json"
            self.assertTrue(task_json.exists())
            self.assertTrue((workspace_dir / "tasks" / "task_001_demo" / "runs").is_dir())

            prepare = run_cli(
                "prepare-run",
                "--args-json",
                json.dumps({"task_path": str(task_json.parent)}),
            )
            self.assertEqual(prepare.returncode, 1)
            prepare_payload = json.loads(prepare.stdout)
            self.assertEqual(prepare_payload["status"], "error")
            self.assertEqual(prepare_payload["error_type"], "source_project_missing")

    def test_production_command_requires_initialized_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cli(
                "prepare-run",
                "--workspace",
                tmpdir,
                "--args-json",
                json.dumps({"task_path": str(Path(tmpdir) / "tasks" / "task_001_demo")}),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error_type"], "workspace_not_initialized")
            self.assertFalse(payload["workspace"]["workspace_initialized"])

    def test_args_template_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "get_1d_result_args.json"
            result = run_cli("args-template", "--tool", "get-1d-result", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(Path(payload["output_path"]), output)
            template = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("project_path", template)
            self.assertIn("treepath", template)

    def test_session_explicit_tools_are_discoverable(self) -> None:
        expected = {
            "list-entities": ["project_path"],
            "list-subprojects": ["project_path"],
            "plot-project-result": ["project_path", "treepath"],
        }
        for tool, fields in expected.items():
            with self.subTest(tool=tool):
                result = run_cli("describe-tool", "--tool", tool)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "success")
                for field in fields:
                    self.assertIn(field, payload["args_template"])

    def test_session_manager_tools_are_discoverable(self) -> None:
        expected = {
            "cst-session-inspect": ["project_path"],
            "cst-session-open": ["project_path"],
            "cst-session-reattach": ["project_path"],
            "cst-session-close": ["project_path", "save", "wait_unlock"],
            "cst-session-quit": ["project_path", "dry_run"],
        }
        for tool, fields in expected.items():
            with self.subTest(tool=tool):
                result = run_cli("describe-tool", "--tool", tool)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "success")
                self.assertEqual(payload["tool"]["category"], "session_manager")
                for field in fields:
                    self.assertIn(field, payload["args_template"])

    def test_session_inspect_no_project_is_safe_json(self) -> None:
        result = run_cli("cst-session-inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertIn(payload["readiness"], {"clear", "attention_required", "blocked"})
        self.assertIn("force_kill_allowlist", payload)
        self.assertIn("process_count", payload)
        self.assertIn("lock_count", payload)
        self.assertIn("next_steps", payload)

    def test_session_quit_dry_run_does_not_kill_processes(self) -> None:
        result = run_cli("cst-session-quit", "--dry-run", "true")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["session_action"], "quit")
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["cleanup_result"]["cleanup_status"], "dry_run")

    def test_session_management_pipeline_is_documented(self) -> None:
        result = run_cli("describe-pipeline", "--pipeline", "cst-session-management-gate")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["recipe"]["category"], "session_manager")
        tools = [step["tool"] for step in payload["recipe"]["steps"]]
        self.assertIn("cst-session-open", tools)
        self.assertIn("cst-session-close", tools)
        self.assertIn("cst-session-quit", tools)

    def test_s11_farfield_dashboard_uses_exported_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            s11_path = tmp / "s11_run_001.json"
            farfield_path = tmp / "farfield_run_001.txt"
            output_html = tmp / "dashboard.html"
            s11_path.write_text(
                json.dumps(
                    {
                        "run_id": 1,
                        "xdata": [9.0, 10.0, 11.0],
                        "ydata": [
                            {"real": 0.3, "imag": 0.0},
                            {"real": 0.1, "imag": 0.0},
                            {"real": 0.2, "imag": 0.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            farfield_path.write_text(
                "\n".join(
                    [
                        "Theta Phi Abs(Realized Gain)[dBi]",
                        "0 0 8.0",
                        "0 180 8.1",
                        "10 0 7.5",
                        "10 180 7.6",
                    ]
                ),
                encoding="utf-8",
            )
            args = {
                "s11_file_paths": [str(s11_path)],
                "farfield_file_paths": [str(farfield_path)],
                "output_html": str(output_html),
                "page_title": "Test Dashboard",
                "farfield_run_id": 1,
            }
            result = run_cli("generate-s11-farfield-dashboard", "--args-json", json.dumps(args))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["selected_farfield_run_id"], 1)
            self.assertTrue(output_html.exists())
            self.assertIn("Test Dashboard", output_html.read_text(encoding="utf-8"))

    def test_inventory_has_required_phase1_fields(self) -> None:
        generator = run_cli("list-tools")
        self.assertEqual(generator.returncode, 0)
        inventory_path = (
            REPO_ROOT
            / "skills"
            / "cst-runtime-cli-optimization"
            / "references"
            / "mcp_cli_tool_inventory.json"
        )
        self.assertTrue(inventory_path.exists(), "Run generate_mcp_cli_inventory.py before this check.")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        required = {
            "name",
            "source",
            "category",
            "risk",
            "cli_status",
            "pipeline_mode",
            "mcp_retention",
            "validation_status",
            "known_issue",
            "replacement",
            "notes",
        }
        self.assertTrue(inventory["records"])
        for record in inventory["records"]:
            self.assertTrue(required.issubset(record), record)

    def test_inventory_classifies_implicit_session_tools_conservatively(self) -> None:
        inventory_path = (
            REPO_ROOT
            / "skills"
            / "cst-runtime-cli-optimization"
            / "references"
            / "mcp_cli_tool_inventory.json"
        )
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        records = {record["name"]: record for record in inventory["records"]}

        init_record = records["init_cst_project"]
        self.assertEqual(init_record["risk"], "write")
        self.assertEqual(init_record["pipeline_mode"], "not_pipeable_destructive")
        self.assertEqual(init_record["mcp_retention"], "mcp_preferred")
        self.assertIn("not a read-only pipe source", init_record["notes"])

        for name in ("export_e_field_data", "export_surface_current_data", "export_voltage_data"):
            with self.subTest(name=name):
                record = records[name]
                self.assertEqual(record["cli_status"], "not_migrated_needs_design")
                self.assertEqual(record["risk"], "session")
                self.assertEqual(record["pipeline_mode"], "not_pipeable_session")
                self.assertEqual(record["mcp_retention"], "mcp_preferred")
                self.assertIn("implicit active project", record["notes"])


if __name__ == "__main__":
    unittest.main()
