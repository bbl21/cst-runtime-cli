from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cst_runtime import project_identity


class FakeProject:
    def __init__(self, path: str) -> None:
        self._path = path

    def filename(self) -> str:
        return self._path


class FakeDesignEnvironment:
    def __init__(self, paths: list[str], active_path: str) -> None:
        self.paths = paths
        self.projects = {path: FakeProject(path) for path in paths}
        self.active_project = self.projects[active_path]
        self.requested_open_project: str | None = None

    def list_open_projects(self) -> list[str]:
        return self.paths

    def get_open_project(self, path: str) -> FakeProject:
        self.requested_open_project = path
        return self.projects[path]

    def has_active_project(self) -> bool:
        return self.active_project is not None


class ProjectIdentityTests(unittest.TestCase):
    def test_multi_project_attach_activates_expected_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = str(root / "first.cst")
            second = str(root / "second.cst")
            de = FakeDesignEnvironment(paths=[first, second], active_path=first)

            with patch("cst_runtime.project_identity._connected_design_environments", return_value=([(de, 1234)], "")):
                project, status = project_identity.attach_expected_project(second)

            self.assertIs(project, de.projects[second])
            self.assertEqual(status["status"], "success")
            self.assertTrue(status["was_activated"])
            self.assertEqual(de.requested_open_project, second)

    def test_multi_project_attach_rejects_missing_expected_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = str(root / "first.cst")
            second = str(root / "second.cst")
            missing = str(root / "missing.cst")
            de = FakeDesignEnvironment(paths=[first, second], active_path=first)

            with patch("cst_runtime.project_identity._connected_design_environments", return_value=([(de, 1234)], "")):
                project, status = project_identity.attach_expected_project(missing)

            self.assertIsNone(project)
            self.assertEqual(status["status"], "error")
            self.assertEqual(status["error_type"], "project_not_open")
            self.assertIsNone(de.requested_open_project)

    def test_attach_searches_across_design_environments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = str(root / "first.cst")
            second = str(root / "second.cst")
            de_a = FakeDesignEnvironment(paths=[first], active_path=first)
            de_b = FakeDesignEnvironment(paths=[second], active_path=second)

            with patch(
                "cst_runtime.project_identity._connected_design_environments",
                return_value=([(de_a, 1111), (de_b, 2222)], ""),
            ):
                project, status = project_identity.attach_expected_project(second)

            self.assertIs(project, de_b.projects[second])
            self.assertEqual(status["status"], "success")
            self.assertEqual(status["design_environment_pid"], 2222)


if __name__ == "__main__":
    unittest.main()
