from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from . import process as process_cleanup
from . import gateway
from .errors import error_response
from .session import get_attached_project, open_project, close_project
from .utils import abs_project_path, serialize_value
from ..analysis.farfield import (
    _extract_farfield_frequency_ghz,
    _build_farfield_angle_values,
    _parse_farfield_cut_payload,
    _evaluate_farfield_cut_neighborhood_flatness,
    _group_farfield_cut_flatness,
    calculate_farfield_neighborhood_flatness,
)




def _build_farfield_cut_export_command(tree_path: str, output_file: str) -> str:
    return "\n".join(
        [
            f'SelectTreeItem "{tree_path}"',
            "With ASCIIExport",
            "    .Reset",
            f'    .FileName "{output_file}"',
            "    .Execute",
            "End With",
        ]
    )


def _normalize_farfield_plot_mode(plot_mode: str) -> dict[str, str]:
    normalized = (plot_mode or "").strip().lower()
    normalized = normalized.replace("_", " ").replace("-", " ").replace(".", " ")
    normalized = " ".join(normalized.split())

    if normalized in {"", "realized gain", "realizedgain", "rlzd gain", "rlzdgain"}:
        return {
            "result_type": "Realized Gain",
            "header_quantity": "Abs(Realized Gain)",
            "unit": "dBi",
        }
    if normalized in {"gain", "abs gain", "absgain"}:
        return {
            "result_type": "Gain",
            "header_quantity": "Abs(Gain)",
            "unit": "dBi",
        }
    if normalized in {"directivity", "abs directivity", "absdirectivity"}:
        return {
            "result_type": "Directivity",
            "header_quantity": "Abs(Directivity)",
            "unit": "dBi",
        }
    if normalized in {"efield", "e field", "electric field", "field", "abs e", "abse"}:
        raise ValueError(
            "Efield/Abs(E) is not supported for gain evidence. Use Realized Gain, Gain, or Directivity."
        )
    raise ValueError("unsupported plot_mode; use Realized Gain, Gain, or Directivity")


def _gui_open_project(fullpath: str, session_type: str = "modeler") -> dict[str, Any]:
    normalized = abs_project_path(fullpath)
    if not os.path.isfile(normalized):
        return error_response("project_file_missing", "project file does not exist", project_path=normalized)
    try:
        existing = get_attached_project(normalized)
        if existing is not None:
            return {
                "status": "success",
                "project": existing,
                "fullpath": normalized,
                "reused": True,
                "runtime_module": "cst_runtime.farfield",
            }
        result = open_project(normalized)
        if result.get("status") != "success":
            return error_response(
                "gui_open_project_failed",
                result.get("message", "failed to open project"),
                project_path=normalized,
                runtime_module="cst_runtime.farfield",
            )
        project = get_attached_project(normalized)
        if project is None:
            return error_response(
                "gui_open_project_failed",
                "project opened but not found in attached projects",
                project_path=normalized,
                runtime_module="cst_runtime.farfield",
            )
        gateway.on_session_open(normalized, session_type)
        return {
            "status": "success",
            "project": project,
            "fullpath": normalized,
            "reused": False,
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "gui_open_project_failed",
            str(exc),
            project_path=normalized,
            runtime_module="cst_runtime.farfield",
        )


def _gui_close_project(project: Any, fullpath: str, save: bool = False) -> dict[str, Any]:
    try:
        if save and hasattr(project, "save"):
            project.save()
        project.close()
        result = close_project(fullpath, save=False)
        gateway.on_session_close(fullpath)
        return result
    except Exception as exc:
        return error_response(
            "gui_close_project_failed",
            str(exc),
            project_path=fullpath,
            runtime_module="cst_runtime.farfield",
        )


def _gui_add_to_history(project: Any, command: str, history_name: str) -> dict[str, Any]:
    try:
        project.modeler.add_to_history(history_name, command)
        return {
            "status": "success",
            "message": f"command added to history: {history_name}",
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "add_to_history_failed",
            str(exc),
            runtime_module="cst_runtime.farfield",
        )


def _gui_execute_vba(project: Any, code: str) -> dict[str, Any]:
    errors: list[str] = []
    for entrypoint in ("schematic",):
        target = getattr(project, entrypoint, None)
        if target is None:
            errors.append(f"{entrypoint}: missing")
            continue
        execute = getattr(target, "execute_vba_code", None)
        if not callable(execute):
            errors.append(f"{entrypoint}: execute_vba_code unavailable")
            continue
        try:
            result = execute(code)
            return {
                "status": "success",
                "entrypoint": entrypoint,
                "result": serialize_value(result),
                "runtime_module": "cst_runtime.farfield",
            }
        except Exception as exc:
            errors.append(f"{entrypoint}: {str(exc)}")

    # CST 2026: model3d._execute_vba_code (private method)
    m3d = getattr(project, "model3d", None)
    if m3d is not None:
        execute = getattr(m3d, "_execute_vba_code", None)
        if callable(execute):
            try:
                result = execute(code)
                return {
                    "status": "success",
                    "entrypoint": "model3d._execute_vba_code",
                    "result": serialize_value(result),
                    "runtime_module": "cst_runtime.farfield",
                }
            except Exception as exc:
                errors.append(f"model3d._execute_vba_code: {str(exc)}")

    try:
        project.modeler.add_to_history("ExecuteVBA", code)
        return {
            "status": "success",
            "entrypoint": "modeler.add_to_history",
            "result": None,
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        errors.append(f"modeler.add_to_history: {str(exc)}")
    return error_response(
        "execute_vba_unavailable",
        " ; ".join(errors) if errors else "execute_vba_code unavailable",
        runtime_module="cst_runtime.farfield",
    )


def _gui_set_result_navigator_selection(
    project: Any,
    run_ids: list[int] | None,
    selection_tree_path: str = "1D Results\\S-Parameters",
) -> dict[str, Any]:
    normalized_tree_path = (selection_tree_path or "").strip()
    if not normalized_tree_path:
        return error_response("selection_tree_path_missing", "selection_tree_path cannot be empty")

    normalized_ids = sorted({int(run_id) for run_id in (run_ids or [])})
    escaped_tree_path = normalized_tree_path.replace('"', '""')
    if normalized_ids:
        selection = " ".join(str(run_id) for run_id in normalized_ids)
        request = "set selection"
    else:
        selection = ""
        request = "reset selection"
    escaped_selection = selection.replace('"', '""')
    macro = "\n".join(
        [
            "Sub Main()",
            f'    SelectTreeItem("{escaped_tree_path}")',
            "    Dim response As String",
            f'    response = ResultNavigatorRequest("{request}", "{escaped_selection}")',
            "End Sub",
        ]
    )
    result = _gui_execute_vba(project, macro)
    if result.get("status") == "success":
        result.update(
            {
                "selection_tree_path": normalized_tree_path,
                "selected_run_ids": normalized_ids,
                "request": request,
            }
        )
    return result


def _read_farfield_scalar_grid_via_calculator(
    project: Any,
    farfield_name: str,
    result_type: str,
    unit: str,
    theta_step_deg: float,
    phi_step_deg: float,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    frequency_ghz = _extract_farfield_frequency_ghz(farfield_name)
    if frequency_ghz is None:
        return error_response(
            "farfield_frequency_parse_failed",
            f"cannot parse frequency from farfield_name: {farfield_name}",
            runtime_module="cst_runtime.farfield",
        )

    theta_step = max(0.1, float(theta_step_deg))
    phi_step = max(0.1, float(phi_step_deg))
    theta_min = 0.0 if theta_min_deg is None else float(theta_min_deg)
    theta_max = 180.0 if theta_max_deg is None else float(theta_max_deg)
    phi_min = 0.0 if phi_min_deg is None else float(phi_min_deg)
    phi_max = 360.0 if phi_max_deg is None else float(phi_max_deg)
    full_theta_range = abs(theta_min - 0.0) < 1e-9 and abs(theta_max - 180.0) < 1e-9
    full_phi_range = abs(phi_min - 0.0) < 1e-9 and abs(phi_max - 360.0) < 1e-9

    try:
        theta_values = _build_farfield_angle_values(theta_min, theta_max, theta_step, upper_bound=180.0)
        phi_values = _build_farfield_angle_values(
            phi_min,
            phi_max,
            phi_step,
            upper_bound=360.0,
            exclude_upper_endpoint=full_phi_range,
        )
    except ValueError as exc:
        return error_response("invalid_angle_range", str(exc), runtime_module="cst_runtime.farfield")

    try:
        calculator = project.model3d.FarfieldCalculator
        calculator.Reset()
        calculator.SetScaleLinear(False)
        calculator.DBUnit("0")

        tree_path = f"Farfields\\{farfield_name}"
        project.model3d.SelectTreeItem(tree_path)
        for phi_value in phi_values:
            for theta_value in theta_values:
                calculator.AddListEvaluationPoint(
                    theta_value,
                    phi_value,
                    1.0,
                    "spherical",
                    "frequency",
                    frequency_ghz,
                )
        calculator.CalculateList(tree_path, "farfield Eonly")

        scalar_values = [float(value) for value in calculator.GetList(result_type, "Spherical Abs")]
        point_theta = [float(value) for value in calculator.GetList(result_type, "Point_T")]
        point_phi = [float(value) for value in calculator.GetList(result_type, "Point_P")]

        expected_points = len(theta_values) * len(phi_values)
        if len(scalar_values) != expected_points:
            return error_response(
                "farfield_point_count_mismatch",
                f"points={len(scalar_values)}, expected={expected_points}",
                runtime_module="cst_runtime.farfield",
            )

        row_width = len(theta_values)
        grid_values = [
            scalar_values[idx : idx + row_width]
            for idx in range(0, len(scalar_values), row_width)
        ]

        peak_idx = max(range(len(scalar_values)), key=lambda idx: scalar_values[idx])
        boresight_value = None
        for theta_value, phi_value, scalar_value in zip(point_theta, point_phi, scalar_values):
            if abs(theta_value) <= 1e-9 and abs(phi_value) <= 1e-9:
                boresight_value = scalar_value
                break

        return {
            "status": "success",
            "source": "FarfieldCalculator",
            "quantity": result_type,
            "unit": unit,
            "tree_path": tree_path,
            "frequency_ghz": float(frequency_ghz),
            "scope": "full_sphere" if full_theta_range and full_phi_range else "partial_range",
            "is_full_sphere": full_theta_range and full_phi_range,
            "theta_min_deg": theta_min,
            "theta_max_deg": theta_max,
            "phi_min_deg": phi_min,
            "phi_max_deg": phi_max,
            "theta_values_deg": theta_values,
            "phi_values_deg": phi_values,
            "grid_values": grid_values,
            "sample_count": len(scalar_values),
            "peak_value": float(scalar_values[peak_idx]),
            "peak_theta_deg": float(point_theta[peak_idx]),
            "peak_phi_deg": float(point_phi[peak_idx]),
            "boresight_value": None if boresight_value is None else float(boresight_value),
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "farfield_calculator_read_failed",
            f"{result_type} read failed: {str(exc)}",
            runtime_module="cst_runtime.farfield",
        )


def discover_farfield_monitors(project_path: str) -> dict[str, Any]:
    normalized_project = abs_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response(
            "project_file_missing",
            "project_path does not exist",
            project_path=normalized_project,
            runtime_module="cst_runtime.farfield",
        )
    project = None
    try:
        open_result = _gui_open_project(normalized_project)
        if open_result.get("status") != "success":
            return error_response(
                "gui_open_project_failed",
                open_result.get("message", "failed to open project"),
                project_path=normalized_project,
                runtime_module="cst_runtime.farfield",
            )
        project = open_result["project"]
        discovered: list[str] = []
        for item in project.model3d.get_tree_items():
            tree_path = str(item)
            low = tree_path.lower()
            if "farfields" in low and "\\farfield" in low and "cut" not in low:
                short = tree_path.rsplit("\\", 1)[-1]
                if short and short.strip() and short not in discovered:
                    discovered.append(short)
        return {
            "status": "success",
            "project_path": normalized_project,
            "farfield_names": discovered,
            "count": len(discovered),
            "runtime_module": "cst_runtime.farfield",
        }
    except Exception as exc:
        return error_response(
            "farfield_discovery_failed",
            str(exc),
            project_path=normalized_project,
            runtime_module="cst_runtime.farfield",
        )
    finally:
        if project is not None:
            try:
                _gui_close_project(project, normalized_project, save=False)
            except Exception:
                pass


def _make_farfield_grid_slug(farfield_name: str, quantity: str, run_id: int | None = None) -> str:
    freq = _extract_farfield_frequency_ghz(farfield_name)
    port_match = re.search(r"\[(\d+)\]", farfield_name)
    port = port_match.group(1) if port_match else "1"
    q_slug = quantity.lower().replace(" ", "_")
    freq_suffix = f"_{freq}ghz" if freq else ""
    run_suffix = f"_run{run_id}" if run_id is not None and run_id > 0 else ""
    return f"farfield{freq_suffix}_port{port}{run_suffix}_{q_slug}"


def _make_farfield_cut_slug(tree_path: str) -> str:
    freq = _extract_farfield_frequency_ghz(tree_path)
    port_match = re.search(r"Excitation \[(\d+)\]", tree_path)
    port = port_match.group(1) if port_match else "1"
    axis_match = re.search(r"\\(Phi|Theta)=([\d.]+)", tree_path)
    axis_str = ""
    if axis_match:
        axis_str = f"_{axis_match.group(1).lower()}{axis_match.group(2)}"
    freq_suffix = f"_{freq}ghz" if freq else ""
    return f"farfield{freq_suffix}_port{port}{axis_str}_cut"


def export_farfield_grid(
    project_path: str,
    farfield_name: str,
    export_dir: str,
    quantity: str = "Realized Gain",
    theta_step_deg: float = 1.0,
    phi_step_deg: float = 2.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
    run_id: int | None = None,
    fresh_session: bool = False,
    selection_tree_path: str = "1D Results\\S-Parameters",
) -> dict[str, Any]:
    normalized_project = abs_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response("project_file_missing", "project_path does not exist", project_path=normalized_project)

    rejected = gateway.guard_farfield_quantity(quantity)
    if rejected:
        return rejected

    try:
        normalized_mode = _normalize_farfield_plot_mode(quantity)
    except ValueError as exc:
        return error_response("unsupported_quantity", str(exc), runtime_module="cst_runtime.farfield")

    export_base = Path(export_dir).expanduser().resolve()
    ff_dir = export_base / "farfield"
    ff_dir.mkdir(parents=True, exist_ok=True)
    slug = _make_farfield_grid_slug(farfield_name, normalized_mode["result_type"], run_id=run_id)
    output_path = ff_dir / f"{slug}.json"
    flow_log: list[dict[str, Any]] = []

    if fresh_session:
        start_quit = process_cleanup.cleanup_cst_processes(dry_run=False, settle_seconds=0.5)
        flow_log.append({"step": "quit_before_open", "result": start_quit})
        if start_quit.get("status") != "success":
            return error_response("kill_cst_failed", "failed to clean CST processes before export", flow_log=flow_log)

    open_result = _gui_open_project(normalized_project)
    flow_log.append({"step": "open_project", "result": {k: v for k, v in open_result.items() if k not in {"project", "design_environment"}}})
    if open_result.get("status") != "success":
        return error_response("gui_open_project_failed", open_result.get("message", "failed to open project"), flow_log=flow_log)

    project = open_result["project"]
    reuse = open_result.get("reused", False)
    try:
        if run_id is not None:
            sel_result = _gui_set_result_navigator_selection(project=project, run_ids=[int(run_id)], selection_tree_path=selection_tree_path)
            flow_log.append({"step": "set_result_navigator_selection", "result": sel_result})
            if sel_result.get("status") != "success":
                import warnings
                warnings.warn(f"Result navigator selection failed (non-fatal): {sel_result.get('message')}")

        read_result = _read_farfield_scalar_grid_via_calculator(
            project=project, farfield_name=farfield_name,
            result_type=normalized_mode["result_type"], unit=normalized_mode["unit"],
            theta_step_deg=theta_step_deg, phi_step_deg=phi_step_deg,
            theta_min_deg=theta_min_deg, theta_max_deg=theta_max_deg,
            phi_min_deg=phi_min_deg, phi_max_deg=phi_max_deg,
        )
        flow_log.append({"step": "read_grid", "result": read_result})
        if read_result.get("status") != "success":
            return error_response("farfield_grid_read_failed", read_result.get("message", "grid read failed"), flow_log=flow_log)

        payload = {
            "format": "farfield_grid",
            "version": 1,
            "data": read_result["grid_values"],
            "xpositions": read_result["theta_values_deg"],
            "ypositions": read_result["phi_values_deg"],
            "title": farfield_name,
            "xlabel": "Theta [deg.]",
            "ylabel": "Phi [deg.]",
            "zlabel": f"{normalized_mode['result_type']} [{normalized_mode['unit']}]",
            "quantity": normalized_mode["result_type"],
            "unit": normalized_mode["unit"],
            "frequency_ghz": read_result["frequency_ghz"],
            "peak_value": read_result["peak_value"],
            "peak_theta_deg": read_result["peak_theta_deg"],
            "peak_phi_deg": read_result["peak_phi_deg"],
            "boresight_value": read_result["boresight_value"],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        gateway.mark_farfield_exported(normalized_project)

        return {
            "status": "success",
            "project_path": normalized_project,
            "farfield_name": farfield_name,
            "quantity": normalized_mode["result_type"],
            "unit": normalized_mode["unit"],
            "output_file": str(output_path),
            "file_size": output_path.stat().st_size,
            "frequency_ghz": read_result["frequency_ghz"],
            "peak_value": read_result["peak_value"],
            "peak_theta_deg": read_result["peak_theta_deg"],
            "peak_phi_deg": read_result["peak_phi_deg"],
            "boresight_value": read_result["boresight_value"],
            "flow_log": flow_log,
            "reused_session": reuse,
            "runtime_module": "cst_runtime.farfield",
        }
    finally:
        if run_id is not None:
            try:
                reset_result = _gui_set_result_navigator_selection(project=project, run_ids=None, selection_tree_path=selection_tree_path)
            except Exception:
                reset_result = {"status": "error", "message": "reset navigator selection failed (non-fatal)"}
            flow_log.append({"step": "reset_result_navigator_selection", "result": reset_result})
        if not reuse:
            try:
                project.close()
            except Exception:
                pass
            close_project(normalized_project, save=False, kill_processes=fresh_session)
            if fresh_session:
                end_quit = process_cleanup.cleanup_cst_processes(dry_run=False, settle_seconds=0.5)
                flow_log.append({"step": "quit_after_close", "result": end_quit})


def export_farfield_cut(
    project_path: str,
    tree_path: str,
    export_dir: str,
    fresh_session: bool = False,
) -> dict[str, Any]:
    normalized_project = abs_project_path(project_path)
    if not os.path.isfile(normalized_project):
        return error_response("project_file_missing", "project_path does not exist", project_path=normalized_project)

    normalized_tree_path = tree_path.strip()
    if not normalized_tree_path.startswith("Farfields\\Farfield Cuts\\"):
        return error_response("invalid_farfield_cut_tree_path", "tree_path must point to an existing Farfield Cut result node", tree_path=normalized_tree_path)

    export_base = Path(export_dir).expanduser().resolve()
    cuts_dir = export_base / "farfield" / "cuts"
    cuts_dir.mkdir(parents=True, exist_ok=True)
    slug = _make_farfield_cut_slug(normalized_tree_path)
    output_path = cuts_dir / f"{slug}.json"
    temp_txt = cuts_dir / f"_{slug}_tmp.txt"
    flow_log: list[dict[str, Any]] = []

    if fresh_session:
        start_quit = process_cleanup.cleanup_cst_processes(dry_run=False, settle_seconds=0.5)
        flow_log.append({"step": "quit_before_open", "result": start_quit})
        if start_quit.get("status") != "success":
            return error_response("kill_cst_failed", "failed to clean CST processes before export", flow_log=flow_log)

    open_result = _gui_open_project(normalized_project)
    flow_log.append({"step": "open_project", "result": {k: v for k, v in open_result.items() if k not in {"project", "design_environment"}}})
    if open_result.get("status") != "success":
        return error_response("gui_open_project_failed", open_result.get("message", "failed to open project"), flow_log=flow_log)

    project = open_result["project"]
    reuse = open_result.get("reused", False)
    try:
        export_result = _gui_add_to_history(project, _build_farfield_cut_export_command(normalized_tree_path, str(temp_txt)), history_name=f"ExportFarfieldCut:{normalized_tree_path}")
        flow_log.append({"step": "export_cut", "result": export_result})
        if export_result.get("status") != "success":
            return error_response("farfield_cut_export_failed", "Farfield Cut export failed", flow_log=flow_log)
        if not temp_txt.is_file() or temp_txt.stat().st_size <= 0:
            return error_response("export_file_missing", "export command succeeded but file was not created or empty", flow_log=flow_log)

        # Parse VBA-exported ASCII into structured data
        lines = temp_txt.read_text(encoding="utf-8").strip().splitlines()
        angle_vals: list[float] = []
        primary_vals: list[float] = []
        secondary_vals: list[float] = []
        axial_vals: list[float] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Theta") or line.startswith("---"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    angle_vals.append(float(parts[0]))
                    primary_vals.append(float(parts[2]))
                    if len(parts) >= 4:
                        secondary_vals.append(float(parts[3]))
                    if len(parts) >= 7:
                        axial_vals.append(float(parts[6]))
                except (ValueError, IndexError):
                    continue

        temp_txt.unlink(missing_ok=True)

        payload = {
            "format": "farfield_cut",
            "version": 1,
            "tree_path": normalized_tree_path,
            "frequency_ghz": _extract_farfield_frequency_ghz(normalized_tree_path),
            "angle_values_deg": angle_vals,
            "primary_db": primary_vals,
            "secondary_db": secondary_vals if secondary_vals else None,
            "axial_ratio_db": axial_vals if axial_vals else None,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        gateway.mark_farfield_exported(normalized_project)

        return {
            "status": "success",
            "project_path": normalized_project,
            "tree_path": normalized_tree_path,
            "output_file": str(output_path),
            "file_size": output_path.stat().st_size,
            "sample_count": len(angle_vals),
            "flow_log": flow_log,
            "reused_session": reuse,
            "runtime_module": "cst_runtime.farfield",
        }
    finally:
        temp_txt.unlink(missing_ok=True)
        if not reuse:
            try:
                project.close()
            except Exception:
                pass
            close_project(normalized_project, save=False, kill_processes=fresh_session)
            if fresh_session:
                end_quit = process_cleanup.cleanup_cst_processes(dry_run=False, settle_seconds=0.5)
                flow_log.append({"step": "quit_after_close", "result": end_quit})



