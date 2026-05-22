"""Test core/farfield.py: guard integration."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import assert_json_error


def test_export_farfield_grid_missing_file():
    """export_farfield_grid returns error for missing project file."""
    from cst_runtime.core.farfield import export_farfield_grid
    result = export_farfield_grid(
        project_path="/nonexistent.cst",
        farfield_name="test",
        export_dir="/tmp",
    )
    assert_json_error(result, "project_file_missing")


def test_export_farfield_grid_invalid_quantity(tmp_path):
    """T8: Abs(E) rejected."""
    dummy_cst = tmp_path / "project.cst"
    dummy_cst.write_text("")
    from cst_runtime.core.farfield import export_farfield_grid
    result = export_farfield_grid(
        project_path=str(dummy_cst),
        farfield_name="test",
        export_dir=str(tmp_path / "exports"),
        quantity="Abs(E)",
    )
    assert_json_error(result, "not_gain_evidence")


def test_export_farfield_grid_no_run_id(tmp_path):
    """T11 was here — now passes through to project open which fails."""
    dummy_cst = tmp_path / "project.cst"
    dummy_cst.write_text("")
    from cst_runtime.core.farfield import export_farfield_grid
    result = export_farfield_grid(
        project_path=str(dummy_cst),
        farfield_name="test",
        export_dir=str(tmp_path / "exports"),
        quantity="Gain",
        run_id=None,
    )
    assert result["status"] == "error"


def test_export_farfield_grid_valid_quantity_passes_gate():
    """T8: Realized Gain passes quantity guard — fails on file check."""
    from cst_runtime.core.farfield import export_farfield_grid
    result = export_farfield_grid(
        project_path="/nonexistent.cst",
        farfield_name="test",
        export_dir="/tmp",
        quantity="Realized Gain",
        run_id=1,
    )
    assert_json_error(result, "project_file_missing")


def test_export_farfield_cut_missing_file():
    """export_farfield_cut returns error for missing project file."""
    from cst_runtime.core.farfield import export_farfield_cut
    result = export_farfield_cut(
        project_path="/nonexistent.cst",
        tree_path="Farfields\\Farfield Cuts\\test",
        export_dir="/tmp",
    )
    assert_json_error(result, "project_file_missing")


def test_export_farfield_cut_invalid_tree_path(tmp_path):
    """export_farfield_cut with non-Farfield Cuts tree path returns error."""
    dummy_cst = tmp_path / "project.cst"
    dummy_cst.write_text("")
    from cst_runtime.core.farfield import export_farfield_cut
    result = export_farfield_cut(
        project_path=str(dummy_cst),
        tree_path="1D Results\\S-Parameters",
        export_dir=str(tmp_path / "exports"),
    )
    assert_json_error(result, "invalid_farfield_cut_tree_path")
