# -*- coding: utf-8 -*-
"""
CST 结果查询 MCP 服务
使用 cst.results 模块读取仿真结果，无需运行中的 CST 实例

使用方法：
1. 注册为单独的 MCP 服务
2. 使用 open_project 打开项目文件
3. 使用结果查询工具读取数据
4. 使用绘图工具生成接近 CST 内部查看体验的交互式 HTML 预览
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


import cst.interface
import cst.results
from mcp.server import FastMCP

mcp = FastMCP("cst_results_interface", log_level="ERROR")

_current_project_path: str | None = None
_current_active_subproject: str | None = None
_current_allow_interactive: bool = False
# 缓存：同一文件路径+子项目+interactive 模式下复用同一 ProjectFile 实例
_project_cache: dict[tuple[str, str | None, bool], cst.results.ProjectFile] = {}

DEFAULT_PLOT_DIR = Path(__file__).resolve().parent.parent / "plot_previews"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"
FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS = 6
FARFIELD_EXPORT_HARD_MAX_ATTEMPTS = 12


def save_project_context(
    fullpath: str,
    allow_interactive: bool = False,
    subproject_treepath: str | None = None,
):
    """保存当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    _current_project_path = os.path.abspath(fullpath)
    _current_active_subproject = subproject_treepath
    _current_allow_interactive = allow_interactive


def get_project_context():
    """读取当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    if _current_project_path:
        return {
            "fullpath": _current_project_path,
            "active_subproject": _current_active_subproject,
            "allow_interactive": _current_allow_interactive,
        }
    return None


def clear_project_context():
    """清除当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    _current_project_path = None
    _current_active_subproject = None
    _current_allow_interactive = False


def _serialize_value(value: Any):
    """将 cst.results 返回值转换为可 JSON 序列化的数据"""
    if isinstance(value, complex):
        return {
            "real": value.real,
            "imag": value.imag,
            "complex_str": str(value),
        }
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if hasattr(value, "tolist"):
        return _serialize_value(value.tolist())
    return value


def _load_project():
    """按当前上下文重新加载 ProjectFile / 子项目

    关键：cst.interface.Project（modeler）和 cst.results.ProjectFile（results）
    是不同的 COM 对象，不能混用。必须各自独立创建。
    但多次调用 _load_project 加载同一文件时，缓存同一 ProjectFile 实例，
    复用会话，避免重复创建。
    """
    context = get_project_context()
    if not context:
        raise RuntimeError("当前没有活动的项目，请先调用 open_project")

    cache_key = (
        context["fullpath"],
        context.get("active_subproject"),
        context["allow_interactive"],
    )
    cached = _project_cache.get(cache_key)
    if cached is not None:
        return cached, context

    project = cst.results.ProjectFile(
        context["fullpath"],
        allow_interactive=context["allow_interactive"],
    )

    active_subproject = context.get("active_subproject")
    if active_subproject:
        project = project.load_subproject(active_subproject)

    _project_cache[cache_key] = project
    return project, context


def _get_result_module(project, module_type: str):
    module_key = (module_type or "3d").lower()
    if module_key == "schematic":
        return project.get_schematic(), "schematic"
    return project.get_3d(), "3d"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _derive_farfield_cut_tree_path(
    farfield_name: str, cut_axis: str = "Phi", cut_angle: str = "0"
) -> str | None:
    match = re.fullmatch(r"farfield \(f=(.+?)\) \[(\d+)\]", farfield_name.strip())
    if not match:
        return None
    frequency, port = match.groups()
    normalized_axis = cut_axis.strip().capitalize()
    if normalized_axis not in {"Phi", "Theta"}:
        return None
    return (
        f"Farfields\\Farfield Cuts\\Excitation [{port}]\\"
        f"{normalized_axis}={cut_angle}\\farfield (f={frequency})"
    )


def _build_farfield_cut_export_command(tree_path: str, output_file: str):
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


def _inspect_farfield_ascii_grid(file_path: str) -> dict[str, Any]:
    theta_values: set[float] = set()
    phi_values: set[float] = set()
    row_count = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                theta = float(parts[0])
                phi = float(parts[1])
            except Exception:
                continue
            theta_values.add(theta)
            phi_values.add(phi)
            row_count += 1
    return {
        "row_count": row_count,
        "theta_count": len(theta_values),
        "phi_count": len(phi_values),
        "theta_min": min(theta_values) if theta_values else None,
        "theta_max": max(theta_values) if theta_values else None,
        "phi_min": min(phi_values) if phi_values else None,
        "phi_max": max(phi_values) if phi_values else None,
    }


def _extract_farfield_frequency_ghz(farfield_name: str) -> float | None:
    match = re.search(r"f\s*=\s*([0-9]+(?:\.[0-9]+)?)", farfield_name)
    if not match:
        return None
    return float(match.group(1))


def _phase_deg_from_components(real: float, imag: float) -> float:
    return math.degrees(math.atan2(imag, real))


def _build_farfield_angle_values(
    minimum: float,
    maximum: float,
    step: float,
    *,
    upper_bound: float,
    exclude_upper_endpoint: bool = False,
) -> list[float]:
    if step <= 0:
        raise ValueError("angle step must be positive")
    if minimum < 0 or maximum > upper_bound or minimum > maximum:
        raise ValueError(
            f"invalid angle range: min={minimum}, max={maximum}, upper_bound={upper_bound}"
        )

    values: list[float] = []
    value = minimum
    if exclude_upper_endpoint:
        while value < maximum - 1e-9:
            values.append(round(value, 10))
            value += step
    else:
        while value <= maximum + 1e-9:
            values.append(round(value, 10))
            value += step
    if not values:
        raise ValueError(
            f"angle range produced no sample points: min={minimum}, max={maximum}, step={step}"
        )
    return values


def _com_best_effort_set(obj, name: str, value) -> bool:
    """Best-effort setter for CST COM objects.

    CST exposes some members as methods in VBA (e.g. `FarfieldPlot.Step "5"`)
    but they may appear as properties or callables in Python COM. We try both
    calling and assignment and never raise.
    """
    try:
        attr = getattr(obj, name)
        if callable(attr):
            attr(value)
        else:
            setattr(obj, name, value)
        return True
    except Exception:
        try:
            setattr(obj, name, value)
            return True
        except Exception:
            return False


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
    if normalized in {
        "efield",
        "e field",
        "electric field",
        "field",
        "abs e",
        "abse",
    }:
        raise ValueError(
            "电场强度读取/导出已移除。真实增益请改用 "
            "read_realized_gain_grid_fresh_session；完整方向图导出仅支持 "
            "Realized Gain/Gain/Directivity。"
        )

    raise ValueError(
        "不支持的 plot_mode。当前仅支持 Realized Gain、Gain、Directivity；"
        "不再支持 Efield/Abs(E)。"
    )


def _read_farfield_scalar_grid_via_calculator(
    project,
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
        return {
            "status": "error",
            "message": f"无法从 farfield_name 解析频率: {farfield_name}",
        }

    theta_step = max(0.1, float(theta_step_deg))
    phi_step = max(0.1, float(phi_step_deg))
    theta_min = 0.0 if theta_min_deg is None else float(theta_min_deg)
    theta_max = 180.0 if theta_max_deg is None else float(theta_max_deg)
    phi_min = 0.0 if phi_min_deg is None else float(phi_min_deg)
    phi_max = 360.0 if phi_max_deg is None else float(phi_max_deg)
    full_theta_range = abs(theta_min - 0.0) < 1e-9 and abs(theta_max - 180.0) < 1e-9
    full_phi_range = abs(phi_min - 0.0) < 1e-9 and abs(phi_max - 360.0) < 1e-9

    try:
        theta_values = _build_farfield_angle_values(
            theta_min, theta_max, theta_step, upper_bound=180.0
        )
        phi_values = _build_farfield_angle_values(
            phi_min,
            phi_max,
            phi_step,
            upper_bound=360.0,
            exclude_upper_endpoint=full_phi_range,
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}

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

        scalar_values = [
            float(value) for value in calculator.GetList(result_type, "Spherical Abs")
        ]
        point_theta = [
            float(value) for value in calculator.GetList(result_type, "Point_T")
        ]
        point_phi = [
            float(value) for value in calculator.GetList(result_type, "Point_P")
        ]

        expected_points = len(theta_values) * len(phi_values)
        if len(scalar_values) != expected_points:
            return {
                "status": "error",
                "message": (
                    "FarfieldCalculator 返回的数据点数量与角度网格不一致: "
                    f"points={len(scalar_values)}, expected={expected_points}"
                ),
            }

        row_width = len(theta_values)
        grid_values = [
            scalar_values[idx : idx + row_width]
            for idx in range(0, len(scalar_values), row_width)
        ]

        peak_idx = max(range(len(scalar_values)), key=lambda idx: scalar_values[idx])
        peak_value = scalar_values[peak_idx]
        peak_theta_deg = point_theta[peak_idx]
        peak_phi_deg = point_phi[peak_idx]

        boresight_value = None
        for theta_value, phi_value, scalar_value in zip(
            point_theta, point_phi, scalar_values
        ):
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
            "peak_value": float(peak_value),
            "peak_theta_deg": float(peak_theta_deg),
            "peak_phi_deg": float(peak_phi_deg),
            "boresight_value": None if boresight_value is None else float(boresight_value),
        }
    except Exception as e:
        return {"status": "error", "message": f"{result_type} 读取失败: {str(e)}"}


def _write_farfield_scalar_ascii(
    output_file: str,
    *,
    header_quantity: str,
    unit: str,
    theta_values: list[float],
    phi_values: list[float],
    grid_values: list[list[float]],
):
    with open(output_file, "w", encoding="utf-8", newline="") as handle:
        handle.write(
            f"Theta [deg.]  Phi   [deg.]  {header_quantity}[{unit}]  "
            "Aux1[-]  Aux2[-]  Aux3[-]  Aux4[-]  Aux5[-]\n"
        )
        handle.write(
            "------------------------------------------------------------------------------------------------------------------------------------------------------\n"
        )
        for phi_idx, phi_value in enumerate(phi_values):
            for theta_idx, theta_value in enumerate(theta_values):
                scalar_value = float(grid_values[phi_idx][theta_idx])
                handle.write(
                    f"{theta_value:.3f} {phi_value:.3f} "
                    f"{scalar_value:.6E} 0.000000E+00 0.000000E+00 "
                    "0.000000E+00 0.000000E+00 0.000000E+00\n"
                )


def _export_farfield_grid_direct_com(
    project,
    farfield_name: str,
    output_file: str,
    theta_step_deg: float,
    phi_step_deg: float,
    plot_mode: str,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    try:
        normalized_mode = _normalize_farfield_plot_mode(plot_mode)
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
            "alternative_tool": "read_realized_gain_grid_fresh_session",
        }

    read_result = _read_farfield_scalar_grid_via_calculator(
        project=project,
        farfield_name=farfield_name,
        result_type=normalized_mode["result_type"],
        unit=normalized_mode["unit"],
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
    )
    if read_result.get("status") != "success":
        return read_result

    _write_farfield_scalar_ascii(
        output_file,
        header_quantity=normalized_mode["header_quantity"],
        unit=normalized_mode["unit"],
        theta_values=read_result["theta_values_deg"],
        phi_values=read_result["phi_values_deg"],
        grid_values=read_result["grid_values"],
    )

    return {
        "status": "success",
        "message": f"真实 farfield 标量网格已导出: {output_file}",
        "tree_path": read_result["tree_path"],
        "frequency_ghz": read_result["frequency_ghz"],
        "requested_plot_mode": plot_mode,
        "exported_quantity": read_result["quantity"],
        "unit": read_result["unit"],
        "scope": read_result["scope"],
        "is_full_sphere": read_result["is_full_sphere"],
        "theta_min_deg": read_result["theta_min_deg"],
        "theta_max_deg": read_result["theta_max_deg"],
        "phi_min_deg": read_result["phi_min_deg"],
        "phi_max_deg": read_result["phi_max_deg"],
        "theta_count": len(read_result["theta_values_deg"]),
        "phi_count": len(read_result["phi_values_deg"]),
        "row_count": read_result["sample_count"],
        "peak_value": read_result["peak_value"],
        "peak_theta_deg": read_result["peak_theta_deg"],
        "peak_phi_deg": read_result["peak_phi_deg"],
        "boresight_value": read_result["boresight_value"],
    }

    frequency_ghz = _extract_farfield_frequency_ghz(farfield_name)
    if frequency_ghz is None:
        return {
            "status": "error",
            "message": f"无法从 farfield_name 解析频率: {farfield_name}",
        }
    # CST COM API expects frequency in Hz for list evaluation points.
    frequency_hz = float(frequency_ghz) * 1e9

    theta_step = max(0.1, float(theta_step_deg))
    phi_step = max(0.1, float(phi_step_deg))
    theta_min = 0.0 if theta_min_deg is None else float(theta_min_deg)
    theta_max = 180.0 if theta_max_deg is None else float(theta_max_deg)
    phi_min = 0.0 if phi_min_deg is None else float(phi_min_deg)
    phi_max = 360.0 if phi_max_deg is None else float(phi_max_deg)
    full_theta_range = abs(theta_min - 0.0) < 1e-9 and abs(theta_max - 180.0) < 1e-9
    full_phi_range = abs(phi_min - 0.0) < 1e-9 and abs(phi_max - 360.0) < 1e-9

    try:
        theta_values = _build_farfield_angle_values(
            theta_min, theta_max, theta_step, upper_bound=180.0
        )
        # Exclude 360 degrees only for the full 0..360 sweep to avoid duplicating phi=0.
        phi_values = _build_farfield_angle_values(
            phi_min,
            phi_max,
            phi_step,
            upper_bound=360.0,
            exclude_upper_endpoint=full_phi_range,
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    is_full_sphere = full_theta_range and full_phi_range

    try:
        model = project.model3d
        tree_path = f"Farfields\\{farfield_name}"
        model.SelectTreeItem(tree_path)
        farfield_plot = model.FarfieldPlot
        farfield_plot.Reset()
        # We always export th/ph complex E-field components via GetListItem("th_re"/"th_im"/...).
        # Other plot modes like "Gain" do not provide those component keys reliably.
        farfield_plot.SetPlotMode("efield")
        farfield_plot.SetScaleLinear("True")
        # Some projects cannot CalculateList unless CST generated the 3D farfield plot data
        # at least once in the session (it writes `farfield (f=xx)2D_*.ffp` into Result/).
        # This mirrors the historically working VBA sequence: set plottype/step -> SelectTreeItem -> Plot.
        try:
            _com_best_effort_set(farfield_plot, "Plottype", "3d")
            _com_best_effort_set(farfield_plot, "Step", str(theta_step_deg))
            _com_best_effort_set(farfield_plot, "SetColorByValue", "True")
            _com_best_effort_set(farfield_plot, "SetTheta360", "False")
            _com_best_effort_set(farfield_plot, "DBUnit", "0")
            _com_best_effort_set(farfield_plot, "Distance", "1")
            model.SelectTreeItem(tree_path)
            if hasattr(farfield_plot, "Plot"):
                farfield_plot.Plot()
        except Exception:
            pass
        # Direct COM evaluation must bind frequency per point; VBA AddListItem
        # otherwise falls back to HEX-mesh farfield approximation in CST 2026.
        farfield_plot.UseFarfieldApproximation("False")
        for phi_value in phi_values:
            for theta_value in theta_values:
                farfield_plot.AddListEvaluationPoint(
                    theta_value,
                    phi_value,
                    1,
                    "spherical",
                    "frequency",
                    frequency_hz,
                )
        farfield_plot.CalculateList(farfield_name)

        with open(output_file, "w", encoding="utf-8", newline="") as handle:
            handle.write(
                "Theta [deg.]  Phi   [deg.]  Abs(E   )[V/m   ]   "
                "Abs(Theta)[V/m   ]  Phase(Theta)[deg.]  "
                "Abs(Phi  )[V/m   ]  Phase(Phi  )[deg.]  Ax.Ratio[      ]\n"
            )
            handle.write(
                "------------------------------------------------------------------------------------------------------------------------------------------------------\n"
            )
            index = 0
            for phi_value in phi_values:
                for theta_value in theta_values:
                    theta_real = float(farfield_plot.GetListItem(index, "th_re"))
                    theta_imag = float(farfield_plot.GetListItem(index, "th_im"))
                    phi_real = float(farfield_plot.GetListItem(index, "ph_re"))
                    phi_imag = float(farfield_plot.GetListItem(index, "ph_im"))
                    abs_theta = math.hypot(theta_real, theta_imag)
                    abs_phi = math.hypot(phi_real, phi_imag)
                    abs_e = math.hypot(abs_theta, abs_phi)
                    handle.write(
                        f"{theta_value:.3f} {phi_value:.3f} "
                        f"{abs_e:.6E} {abs_theta:.6E} {_phase_deg_from_components(theta_real, theta_imag):.3f} "
                        f"{abs_phi:.6E} {_phase_deg_from_components(phi_real, phi_imag):.3f} 0.000000E+00\n"
                    )
                    index += 1
        return {
            "status": "success",
            "message": f"完整 farfield 网格已导出: {output_file}",
            "tree_path": tree_path,
            "frequency_ghz": frequency_ghz,
            "requested_plot_mode": plot_mode,
            "exported_quantity": "Efield_components",
            "scope": "full_sphere" if is_full_sphere else "partial_range",
            "is_full_sphere": is_full_sphere,
            "theta_min_deg": theta_min,
            "theta_max_deg": theta_max,
            "phi_min_deg": phi_min,
            "phi_max_deg": phi_max,
            "theta_count": len(theta_values),
            "phi_count": len(phi_values),
            "row_count": len(theta_values) * len(phi_values),
        }
    except Exception as e:
        return {"status": "error", "message": f"完整 farfield 网格导出失败: {str(e)}"}


def _cleanup_temp_export_file(file_path: str):
    try:
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
    except Exception:
        pass


def _kill_cst_processes():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "tools" / "kill_cst.ps1"
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "message": (
                    f"kill_cst.ps1 failed: exit_code={result.returncode}, "
                    f"stdout={result.stdout.strip()}, stderr={result.stderr.strip()}"
                ),
            }
        return {
            "status": "success",
            "message": result.stdout.strip() or "CST processes killed",
        }
    except Exception as e:
        return {"status": "error", "message": f"kill_cst.ps1 failed: {str(e)}"}


def _close_results_context_if_matches(project_path: str):
    context = get_project_context()
    if not context:
        return None
    current_path = os.path.abspath(context["fullpath"])
    if current_path != os.path.abspath(project_path):
        return None
    return close_project()


def _gui_open_project(fullpath: str):
    if os.path.isdir(fullpath):
        return {"status": "error", "message": f"路径是文件夹，不是项目文件: {fullpath}"}
    normalized_path = fullpath
    if not normalized_path.endswith(".cst"):
        cst_path = normalized_path + ".cst"
        if os.path.exists(cst_path):
            normalized_path = cst_path
        else:
            return {"status": "error", "message": f"项目文件不存在: {fullpath}"}
    if not os.path.exists(normalized_path) or not os.path.isfile(normalized_path):
        return {"status": "error", "message": f"项目文件不存在: {normalized_path}"}
    try:
        de = cst.interface.DesignEnvironment()
        project = de.open_project(normalized_path)
        return {
            "status": "success",
            "project": project,
            "design_environment": de,
            "fullpath": normalized_path,
        }
    except Exception as e:
        return {"status": "error", "message": f"打开 GUI 项目失败: {str(e)}"}


def _gui_close_project(project, fullpath: str, save: bool = False):
    try:
        if save:
            project.save()
        project.close()
        return {"status": "success", "message": f"项目已关闭: {fullpath}"}
    except Exception as e:
        return {"status": "error", "message": f"关闭 GUI 项目失败: {str(e)}"}


def _gui_add_to_history(project, command: str, history_name: str):
    try:
        project.modeler.add_to_history(history_name, command)
        return {"status": "success", "message": f"命令已添加到历史记录: {history_name}"}
    except Exception as e:
        return {"status": "error", "message": f"添加命令失败: {str(e)}"}


def _gui_execute_vba(project, code: str):
    errors: list[str] = []
    for entrypoint in ("schematic", "modeler"):
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
                "result": _serialize_value(result),
            }
        except Exception as e:
            errors.append(f"{entrypoint}: {str(e)}")
    return {
        "status": "error",
        "message": " ; ".join(errors) if errors else "execute_vba_code unavailable",
    }


def _gui_set_result_navigator_selection(
    project,
    run_ids: list[int] | None,
    selection_tree_path: str = "1D Results\\S-Parameters",
):
    normalized_tree_path = (selection_tree_path or "").strip()
    if not normalized_tree_path:
        return {"status": "error", "message": "selection_tree_path cannot be empty"}

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


def _read_realized_gain_grid_via_calculator(
    project,
    farfield_name: str,
    theta_step_deg: float,
    phi_step_deg: float,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
) -> dict[str, Any]:
    base_result = _read_farfield_scalar_grid_via_calculator(
        project=project,
        farfield_name=farfield_name,
        result_type="Realized Gain",
        unit="dBi",
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
    )
    if base_result.get("status") != "success":
        return base_result

    return {
        **base_result,
        "grid_db": base_result["grid_values"],
        "peak_realized_gain_dbi": base_result["peak_value"],
        "boresight_realized_gain_dbi": base_result["boresight_value"],
    }

    frequency_ghz = _extract_farfield_frequency_ghz(farfield_name)
    if frequency_ghz is None:
        return {
            "status": "error",
            "message": f"无法从 farfield_name 解析频率: {farfield_name}",
        }

    theta_step = max(0.1, float(theta_step_deg))
    phi_step = max(0.1, float(phi_step_deg))
    theta_min = 0.0 if theta_min_deg is None else float(theta_min_deg)
    theta_max = 180.0 if theta_max_deg is None else float(theta_max_deg)
    phi_min = 0.0 if phi_min_deg is None else float(phi_min_deg)
    phi_max = 360.0 if phi_max_deg is None else float(phi_max_deg)
    full_phi_range = abs(phi_min - 0.0) < 1e-9 and abs(phi_max - 360.0) < 1e-9

    try:
        theta_values = _build_farfield_angle_values(
            theta_min, theta_max, theta_step, upper_bound=180.0
        )
        phi_values = _build_farfield_angle_values(
            phi_min,
            phi_max,
            phi_step,
            upper_bound=360.0,
            exclude_upper_endpoint=full_phi_range,
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    try:
        calculator = project.model3d.FarfieldCalculator
        calculator.Reset()
        # Keep logarithmic gain scaling so returned values map to dBi-like CST gain readout.
        calculator.SetScaleLinear(False)
        calculator.DBUnit("0")

        tree_path = f"Farfields\\{farfield_name}"
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

        realized_gain_db = [
            float(value)
            for value in calculator.GetList("Realized Gain", "Spherical Abs")
        ]
        point_theta = [
            float(value) for value in calculator.GetList("Realized Gain", "Point_T")
        ]
        point_phi = [
            float(value) for value in calculator.GetList("Realized Gain", "Point_P")
        ]

        row_width = len(theta_values)
        grid_db = [
            realized_gain_db[idx : idx + row_width]
            for idx in range(0, len(realized_gain_db), row_width)
        ]
        if len(grid_db) != len(phi_values):
            return {
                "status": "error",
                "message": (
                    "FarfieldCalculator 返回的数据点数量与角度网格不一致: "
                    f"points={len(realized_gain_db)}, expected={len(theta_values) * len(phi_values)}"
                ),
            }

        peak_idx = max(range(len(realized_gain_db)), key=lambda idx: realized_gain_db[idx])
        peak_gain_db = realized_gain_db[peak_idx]
        peak_theta_deg = point_theta[peak_idx]
        peak_phi_deg = point_phi[peak_idx]

        boresight_gain_db = None
        for theta_value, phi_value, gain_value in zip(
            point_theta, point_phi, realized_gain_db
        ):
            if abs(theta_value) <= 1e-9 and abs(phi_value) <= 1e-9:
                boresight_gain_db = gain_value
                break

        return {
            "status": "success",
            "source": "FarfieldCalculator",
            "quantity": "Realized Gain",
            "unit": "dBi",
            "tree_path": tree_path,
            "frequency_ghz": float(frequency_ghz),
            "theta_values_deg": theta_values,
            "phi_values_deg": phi_values,
            "grid_db": grid_db,
            "sample_count": len(realized_gain_db),
            "peak_realized_gain_dbi": float(peak_gain_db),
            "peak_theta_deg": float(peak_theta_deg),
            "peak_phi_deg": float(peak_phi_deg),
            "boresight_realized_gain_dbi": (
                None if boresight_gain_db is None else float(boresight_gain_db)
            ),
        }
    except Exception as e:
        return {"status": "error", "message": f"Realized Gain 读取失败: {str(e)}"}


def _default_plot_dir() -> Path:
    context = get_project_context()
    if context and context.get("fullpath"):
        project_path = Path(context["fullpath"]).resolve()
        parents = list(project_path.parents)
        for idx, parent in enumerate(parents):
            if parent.name == "runs" and idx > 0:
                run_dir = parents[idx - 1]
                exports_dir = run_dir / "exports"
                exports_dir.mkdir(parents=True, exist_ok=True)
                return exports_dir
            if parent.name == "projects":
                run_dir = parent.parent
                if run_dir.name.startswith("run_") and run_dir.parent.name == "runs":
                    exports_dir = run_dir / "exports"
                    exports_dir.mkdir(parents=True, exist_ok=True)
                    return exports_dir

    DEFAULT_PLOT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_PLOT_DIR


def _ensure_plot_output_path(output_html: str = "", prefix: str = "plot") -> Path:
    if output_html:
        target = Path(output_html).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = (_default_plot_dir() / f"{prefix}_{timestamp}.html").resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _is_complex_payload(value: Any) -> bool:
    return isinstance(value, dict) and "real" in value and "imag" in value


def _complex_components(value: Any) -> tuple[float, float]:
    if _is_complex_payload(value):
        return float(value.get("real", 0.0)), float(value.get("imag", 0.0))
    if isinstance(value, complex):
        return float(value.real), float(value.imag)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), 0.0
    return 0.0, 0.0


def _to_scalar(value: Any) -> float:
    if _is_complex_payload(value):
        real, imag = _complex_components(value)
        return math.sqrt(real * real + imag * imag)
    if isinstance(value, complex):
        return abs(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _phase_deg(value: Any) -> float:
    real, imag = _complex_components(value)
    return math.degrees(math.atan2(imag, real))


def _safe_log_db(value: float) -> float | None:
    if value <= 0:
        return None
    return 20.0 * math.log10(value)


def _first_numeric_column(rows: list[list[str]], col_index: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        if col_index >= len(row):
            continue
        cell = row[col_index].strip()
        if cell == "":
            continue
        values.append(float(cell))
    return values


def _infer_xy_from_rows(rows: list[list[str]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("文件没有可解析的数据行")

    numeric_rows: list[list[float]] = []
    for row in rows:
        parsed_row: list[float] = []
        for cell in row:
            parsed_row.append(float(cell.strip()))
        numeric_rows.append(parsed_row)

    widths = {len(row) for row in numeric_rows}
    if len(widths) != 1:
        raise ValueError("文件列数不一致，无法自动绘图")

    width = widths.pop()
    if width == 1:
        return {
            "kind": "1d",
            "xdata": list(range(1, len(numeric_rows) + 1)),
            "ydata": [row[0] for row in numeric_rows],
            "title": "单列数值数据",
            "xlabel": "Index",
            "ylabel": "Value",
        }
    if width == 2:
        return {
            "kind": "1d",
            "xdata": [row[0] for row in numeric_rows],
            "ydata": [row[1] for row in numeric_rows],
            "title": "二维表格曲线",
            "xlabel": "X",
            "ylabel": "Y",
        }
    return {
        "kind": "2d",
        "xpositions": list(range(width)),
        "ypositions": list(range(len(numeric_rows))),
        "data": numeric_rows,
        "title": "矩阵热图",
        "xlabel": "Column",
        "ylabel": "Row",
        "dataunit": "",
    }


def _try_parse_cst_farfield_ascii(
    text: str, filename: str = ""
) -> dict[str, Any] | None:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    header_index = -1
    source_quantity = "Abs(E)"
    data_unit = "V/m"
    component_mode = "vector_efield"
    for idx, line in enumerate(lines[:10]):
        normalized = line.lower().replace(" ", "")
        if (
            "theta[deg.]" in normalized
            and "phi[deg.]" in normalized
            and (
                "abs(e" in normalized
                or "abs(gain)" in normalized
                or "abs(realizedgain)" in normalized
                or "abs(directivity)" in normalized
            )
        ):
            header_index = idx
            if "abs(realizedgain)" in normalized:
                source_quantity = "Abs(Realized Gain)"
                data_unit = "dBi"
                component_mode = "scalar"
            elif "abs(directivity)" in normalized:
                source_quantity = "Abs(Directivity)"
                data_unit = "dBi"
                component_mode = "scalar"
            elif "abs(gain)" in normalized:
                source_quantity = "Abs(Gain)"
                data_unit = "dBi"
                component_mode = "scalar"
            break

    if header_index < 0:
        return None

    data_rows: list[list[float]] = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= {"-", "="}:
            continue
        parts = stripped.split()
        if len(parts) < 8:
            continue
        try:
            data_rows.append([float(parts[i]) for i in range(8)])
        except Exception:
            continue

    if not data_rows:
        raise ValueError("识别到 CST farfield ASCII 表头，但未解析出有效数据行")

    theta_values = sorted({row[0] for row in data_rows})
    phi_values = sorted({row[1] for row in data_rows})
    theta_index = {value: idx for idx, value in enumerate(theta_values)}
    phi_index = {value: idx for idx, value in enumerate(phi_values)}

    abs_e_matrix = [[None for _ in theta_values] for _ in phi_values]
    abs_theta_matrix = [[None for _ in theta_values] for _ in phi_values]
    phase_theta_matrix = [[None for _ in theta_values] for _ in phi_values]
    abs_phi_matrix = [[None for _ in theta_values] for _ in phi_values]
    phase_phi_matrix = [[None for _ in theta_values] for _ in phi_values]
    ax_ratio_matrix = [[None for _ in theta_values] for _ in phi_values]

    for row in data_rows:
        theta_idx = theta_index[row[0]]
        phi_idx = phi_index[row[1]]
        abs_e_matrix[phi_idx][theta_idx] = row[2]
        abs_theta_matrix[phi_idx][theta_idx] = row[3]
        phase_theta_matrix[phi_idx][theta_idx] = row[4]
        abs_phi_matrix[phi_idx][theta_idx] = row[5]
        phase_phi_matrix[phi_idx][theta_idx] = row[6]
        ax_ratio_matrix[phi_idx][theta_idx] = row[7]

    # 缝合：若 Phi 未到 360°，在末尾追加一行等于 Phi=0° 的数据，闭合极坐标圆
    if phi_values and phi_values[-1] < 360.0 - 1e-6:
        phi_values.append(360.0)
        phi_0_row = abs_e_matrix[0][:]
        abs_e_matrix.append(phi_0_row)
        abs_theta_matrix.append(abs_theta_matrix[0][:])
        phase_theta_matrix.append(phase_theta_matrix[0][:])
        abs_phi_matrix.append(abs_phi_matrix[0][:])
        phase_phi_matrix.append(phase_phi_matrix[0][:])
        ax_ratio_matrix.append(ax_ratio_matrix[0][:])

    def _fill_none(matrix: list[list[float | None]]) -> list[list[float]]:
        return [
            [0.0 if cell is None else float(cell) for cell in row] for row in matrix
        ]

    return {
        "kind": "2d",
        "title": f"CST Farfield ASCII - {filename or source_quantity}",
        "xlabel": "Theta [deg.]",
        "ylabel": "Phi [deg.]",
        "dataunit": data_unit,
        "xpositions": theta_values,
        "ypositions": phi_values,
        "data": _fill_none(abs_e_matrix),
        "meta": {
            "source_format": "cst_farfield_ascii",
            "source_quantity": source_quantity,
            "component_mode": component_mode,
            "point_count": len(data_rows),
            "theta_count": len(theta_values),
            "phi_count": len(phi_values),
            "components": {
                "abs_theta": _fill_none(abs_theta_matrix),
                "phase_theta": _fill_none(phase_theta_matrix),
                "abs_phi": _fill_none(abs_phi_matrix),
                "phase_phi": _fill_none(phase_phi_matrix),
                "ax_ratio": _fill_none(ax_ratio_matrix),
            },
        },
    }


def _load_exported_payload(file_path: str) -> dict[str, Any]:
    target = Path(file_path)
    if not target.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = target.suffix.lower()
    if suffix == ".json":
        with target.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError(
                "JSON 文件内容必须是对象，且应包含 xdata/ydata 或二维 data"
            )
        return payload

    text = target.read_text(encoding="utf-8-sig")
    farfield_payload = _try_parse_cst_farfield_ascii(text, target.name)
    if farfield_payload is not None:
        farfield_payload.setdefault("meta", {})["source_file"] = str(target.resolve())
        return farfield_payload

    with target.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t; ")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not rows:
        raise ValueError("文件为空或没有可解析内容")

    try:
        return _infer_xy_from_rows(rows)
    except Exception:
        try:
            return _infer_xy_from_rows(rows[1:])
        except Exception as e:
            raise ValueError(f"无法自动解析导出文件为可绘图数据: {str(e)}")


def _parse_frequency_from_name(name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*GHz", name, flags=re.I)
    if match:
        return float(match.group(1))
    match = re.search(r"f\s*=\s*(\d+(?:\.\d+)?)", name, flags=re.I)
    if match:
        return float(match.group(1))
    return None


def _load_farfield_payloads(file_paths: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file_path in file_paths:
        payload = _load_exported_payload(file_path)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        source_format = (meta.get("source_format") or "").strip().lower()
        if source_format != "cst_farfield_ascii":
            raise ValueError(f"仅支持 CST farfield ASCII 文件: {file_path}")

        source_file = meta.get("source_file") or str(Path(file_path).resolve())
        freq = _parse_frequency_from_name(Path(source_file).name)
        if freq is None:
            freq = _parse_frequency_from_name(str(Path(source_file).parent))

        matrix = _normalize_matrix(payload.get("data"))
        xpositions = payload.get("xpositions") or []
        ypositions = payload.get("ypositions") or []
        if not matrix or not xpositions or not ypositions:
            raise ValueError(f"远场文件缺少有效矩阵或坐标: {file_path}")

        max_value = max(cell for row in matrix for cell in row)
        norm_matrix = [
            [(cell / max_value) if max_value > 0 else 0.0 for cell in row]
            for row in matrix
        ]
        db_matrix = [
            [safe if (safe := _safe_log_db(v)) is not None else -120.0 for v in row]
            for row in norm_matrix
        ]

        def _cut_for_phi(target_phi: float):
            idx = min(
                range(len(ypositions)),
                key=lambda i: abs(float(ypositions[i]) - target_phi),
            )
            return {
                "phi": float(ypositions[idx]),
                "theta": [float(v) for v in xpositions],
                "gain_db": [float(v) for v in db_matrix[idx]],
            }

        items.append(
            {
                "label": f"{freq:g} GHz"
                if freq is not None
                else Path(source_file).stem,
                "frequency": freq,
                "file": str(Path(source_file)),
                "points": int(
                    meta.get("point_count", len(xpositions) * len(ypositions))
                ),
                "theta_range": [float(xpositions[0]), float(xpositions[-1])],
                "phi_range": [float(ypositions[0]), float(ypositions[-1])],
                "theta_step": float(xpositions[1] - xpositions[0])
                if len(xpositions) > 1
                else None,
                "phi_step": float(ypositions[1] - ypositions[0])
                if len(ypositions) > 1
                else None,
                "min_db": min(cell for row in db_matrix for cell in row),
                "max_db": max(cell for row in db_matrix for cell in row),
                "theta": [float(v) for v in xpositions],
                "phi": [float(v) for v in ypositions],
                "radius": norm_matrix,
                "surface_color": db_matrix,
                "cuts": [_cut_for_phi(0.0), _cut_for_phi(90.0)],
            }
        )

    items.sort(
        key=lambda x: (999999 if x["frequency"] is None else x["frequency"], x["label"])
    )
    return items


def _parse_farfield_cut_payload(file_path: str) -> dict[str, Any]:
    payload = _load_exported_payload(file_path)
    angle_deg = payload.get("angle_deg")
    primary_db = payload.get("primary_db")
    if not isinstance(angle_deg, list) or not isinstance(primary_db, list):
        raise ValueError(
            f"仅支持包含 angle_deg 和 primary_db 的 farfield cut JSON: {file_path}"
        )
    if len(angle_deg) != len(primary_db):
        raise ValueError(f"angle_deg 与 primary_db 长度不一致: {file_path}")

    samples: list[tuple[float, float]] = []
    for angle, gain in zip(angle_deg, primary_db):
        try:
            samples.append((float(angle), float(gain)))
        except Exception as exc:
            raise ValueError(f"farfield cut 数据含非数值项: {file_path}") from exc

    if not samples:
        raise ValueError(f"farfield cut 数据为空: {file_path}")

    source = Path(file_path).resolve()
    return {
        "file_path": str(source),
        "label": source.stem,
        "frequency_ghz": payload.get("frequency_ghz"),
        "port": payload.get("port"),
        "cut": payload.get("cut"),
        "const_axis_value": payload.get("const_axis_value"),
        "samples": samples,
    }


def _evaluate_farfield_cut_neighborhood_flatness(
    cut_item: dict[str, Any], theta_max_deg: float
) -> dict[str, Any]:
    samples = [
        (angle, gain)
        for angle, gain in cut_item["samples"]
        if 0.0 <= angle <= theta_max_deg
    ]
    if not samples:
        raise ValueError(
            f"在 theta <= {theta_max_deg:g}° 范围内没有可用采样点: {cut_item['file_path']}"
        )

    gains = [gain for _, gain in samples]
    max_idx = max(range(len(samples)), key=lambda idx: samples[idx][1])
    min_idx = min(range(len(samples)), key=lambda idx: samples[idx][1])
    max_angle, max_gain = samples[max_idx]
    min_angle, min_gain = samples[min_idx]
    boresight_gain = next(
        (gain for angle, gain in samples if abs(angle) <= 1e-9),
        None,
    )

    frequency = cut_item.get("frequency_ghz")
    try:
        frequency = None if frequency is None else float(frequency)
    except Exception:
        frequency = None

    port = cut_item.get("port")
    try:
        port = None if port is None else int(port)
    except Exception:
        port = None

    return {
        "file_path": cut_item["file_path"],
        "label": cut_item["label"],
        "frequency_ghz": frequency,
        "port": port,
        "cut": cut_item.get("cut"),
        "const_axis_value": cut_item.get("const_axis_value"),
        "theta_max_deg": float(theta_max_deg),
        "sample_count": len(samples),
        "angle_range_deg": [samples[0][0], samples[-1][0]],
        "flatness_db": float(max_gain - min_gain),
        "max_gain_db": float(max_gain),
        "max_gain_angle_deg": float(max_angle),
        "min_gain_db": float(min_gain),
        "min_gain_angle_deg": float(min_angle),
        "boresight_gain_db": None if boresight_gain is None else float(boresight_gain),
    }


def _group_farfield_cut_flatness(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[float | None, int | None], list[dict[str, Any]]] = {}
    for item in items:
        key = (item.get("frequency_ghz"), item.get("port"))
        groups.setdefault(key, []).append(item)

    summaries: list[dict[str, Any]] = []
    for key in sorted(
        groups.keys(),
        key=lambda value: (
            float("inf") if value[0] is None else float(value[0]),
            float("inf") if value[1] is None else int(value[1]),
        ),
    ):
        members = groups[key]
        flatness_values = [float(member["flatness_db"]) for member in members]
        max_gain_values = [float(member["max_gain_db"]) for member in members]
        min_gain_values = [float(member["min_gain_db"]) for member in members]
        summaries.append(
            {
                "frequency_ghz": key[0],
                "port": key[1],
                "cut_count": len(members),
                "cuts": [member.get("cut") for member in members],
                "worst_flatness_db": max(flatness_values),
                "best_flatness_db": min(flatness_values),
                "mean_flatness_db": sum(flatness_values) / len(flatness_values),
                "max_gain_db": max(max_gain_values),
                "min_gain_db": min(min_gain_values),
                "files": [member["file_path"] for member in members],
            }
        )
    return summaries


def _build_summary_cards(cards: list[tuple[str, Any]]) -> str:
    items = []
    for label, value in cards:
        items.append(
            f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"
        )
    return "\n".join(items)


def _html_template(title: str, body: str, script: str) -> str:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <script src=\"{PLOTLY_CDN}\"></script>
  <style>
    :root {{
      --bg: #111827;
      --panel: #1f2937;
      --panel-2: #0f172a;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --line: #334155;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }}
    .wrap {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
    .header {{ margin-bottom: 18px; }}
    .title {{ font-size: 28px; font-weight: 700; margin-bottom: 6px; }}
    .subtitle {{ color: var(--muted); font-size: 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0 22px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; min-height: 88px; }}
    .label {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }}
    .value {{ font-size: 22px; font-weight: 700; line-height: 1.2; word-break: break-word; }}
    .section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
    .section h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .plot {{ width: 100%; height: 520px; }}
    .plot.small {{ height: 380px; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .note {{ color: var(--muted); font-size: 13px; margin-top: 6px; }}
    @media (max-width: 1100px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">{body}</div>
  <script>{script}</script>
</body>
</html>
"""


def _create_1d_plot_html(payload: dict[str, Any], page_title: str) -> str:
    xdata = payload.get("xdata", []) or []
    ydata = payload.get("ydata", []) or []
    xlabel = payload.get("xlabel", "X") or "X"
    ylabel = payload.get("ylabel", "Y") or "Y"
    title = payload.get("title", page_title) or page_title

    real_values = []
    imag_values = []
    mag_values = []
    phase_values = []
    has_complex = False
    for item in ydata:
        real, imag = _complex_components(item)
        mag = _to_scalar(item)
        real_values.append(real)
        imag_values.append(imag)
        mag_values.append(mag)
        phase_values.append(_phase_deg(item))
        if abs(imag) > 0:
            has_complex = True

    mag_db_values = [_safe_log_db(v) for v in mag_values]
    finite_mag_db = [v for v in mag_db_values if v is not None]
    point_count = len(xdata)

    cards = [
        ("数据类型", "1D/曲线" if point_count > 1 else "单点数据"),
        ("点数", point_count),
        ("X轴", xlabel),
        ("Y轴", ylabel),
    ]
    if xdata:
        cards.append(("起点", xdata[0]))
        cards.append(("终点", xdata[-1]))
    if mag_values:
        cards.append(("幅值最小", round(min(mag_values), 6)))
        cards.append(("幅值最大", round(max(mag_values), 6)))
    if finite_mag_db:
        cards.append(("幅值dB最小", round(min(finite_mag_db), 4)))
        cards.append(("幅值dB最大", round(max(finite_mag_db), 4)))

    body = f"""
    <div class=\"header\">
      <div class=\"title\">{title}</div>
      <div class=\"subtitle\">交互式结果预览 · 支持缩放、平移、悬停读取、导出图片</div>
    </div>
    <div class=\"cards\">{_build_summary_cards(cards)}</div>
    <div class=\"section\">
      <h2>主曲线预览</h2>
      <div id=\"plot_main\" class=\"plot\"></div>
      <div class=\"note\">复数结果默认以幅值显示；如存在虚部，下面还会给出相位与实虚部拆分。</div>
    </div>
    <div class=\"grid-2\">
      <div class=\"section\">
        <h2>幅值 dB</h2>
        <div id=\"plot_db\" class=\"plot small\"></div>
      </div>
      <div class=\"section\">
        <h2>相位 / 度</h2>
        <div id=\"plot_phase\" class=\"plot small\"></div>
      </div>
    </div>
    <div class=\"section\">
      <h2>实部 / 虚部</h2>
      <div id=\"plot_complex\" class=\"plot\"></div>
    </div>
    """

    title_json = _json_dumps(title)
    xlabel_json = _json_dumps(xlabel)
    ylabel_json = _json_dumps(ylabel)
    x_json = _json_dumps(xdata)
    mag_json = _json_dumps(mag_values)
    mag_db_json = _json_dumps(mag_db_values)
    phase_json = _json_dumps(phase_values)
    real_json = _json_dumps(real_values)
    imag_json = _json_dumps(imag_values)

    if point_count <= 1:
        main_trace_expr = "[{type:'indicator',mode:'number',value:mag[0] ?? 0,number:{font:{size:56}},title:{text:'单点幅值'}}]"
        main_layout_extra = "{margin:{t:40,r:30,b:30,l:30}}"
    else:
        main_trace_expr = "[{x:x,y:mag,type:'scatter',mode:'lines',name:'Magnitude',line:{color:'#38bdf8',width:2}}]"
        main_layout_extra = (
            "{xaxis:{title:xlabel},yaxis:{title:ylabel},hovermode:'x unified'}"
        )

    script = f"""
const x = {x_json};
const mag = {mag_json};
const magDb = {mag_db_json};
const phase = {phase_json};
const realPart = {real_json};
const imagPart = {imag_json};
const title = {title_json};
const xlabel = {xlabel_json};
const ylabel = {ylabel_json};
const template = 'plotly_dark';

Plotly.newPlot('plot_main', {main_trace_expr}, {{
  template,
  title: title,
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937',
  ...{main_layout_extra}
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_db', [{{
  x: x,
  y: magDb,
  type: 'scatter',
  mode: 'lines',
  name: 'Magnitude (dB)',
  line: {{color:'#f59e0b',width:2}}
}}], {{
  template,
  title: 'Magnitude (dB)',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'dB'}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_phase', [{{
  x: x,
  y: phase,
  type: 'scatter',
  mode: 'lines',
  name: 'Phase',
  line: {{color:'#a78bfa',width:2}}
}}], {{
  template,
  title: 'Phase (deg)',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'deg'}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_complex', [
  {{x:x,y:realPart,type:'scatter',mode:'lines',name:'Real',line:{{color:'#22c55e',width:2}}}},
  {{x:x,y:imagPart,type:'scatter',mode:'lines',name:'Imag',line:{{color:'#ef4444',width:2,dash:'dot'}}}}
], {{
  template,
  title: 'Real / Imag',
  xaxis: {{title: xlabel}},
  yaxis: {{title: hasComplex ? 'Component' : ylabel}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});
""".replace("hasComplex", "true" if has_complex else "false")

    return _html_template(page_title, body, script)


def _normalize_matrix(data: Any) -> list[list[float]]:
    if not isinstance(data, list) or not data:
        raise ValueError("二维结果缺少有效 data 矩阵")

    matrix: list[list[float]] = []
    for row in data:
        if not isinstance(row, list):
            raise ValueError("二维结果矩阵格式无效")
        matrix.append([_to_scalar(cell) for cell in row])
    return matrix


def _create_2d_plot_html(payload: dict[str, Any], page_title: str) -> str:
    title = payload.get("title", page_title) or page_title
    xlabel = payload.get("xlabel", "X") or "X"
    ylabel = payload.get("ylabel", "Y") or "Y"
    xpositions = payload.get("xpositions") or []
    ypositions = payload.get("ypositions") or []
    matrix = _normalize_matrix(payload.get("data"))
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    source_format = (meta.get("source_format") or "").strip().lower()
    component_mode = (meta.get("component_mode") or "").strip().lower()
    component_payload = (
        meta.get("components") if isinstance(meta.get("components"), dict) else {}
    )
    ny = len(matrix)
    nx = len(matrix[0]) if matrix else 0

    if not xpositions or len(xpositions) != nx:
        xpositions = list(range(nx))
    if not ypositions or len(ypositions) != ny:
        ypositions = list(range(ny))

    flat_values = [cell for row in matrix for cell in row]
    min_value = min(flat_values) if flat_values else 0.0
    max_value = max(flat_values) if flat_values else 0.0
    mid_row = matrix[ny // 2] if ny else []
    mid_col = [row[nx // 2] for row in matrix] if nx else []

    cards = [
        ("数据类型", "2D/多维切片"),
        ("尺寸", f"{ny} × {nx}"),
        ("X轴", xlabel),
        ("Y轴", ylabel),
        ("最小值", round(min_value, 6)),
        ("最大值", round(max_value, 6)),
        ("X范围", f"{xpositions[0]} ~ {xpositions[-1]}" if xpositions else "N/A"),
        ("Y范围", f"{ypositions[0]} ~ {ypositions[-1]}" if ypositions else "N/A"),
    ]
    if source_format == "cst_farfield_ascii":
        cards.extend(
            [
                ("源格式", "CST Farfield ASCII"),
                ("点数", meta.get("point_count", ny * nx)),
                ("Theta数", meta.get("theta_count", nx)),
                ("Phi数", meta.get("phi_count", ny)),
            ]
        )

    extra_sections = ""
    if source_format == "cst_farfield_ascii" and component_mode == "vector_efield":
        extra_sections = """
    <div class="grid-2">
      <div class="section">
        <h2>Abs(Theta) 热图</h2>
        <div id="plot_abs_theta" class="plot small"></div>
      </div>
      <div class="section">
        <h2>Abs(Phi) 热图</h2>
        <div id="plot_abs_phi" class="plot small"></div>
      </div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>Phase(Theta) 热图</h2>
        <div id="plot_phase_theta" class="plot small"></div>
      </div>
      <div class="section">
        <h2>Phase(Phi) 热图</h2>
        <div id="plot_phase_phi" class="plot small"></div>
      </div>
    </div>
    <div class="section">
      <h2>Axial Ratio 热图</h2>
      <div id="plot_ax_ratio" class="plot small"></div>
      <div class="note">对于四脊喇叭这类双极化结构，直接看 Abs(E) 可能会把两正交极化混合；建议配合 Abs(Theta)/Abs(Phi) 一起判断。</div>
    </div>
    """

    body = f"""
    <div class="header">
      <div class="title">{title}</div>
      <div class="subtitle">二维/多维结果可视化 · 热图、等值线、3D表面与中心切片预览</div>
    </div>
    <div class="cards">{_build_summary_cards(cards)}</div>
    <div class="grid-2">
      <div class="section">
        <h2>热图</h2>
        <div id="plot_heatmap" class="plot small"></div>
      </div>
      <div class="section">
        <h2>等值线 / 分析切片</h2>
        <div id="plot_contour" class="plot small"></div>
      </div>
    </div>
    <div class="section">
      <h2>3D 分析图预览</h2>
      <div id="plot_surface" class="plot"></div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>中心横向切片</h2>
        <div id="plot_row_slice" class="plot small"></div>
      </div>
      <div class="section">
        <h2>中心纵向切片</h2>
        <div id="plot_col_slice" class="plot small"></div>
      </div>
    </div>
    {extra_sections}
    """

    title_json = _json_dumps(title)
    xlabel_json = _json_dumps(xlabel)
    ylabel_json = _json_dumps(ylabel)
    x_json = _json_dumps(xpositions)
    y_json = _json_dumps(ypositions)
    z_json = _json_dumps(matrix)
    row_slice_json = _json_dumps(mid_row)
    col_slice_json = _json_dumps(mid_col)
    abs_theta_json = _json_dumps(
        _normalize_matrix(component_payload.get("abs_theta"))
        if component_payload.get("abs_theta")
        else []
    )
    abs_phi_json = _json_dumps(
        _normalize_matrix(component_payload.get("abs_phi"))
        if component_payload.get("abs_phi")
        else []
    )
    phase_theta_json = _json_dumps(
        _normalize_matrix(component_payload.get("phase_theta"))
        if component_payload.get("phase_theta")
        else []
    )
    phase_phi_json = _json_dumps(
        _normalize_matrix(component_payload.get("phase_phi"))
        if component_payload.get("phase_phi")
        else []
    )
    ax_ratio_json = _json_dumps(
        _normalize_matrix(component_payload.get("ax_ratio"))
        if component_payload.get("ax_ratio")
        else []
    )
    source_format_json = _json_dumps(source_format)
    component_mode_json = _json_dumps(component_mode)

    script = f"""
const x = {x_json};
const y = {y_json};
const z = {z_json};
const midRow = {row_slice_json};
const midCol = {col_slice_json};
const title = {title_json};
const xlabel = {xlabel_json};
const ylabel = {ylabel_json};
const sourceFormat = {source_format_json};
const absThetaMatrix = {abs_theta_json};
const absPhiMatrix = {abs_phi_json};
const phaseThetaMatrix = {phase_theta_json};
const phasePhiMatrix = {phase_phi_json};
const axRatioMatrix = {ax_ratio_json};
const template = 'plotly_dark';
const componentMode = {component_mode_json};

function safeDb(v) {{
  return v > 0 ? 20 * Math.log10(v) : -120;
}}

function buildFarfieldCartesian(thetaDeg, phiDeg, radiusMatrix) {{
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < phiDeg.length; i++) {{
    const xr = [];
    const yr = [];
    const zr = [];
    for (let j = 0; j < thetaDeg.length; j++) {{
      const theta = thetaDeg[j] * Math.PI / 180.0;
      const phi = phiDeg[i] * Math.PI / 180.0;
      const r = radiusMatrix[i][j];
      xr.push(r * Math.sin(theta) * Math.cos(phi));
      yr.push(r * Math.sin(theta) * Math.sin(phi));
      zr.push(r * Math.cos(theta));
    }}
    xs.push(xr);
    ys.push(yr);
    zs.push(zr);
  }}
  return {{x: xs, y: ys, z: zs}};
}}

Plotly.newPlot('plot_heatmap', [{{
  x: x,
  y: y,
  z: z,
  type: 'heatmap',
  colorscale: 'Jet',
  colorbar: {chr(123)}title: 'Value'{chr(125)}
}}], {{
  template,
  title: title + ' · Heatmap',
  xaxis: {{title: xlabel}},
  yaxis: {{title: ylabel}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_contour', [{{
  x: x,
  y: y,
  z: z,
  type: 'contour',
  colorscale: 'Jet',
  contours: {{coloring:'heatmap'}},
  colorbar: {chr(123)}title: 'Value'{chr(125)}
}}], {{
  template,
  title: title + ' · Contour',
  xaxis: {{title: xlabel}},
  yaxis: {{title: ylabel}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

if (sourceFormat === 'cst_farfield_ascii') {{
  let maxVal = 0;
  for (const row of z) {{
    for (const v of row) {{
      if (v > maxVal) maxVal = v;
    }}
  }}
  const radius = z.map(row => row.map(v => maxVal > 0 ? v / maxVal : 0));
  const colorDb = z.map(row => row.map(v => safeDb(maxVal > 0 ? v / maxVal : 0)));
  const ff = buildFarfieldCartesian(x, y, radius);
  Plotly.newPlot('plot_surface', [{{
    x: ff.x,
    y: ff.y,
    z: ff.z,
    surfacecolor: colorDb,
    type: 'surface',
    colorscale: 'Jet',
    cmin: -40,
    cmax: 0,
    colorbar: {chr(123)}title: 'Norm dB'{chr(125)}
  }}], {{
    template,
    title: title + ' · 3D Polar Farfield',
    scene: {{
      xaxis: {{title: 'X'}},
      yaxis: {{title: 'Y'}},
      zaxis: {{title: 'Z'}},
      aspectmode: 'data',
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}} else {{
  Plotly.newPlot('plot_surface', [{{
    x: x,
    y: y,
    z: z,
    type: 'surface',
    colorscale: 'Jet',
    colorbar: {chr(123)}title: 'Value'{chr(125)}
  }}], {{
    template,
    title: title + ' · 3D Surface Preview',
    scene: {{
      xaxis: {{title: xlabel}},
      yaxis: {{title: ylabel}},
      zaxis: {{title: 'Value'}},
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}


Plotly.newPlot('plot_row_slice', [{{
  x: x,
  y: midRow,
  type: 'scatter',
  mode: 'lines',
  line: {{color:'#38bdf8',width:2}},
  name: 'Mid Row'
}}], {{
  template,
  title: '中心横向切片',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'Value'}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_col_slice', [{{
  x: y,
  y: midCol,
  type: 'scatter',
  mode: 'lines',
  line: {{color:'#f97316',width:2}},
  name: 'Mid Column'
}}], {{
  template,
  title: '中心纵向切片',
  xaxis: {{title: ylabel}},
  yaxis: {{title: 'Value'}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

if (sourceFormat === 'cst_farfield_ascii' && componentMode === 'vector_efield') {{
  Plotly.newPlot('plot_abs_theta', [{{x:x,y:y,z:absThetaMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Abs(Theta)'{chr(125)}}}], {{template, title:'Abs(Theta)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_abs_phi', [{{x:x,y:y,z:absPhiMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Abs(Phi)'{chr(125)}}}], {{template, title:'Abs(Phi)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_phase_theta', [{{x:x,y:y,z:phaseThetaMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'deg'{chr(125)}}}], {{template, title:'Phase(Theta)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_phase_phi', [{{x:x,y:y,z:phasePhiMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'deg'{chr(125)}}}], {{template, title:'Phase(Phi)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_ax_ratio', [{{x:x,y:y,z:axRatioMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Ax.Ratio'{chr(125)}}}], {{template, title:'Axial Ratio', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
}}
"""

    return _html_template(page_title, body, script)


def _create_farfield_multi_plot_html(
    items: list[dict[str, Any]], page_title: str
) -> str:
    if not items:
        raise ValueError("没有可用的远场文件")

    global_min_db = min(float(item["min_db"]) for item in items)
    global_max_db = max(float(item["max_db"]) for item in items)
    freqs = [item["frequency"] for item in items if item.get("frequency") is not None]
    summary_cards = [
        ("频率文件数", len(items)),
        ("频率范围", f"{min(freqs)} ~ {max(freqs)} GHz" if freqs else "N/A"),
        ("全局色标范围", f"{round(global_min_db, 2)} ~ {round(global_max_db, 2)} dB"),
        ("已载入频率", ", ".join(str(item["label"]) for item in items)),
    ]

    body = f"""
    <div class="header">
      <div class="title">{page_title}</div>
      <div class="subtitle">多频率远场方向图预览 · 单频 3D 图、单频主平面切面，以及跨频率对比曲线。Phi 末端已自动补 360°，保证 355° 与 0° 闭合。</div>
    </div>
    <div class="cards">{_build_summary_cards(summary_cards)}</div>
    <div class="section">
      <h2>选择单频查看</h2>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
        <select id="freqSelect" style="background:#0f172a;color:#e5e7eb;border:1px solid #334155;border-radius:10px;padding:10px 12px;min-width:220px;"></select>
        <div id="fileHint" class="note"></div>
      </div>
    </div>
    <div class="cards" id="singleCards"></div>
    <div class="section">
      <h2>单频 3D 方向图</h2>
      <div id="plot_surface3d" class="plot"></div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>单频主平面切面（Phi = 0° / 90°）</h2>
        <div id="plot_single_cuts" class="plot small"></div>
      </div>
      <div class="section">
        <h2>说明</h2>
        <div class="note">该页面面向多个 farfield ASCII 文件联合展示。若继续导出 `farfield_8GHz.txt`、`farfield_12GHz.txt` 等文件，可直接再次调用本工具生成新的对比页。</div>
      </div>
    </div>
    <div class="section">
      <h2>多频率对比：Phi = 0°</h2>
      <div id="plot_compare_phi0" class="plot small"></div>
    </div>
    <div class="section">
      <h2>多频率对比：Phi = 90°</h2>
      <div id="plot_compare_phi90" class="plot small"></div>
    </div>
    """

    items_json = _json_dumps(items)
    title_json = _json_dumps(page_title)
    summary_json = _json_dumps(
        {"global_min_db": global_min_db, "global_max_db": global_max_db}
    )
    script = f"""
const items = {items_json};
const pageTitle = {title_json};
const summary = {summary_json};
const select = document.getElementById('freqSelect');
const fileHint = document.getElementById('fileHint');
const singleCards = document.getElementById('singleCards');
const palette = ['#38bdf8','#f59e0b','#ef4444','#22c55e','#a78bfa','#f472b6','#14b8a6','#eab308'];

function buildFarfieldCartesian(thetaDeg, phiDeg, radiusMatrix) {{
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < phiDeg.length; i++) {{
    const xr = [];
    const yr = [];
    const zr = [];
    for (let j = 0; j < thetaDeg.length; j++) {{
      const theta = thetaDeg[j] * Math.PI / 180.0;
      const phi = phiDeg[i] * Math.PI / 180.0;
      const r = radiusMatrix[i][j];
      xr.push(r * Math.sin(theta) * Math.cos(phi));
      yr.push(r * Math.sin(theta) * Math.sin(phi));
      zr.push(r * Math.cos(theta));
    }}
    xs.push(xr);
    ys.push(yr);
    zs.push(zr);
  }}
  return {{x: xs, y: ys, z: zs}};
}}

items.forEach((item, idx) => {{
  const opt = document.createElement('option');
  opt.value = String(idx);
  opt.textContent = item.label;
  select.appendChild(opt);
}});

function renderSingleCards(item) {{
  singleCards.innerHTML = `
    <div class="card"><div class="label">频率</div><div class="value">${{item.label}}</div></div>
    <div class="card"><div class="label">数据点数</div><div class="value">${{item.points}}</div></div>
    <div class="card"><div class="label">Theta 范围</div><div class="value">${{item.theta_range[0]}} ~ ${{item.theta_range[1]}}°</div></div>
    <div class="card"><div class="label">Phi 范围</div><div class="value">${{item.phi_range[0]}} ~ ${{item.phi_range[1]}}°</div></div>
    <div class="card"><div class="label">单频动态范围</div><div class="value">${{item.min_db.toFixed(2)}} ~ ${{item.max_db.toFixed(2)}} dB</div></div>
    <div class="card"><div class="label">角步长</div><div class="value">θ ${{item.theta_step ?? '-'}}° / φ ${{item.phi_step ?? '-'}}°</div></div>
  `;
}}

function renderSingle3D(item) {{
  const ff = buildFarfieldCartesian(item.theta, item.phi, item.radius);
  Plotly.newPlot('plot_surface3d', [{{
    x: ff.x,
    y: ff.y,
    z: ff.z,
    surfacecolor: item.surface_color,
    type: 'surface',
    colorscale: 'Jet',
    cmin: summary.global_min_db,
    cmax: summary.global_max_db,
    colorbar: {chr(123)}title: 'Norm dB'{chr(125)}
  }}], {{
    template: 'plotly_dark',
    title: `${{item.label}} · 3D Polar Farfield`,
    scene: {{
      xaxis: {{title: 'X'}},
      yaxis: {{title: 'Y'}},
      zaxis: {{title: 'Z'}},
      aspectmode: 'data',
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function renderSingleCuts(item) {{
  const traces = item.cuts.map((cut, idx) => ({{
    x: cut.theta,
    y: cut.gain_db,
    type: 'scatter',
    mode: 'lines',
    name: `Phi=${{cut.phi}}°`,
    line: {{width: 2.5, color: idx === 0 ? '#38bdf8' : '#f59e0b'}}
  }}));
  Plotly.newPlot('plot_single_cuts', traces, {{
    template: 'plotly_dark',
    title: `${{item.label}} · 主平面切面`,
    xaxis: {{title: 'Theta (deg)'}},
    yaxis: {{title: 'Normalized Gain (dB)'}},
    hovermode: 'x unified',
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function renderComparison(targetId, cutIndex, title) {{
  const traces = items.map((item, idx) => {{
    const cut = item.cuts[cutIndex];
    return {{
      x: cut.theta,
      y: cut.gain_db,
      type: 'scatter',
      mode: 'lines',
      name: `${{item.label}} (Phi=${{cut.phi}}°)`,
      line: {{width: 2.5, color: palette[idx % palette.length]}}
    }};
  }});
  Plotly.newPlot(targetId, traces, {{
    template: 'plotly_dark',
    title,
    xaxis: {{title: 'Theta (deg)'}},
    yaxis: {{title: 'Normalized Gain (dB)'}},
    hovermode: 'x unified',
    legend: {{orientation: 'h', y: 1.15}},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function render(index) {{
  const item = items[index];
  fileHint.textContent = '源文件：' + item.file;
  renderSingleCards(item);
  renderSingle3D(item);
  renderSingleCuts(item);
}}

select.addEventListener('change', e => render(Number(e.target.value)));
render(0);
renderComparison('plot_compare_phi0', 0, pageTitle + ' · 多频率对比（目标 Phi = 0°）');
renderComparison('plot_compare_phi90', 1, pageTitle + ' · 多频率对比（目标 Phi = 90°）');
"""
    return _html_template(page_title, body, script)


def _extract_run_id_from_path(path_str: str) -> int | None:
    target = Path(path_str)
    candidates = [target.stem, target.name, *[parent.name for parent in target.parents]]
    for text in candidates:
        match = re.search(r"run[_-]?(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _build_s11_series(file_paths: list[str]) -> list[dict[str, Any]]:
    all_series: list[dict[str, Any]] = []
    for idx, file_path in enumerate(file_paths):
        if Path(file_path).suffix.lower() != ".json":
            raise ValueError(f"S11 输入仅支持 .json，检测到: {file_path}")

        payload = _load_exported_payload(file_path)
        xdata = payload.get("xdata", [])
        ydata = payload.get("ydata", [])
        if not xdata or not ydata:
            raise ValueError(f"文件缺少有效 xdata/ydata: {file_path}")

        mag_db_values: list[float | None] = []
        for y_val in ydata:
            real, imag = _complex_components(y_val)
            mag = math.hypot(real, imag)
            mag_db_values.append(_safe_log_db(mag))

        finite_db = [(v if v is not None else -120.0) for v in mag_db_values]
        valid_db = [v for v in finite_db if v > -120]
        min_db = min(valid_db) if valid_db else -120.0
        min_idx = next(i for i, v in enumerate(finite_db) if v == min_db)
        best_freq = xdata[min_idx] if min_idx < len(xdata) else None
        run_id = payload.get("run_id")
        if run_id is None:
            run_id = _extract_run_id_from_path(file_path)
        if run_id is None:
            run_id = idx + 1

        all_series.append(
            {
                "label": f"Run {run_id}",
                "run_id": run_id,
                "file": str(Path(file_path).name),
                "full_file": str(Path(file_path).resolve()),
                "xdata": xdata,
                "ydata": finite_db,
                "min_db": min_db,
                "best_freq": best_freq,
                "best_unit": "GHz" if best_freq and best_freq > 0.1 else "",
            }
        )
    return all_series


def _group_farfield_items_by_run(file_paths: list[str]) -> list[dict[str, Any]]:
    raw_items = _load_farfield_payloads(file_paths)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in raw_items:
        run_id = _extract_run_id_from_path(item.get("file", ""))
        if run_id is None:
            raise ValueError(f"无法从 farfield 文件路径识别 run_id: {item.get('file')}")
        item["run_id"] = run_id
        grouped.setdefault(run_id, []).append(item)

    groups: list[dict[str, Any]] = []
    for run_id, items in grouped.items():
        items.sort(
            key=lambda x: (
                999999 if x["frequency"] is None else x["frequency"],
                x["label"],
            )
        )
        groups.append({"run_id": run_id, "label": f"Run {run_id}", "items": items})
    groups.sort(key=lambda x: x["run_id"])
    return groups

def _build_plot_html_from_payload(
    payload: dict[str, Any], page_title: str
) -> tuple[str, str]:
    kind = (payload.get("kind") or "").lower().strip()

    if not kind:
        if "xdata" in payload and "ydata" in payload:
            kind = "1d"
        elif "data" in payload and isinstance(payload.get("data"), list):
            kind = "2d"

    if kind == "1d":
        return _create_1d_plot_html(payload, page_title), "1d"
    if kind == "2d":
        return _create_2d_plot_html(payload, page_title), "2d"

    raise ValueError("无法自动识别数据类型，请提供包含 xdata/ydata 或二维 data 的数据")


def _fetch_plot_payload_from_project(
    treepath: str, module_type: str, run_id: int, load_impedances: bool
):
    project, context = _load_project()
    result_module, normalized_module = _get_result_module(project, module_type)

    try:
        result_item = result_module.get_result_item(
            treepath,
            run_id=run_id,
            load_impedances=load_impedances,
        )
        payload = {
            "kind": "1d",
            "title": result_item.title,
            "xlabel": result_item.xlabel,
            "ylabel": result_item.ylabel,
            "xdata": _serialize_value(result_item.get_xdata()),
            "ydata": _serialize_value(result_item.get_ydata()),
            "run_id": result_item.run_id,
            "parameter_combination": _serialize_value(
                result_item.get_parameter_combination()
            ),
        }
        return payload, "1d", normalized_module, context
    except Exception as first_error:
        try:
            result_2d = result_module.get_result2d_item(treepath)
            payload = {
                "kind": "2d",
                "title": result_2d.title,
                "xlabel": result_2d.xlabel,
                "ylabel": result_2d.ylabel,
                "xunit": result_2d.xunit,
                "yunit": result_2d.yunit,
                "dataunit": result_2d.dataunit,
                "xpositions": _serialize_value(result_2d.get_xpositions()),
                "ypositions": _serialize_value(result_2d.get_ypositions()),
                "data": _serialize_value(result_2d.get_data()),
                "nx": result_2d.nx,
                "ny": result_2d.ny,
            }
            return payload, "2d", normalized_module, context
        except Exception as second_error:
            raise RuntimeError(
                f"无法将 treepath 识别为 1D 或 2D 结果。1D错误: {str(first_error)}；2D错误: {str(second_error)}"
            )


@mcp.tool()
def get_version_info():
    """获取 cst.results 模块版本信息

    返回 cst.results 相关文件的版本信息字典，便于排查接口兼容性。
    """
    try:
        return {
            "status": "success",
            "version_info": _serialize_value(cst.results.get_version_info()),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取版本信息失败: {str(e)}"}


@mcp.tool()
def open_project(fullpath: str, allow_interactive: bool = False):
    """打开 CST 项目文件（用于结果查询）

    使用 cst.results.ProjectFile 打开项目文件并保存上下文。
    allow_interactive=True 时可读取正在 CST 中打开且已保存的项目，但性能较低，
    且未保存状态下数据可能过时或不完整。

    参数:
    - fullpath: 项目文件完整路径
    - allow_interactive: 是否允许交互模式打开，默认 False

    返回:
    - status: 操作状态
    - fullpath: 项目路径
    - filename: 项目文件名
    - active_subproject: 当前活动子项目（初始为 null）
    """
    if not os.path.exists(fullpath):
        return {"status": "error", "message": f"项目文件不存在: {fullpath}"}

    try:
        abs_path = os.path.abspath(fullpath)
        project = cst.results.ProjectFile(abs_path, allow_interactive=allow_interactive)
        save_project_context(
            abs_path, allow_interactive=allow_interactive, subproject_treepath=None
        )
        return {
            "status": "success",
            "fullpath": abs_path,
            "filename": project.filename,
            "allow_interactive": allow_interactive,
            "active_subproject": None,
        }
    except Exception as e:
        return {"status": "error", "message": f"打开项目失败: {str(e)}"}


@mcp.tool()
def close_project():
    """关闭当前项目上下文"""
    global _project_cache
    context = get_project_context()
    if context:
        cache_key = (
            context["fullpath"],
            context.get("active_subproject"),
            context["allow_interactive"],
        )
        _project_cache.pop(cache_key, None)
    clear_project_context()
    return {"status": "success", "message": "项目已关闭"}


@mcp.tool()
def get_project_context_info():
    """获取当前项目上下文信息

    返回当前已打开项目路径、交互模式、当前活动子项目等信息。
    """
    context = get_project_context()
    if not context:
        return {"status": "error", "message": "当前没有活动的项目"}
    return {"status": "success", **context}


@mcp.tool()
def export_farfield(
    farfield_name: str,
    frequency: str,
    file_path: str,
    plot_mode: str = "Realized Gain",
    prime_with_cut: bool = False,
    cut_axis: str = "Phi",
    cut_angle: str = "0",
    theta_step_deg: float = 5.0,
    phi_step_deg: float = 5.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
):
    """基于当前 results 项目上下文导出完整 farfield ASCII/TXT。

    默认会连续重试，直到成功或达到导出上限。
    """
    context = get_project_context()
    if not context:
        return {"status": "error", "message": "当前没有活动的 results 项目，请先调用 open_project"}
    project_path = context["fullpath"]
    return export_farfield_fresh_session(
        project_path=project_path,
        farfield_name=farfield_name,
        output_file=file_path,
        plot_mode=plot_mode,
        prime_with_cut=prime_with_cut,
        cut_axis=cut_axis,
        cut_angle=cut_angle,
        theta_step_deg=theta_step_deg,
        phi_step_deg=phi_step_deg,
        theta_min_deg=theta_min_deg,
        theta_max_deg=theta_max_deg,
        phi_min_deg=phi_min_deg,
        phi_max_deg=phi_max_deg,
        max_attempts=FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS,
        keep_prime_cut_file=False,
    )


@mcp.tool()
def export_farfield_fresh_session(
    project_path: str,
    farfield_name: str,
    output_file: str,
    plot_mode: str = "Realized Gain",
    prime_with_cut: bool = False,
    cut_axis: str = "Phi",
    cut_angle: str = "0",
    theta_step_deg: float = 5.0,
    phi_step_deg: float = 5.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
    max_attempts: int = FARFIELD_EXPORT_DEFAULT_MAX_ATTEMPTS,
    keep_prime_cut_file: bool = False,
):
    """按 fresh CST session 稳定导出单个 farfield ASCII/TXT。

    默认会在同一路径上持续重试，直到成功或达到硬上限。
    """
    normalized_project = os.path.abspath(project_path)
    if not normalized_project.lower().endswith(".cst"):
        normalized_project += ".cst"
    if not os.path.isfile(normalized_project):
        return {"status": "error", "message": f"项目文件不存在: {normalized_project}"}

    normalized_output = os.path.abspath(output_file)
    if not normalized_output.lower().endswith(".txt"):
        normalized_output += ".txt"
    output_dir = os.path.dirname(normalized_output)
    if not output_dir:
        return {"status": "error", "message": f"输出路径无效: {output_file}"}
    os.makedirs(output_dir, exist_ok=True)

    try:
        attempts = max(1, int(max_attempts))
    except Exception:
        return {"status": "error", "message": f"max_attempts 非法: {max_attempts}"}
    attempts = min(attempts, FARFIELD_EXPORT_HARD_MAX_ATTEMPTS)

    derived_prime_tree = None
    if prime_with_cut:
        derived_prime_tree = _derive_farfield_cut_tree_path(
            farfield_name=farfield_name,
            cut_axis=cut_axis,
            cut_angle=cut_angle,
        )
        if not derived_prime_tree:
            return {
                "status": "error",
                "message": (
                    f"无法从 farfield_name 推导预激活 cut 节点: {farfield_name} "
                    f"(需要类似 farfield (f=13) [2] 的格式)"
                ),
            }

    attempt_logs = []
    last_error = None

    for attempt in range(1, attempts + 1):
        flow_log = []
        prime_cut_output = None
        _cleanup_temp_export_file(normalized_output)
        close_results = _close_results_context_if_matches(normalized_project)
        if close_results is not None:
            flow_log.append({"step": "close_results_context", "result": close_results})

        start_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_before_open", "result": start_quit})
        if start_quit.get("status") != "success":
            last_error = "导出前清理 CST 进程失败"
            attempt_logs.append(
                {"attempt": attempt, "success": False, "flow_log": flow_log}
            )
            continue

        open_result = _gui_open_project(normalized_project)
        flow_log.append({"step": "open_project", "result": {
            k: v for k, v in open_result.items() if k not in {"project", "design_environment"}
        }})
        if open_result.get("status") != "success":
            last_error = f"打开项目失败: {normalized_project}"
            attempt_logs.append(
                {"attempt": attempt, "success": False, "flow_log": flow_log}
            )
            continue

        project = open_result["project"]
        try:
            if prime_with_cut and derived_prime_tree:
                output_path = Path(normalized_output)
                prime_cut_output = str(
                    output_path.with_name(
                        f"{output_path.stem}__prime_{cut_axis.lower()}{cut_angle}_attempt{attempt}.txt"
                    )
                )
                _cleanup_temp_export_file(prime_cut_output)
                prime_command = _build_farfield_cut_export_command(
                    derived_prime_tree, prime_cut_output
                )
                prime_result = _gui_add_to_history(
                    project,
                    prime_command,
                    history_name=f"PrimeFarfieldCut:{farfield_name}:attempt{attempt}",
                )
                flow_log.append({"step": "prime_cut", "result": prime_result})
                if prime_result.get("status") != "success":
                    last_error = f"预激活 cut 导出失败: {derived_prime_tree}"
                    attempt_logs.append(
                        {"attempt": attempt, "success": False, "flow_log": flow_log}
                    )
                    continue
                if (not os.path.isfile(prime_cut_output)) or os.path.getsize(prime_cut_output) <= 0:
                    last_error = f"prime cut did not produce output (or empty): {prime_cut_output}"
                    flow_log.append(
                        {
                            "step": "prime_cut_validate",
                            "result": {
                                "status": "error",
                                "message": last_error,
                                "output_file": prime_cut_output,
                            },
                        }
                    )
                    attempt_logs.append(
                        {"attempt": attempt, "success": False, "flow_log": flow_log}
                    )
                    continue

            export_result = _export_farfield_grid_direct_com(
                project=project,
                farfield_name=farfield_name,
                output_file=normalized_output,
                plot_mode=plot_mode,
                theta_step_deg=theta_step_deg,
                phi_step_deg=phi_step_deg,
                theta_min_deg=theta_min_deg,
                theta_max_deg=theta_max_deg,
                phi_min_deg=phi_min_deg,
                phi_max_deg=phi_max_deg,
            )
            flow_log.append({"step": "export_farfield", "result": export_result})
            if export_result.get("status") != "success":
                last_error = f"远场导出失败: {farfield_name}"
                attempt_logs.append(
                    {"attempt": attempt, "success": False, "flow_log": flow_log}
                )
                continue

            if not os.path.isfile(normalized_output):
                last_error = f"导出命令成功但未生成文件: {normalized_output}"
                attempt_logs.append(
                    {"attempt": attempt, "success": False, "flow_log": flow_log}
                )
                continue

            file_size = os.path.getsize(normalized_output)
            if file_size <= 0:
                last_error = f"导出文件为空: {normalized_output}"
                attempt_logs.append(
                    {"attempt": attempt, "success": False, "flow_log": flow_log}
                )
                continue
            grid_info = _inspect_farfield_ascii_grid(normalized_output)
            flow_log.append({"step": "validate_full_grid", "result": grid_info})
            is_full_sphere = export_result.get("is_full_sphere", True)
            if is_full_sphere and grid_info["phi_count"] <= 2:
                last_error = (
                    "导出文件不是完整方向图，只包含切片: "
                    f"phi_count={grid_info['phi_count']}, row_count={grid_info['row_count']}"
                )
                attempt_logs.append(
                    {"attempt": attempt, "success": False, "flow_log": flow_log}
                )
                continue

            success_payload = {
                "status": "success",
                "project_path": normalized_project,
                "farfield_name": farfield_name,
                "output_file": normalized_output,
                "plot_mode": plot_mode,
                "theta_step_deg": theta_step_deg,
                "phi_step_deg": phi_step_deg,
                "theta_min_deg": export_result.get("theta_min_deg"),
                "theta_max_deg": export_result.get("theta_max_deg"),
                "phi_min_deg": export_result.get("phi_min_deg"),
                "phi_max_deg": export_result.get("phi_max_deg"),
                "scope": export_result.get("scope"),
                "is_full_sphere": is_full_sphere,
                "file_size": file_size,
                "grid": grid_info,
                "attempt": attempt,
                "attempt_logs": attempt_logs
                + [{"attempt": attempt, "success": True, "flow_log": flow_log}],
                "message": (
                    f"已按 fresh session 导出远场: {normalized_output} "
                    f"(attempt={attempt}/{attempts}, prime_with_cut={prime_with_cut})"
                ),
            }
            if prime_with_cut:
                success_payload["prime_cut_tree_path"] = derived_prime_tree
                if keep_prime_cut_file and prime_cut_output:
                    success_payload["prime_cut_output"] = prime_cut_output
            return success_payload
        finally:
            if prime_cut_output and not keep_prime_cut_file:
                _cleanup_temp_export_file(prime_cut_output)
            close_result = _gui_close_project(
                project, normalized_project, save=False
            )
            flow_log.append({"step": "close_project", "result": close_result})
            end_quit = _kill_cst_processes()
            flow_log.append({"step": "quit_after_close", "result": end_quit})

    return {
        "status": "error",
        "message": last_error or f"远场导出失败: {farfield_name}",
        "attempt_logs": attempt_logs,
        "project_path": normalized_project,
        "farfield_name": farfield_name,
        "output_file": normalized_output,
        "plot_mode": plot_mode,
        "theta_step_deg": theta_step_deg,
        "phi_step_deg": phi_step_deg,
        "theta_min_deg": theta_min_deg,
        "theta_max_deg": theta_max_deg,
        "phi_min_deg": phi_min_deg,
        "phi_max_deg": phi_max_deg,
        "prime_with_cut": prime_with_cut,
        "prime_cut_tree_path": derived_prime_tree,
        "attempts_used": attempts,
        "hard_max_attempts": FARFIELD_EXPORT_HARD_MAX_ATTEMPTS,
    }


@mcp.tool()
def export_existing_farfield_cut_fresh_session(
    project_path: str,
    tree_path: str,
    output_file: str,
):
    """按 fresh CST session 稳定导出已有 Farfield Cut 结果。"""
    normalized_project = os.path.abspath(project_path)
    if not normalized_project.lower().endswith(".cst"):
        normalized_project += ".cst"
    if not os.path.isfile(normalized_project):
        return {"status": "error", "message": f"项目文件不存在: {normalized_project}"}

    normalized_tree_path = tree_path.strip()
    if not normalized_tree_path.startswith("Farfields\\Farfield Cuts\\"):
        return {
            "status": "error",
            "message": (
                "tree_path 必须指向已有 Farfield Cut 结果节点，"
                "例如 Farfields\\Farfield Cuts\\Excitation [1]\\Phi=0\\farfield (f=12)"
            ),
        }

    normalized_output = os.path.abspath(output_file)
    if not normalized_output.lower().endswith(".txt"):
        normalized_output += ".txt"
    output_dir = os.path.dirname(normalized_output)
    if not output_dir:
        return {"status": "error", "message": f"输出路径无效: {output_file}"}
    os.makedirs(output_dir, exist_ok=True)

    command = _build_farfield_cut_export_command(normalized_tree_path, normalized_output)

    flow_log = []
    close_results = _close_results_context_if_matches(normalized_project)
    if close_results is not None:
        flow_log.append({"step": "close_results_context", "result": close_results})

    start_quit = _kill_cst_processes()
    flow_log.append({"step": "quit_before_open", "result": start_quit})
    if start_quit.get("status") != "success":
        return {
            "status": "error",
            "message": "导出前清理 CST 进程失败",
            "flow_log": flow_log,
        }

    open_result = _gui_open_project(normalized_project)
    flow_log.append({"step": "open_project", "result": {
        k: v for k, v in open_result.items() if k not in {"project", "design_environment"}
    }})
    if open_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"打开项目失败: {normalized_project}",
            "flow_log": flow_log,
        }

    project = open_result["project"]
    try:
        export_result = _gui_add_to_history(
            project,
            command,
            history_name=f"ExportFarfieldCutFresh:{normalized_tree_path}",
        )
        flow_log.append({"step": "export_farfield_cut", "result": export_result})
        if export_result.get("status") != "success":
            return {
                "status": "error",
                "message": f"Farfield Cut 导出失败: {normalized_tree_path}",
                "flow_log": flow_log,
            }

        if not os.path.isfile(normalized_output):
            return {
                "status": "error",
                "message": f"导出命令成功但未生成文件: {normalized_output}",
                "flow_log": flow_log,
            }

        file_size = os.path.getsize(normalized_output)
        if file_size <= 0:
            return {
                "status": "error",
                "message": f"导出文件为空: {normalized_output}",
                "flow_log": flow_log,
            }

        return {
            "status": "success",
            "project_path": normalized_project,
            "tree_path": normalized_tree_path,
            "output_file": normalized_output,
            "file_size": file_size,
            "flow_log": flow_log,
            "message": f"已按 fresh session 导出 Farfield Cut: {normalized_output}",
        }
    finally:
        close_result = _gui_close_project(project, normalized_project, save=False)
        flow_log.append({"step": "close_project", "result": close_result})
        end_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_after_close", "result": end_quit})


@mcp.tool()
def list_subprojects():
    """列出项目中的子项目

    列出 Schematic 中可通过 load_subproject 打开的子项目路径。
    """
    try:
        project, context = _load_project()
        subprojects = project.list_subprojects()
        return {
            "status": "success",
            "fullpath": context["fullpath"],
            "count": len(subprojects),
            "subprojects": subprojects,
        }
    except Exception as e:
        return {"status": "error", "message": f"获取子项目列表失败: {str(e)}"}


@mcp.tool()
def load_subproject(treepath: str):
    """切换当前活动子项目

    参数:
    - treepath: 子项目树路径，可先用 list_subprojects 获取

    返回:
    - status: 操作状态
    - active_subproject: 当前已切换到的子项目路径
    """
    context = get_project_context()
    if not context:
        return {
            "status": "error",
            "message": "当前没有活动的项目，请先调用 open_project",
        }

    try:
        root_project = cst.results.ProjectFile(
            context["fullpath"],
            allow_interactive=context["allow_interactive"],
        )
        subproject = root_project.load_subproject(treepath)
        save_project_context(
            context["fullpath"],
            allow_interactive=context["allow_interactive"],
            subproject_treepath=treepath,
        )
        return {
            "status": "success",
            "fullpath": context["fullpath"],
            "active_subproject": treepath,
            "filename": subproject.filename,
        }
    except Exception as e:
        return {"status": "error", "message": f"加载子项目失败: {str(e)}"}


@mcp.tool()
def reset_to_root_project():
    """从当前子项目切回根项目"""
    context = get_project_context()
    if not context:
        return {"status": "error", "message": "当前没有活动的项目"}

    save_project_context(
        context["fullpath"],
        allow_interactive=context["allow_interactive"],
        subproject_treepath=None,
    )
    return {
        "status": "success",
        "fullpath": context["fullpath"],
        "active_subproject": None,
        "message": "已切换回根项目",
    }


@mcp.tool()
def list_result_items(module_type: str = "3d", filter_type: str = "0D/1D"):
    """列出项目中的结果树项目

    参数:
    - module_type: 模块类型，"3d" 或 "schematic"，默认 "3d"
    - filter_type: 过滤类型，支持 "0D/1D"、"colormap"、"all"，默认 "0D/1D"

    说明:
    - `all` 会基于 cst.results 的 `_get_all_result_items()` 汇总所有可见结果项，
      可用于补充查看与 `0D/1D Results` 并列的结果分类。
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)

        normalized_filter = (filter_type or "0D/1D").strip()
        if normalized_filter.lower() == "all":
            all_items = result_module._get_all_result_items()
            treepaths = []
            seen = set()
            for item in all_items:
                treepath = getattr(item, "treepath", None)
                if not treepath or treepath in seen:
                    continue
                seen.add(treepath)
                treepaths.append(treepath)
            items = treepaths
        else:
            items = result_module.get_tree_items(filter=normalized_filter)

        return {
            "status": "success",
            "module_type": normalized_module,
            "filter_type": normalized_filter,
            "active_subproject": context["active_subproject"],
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        return {"status": "error", "message": f"查询结果树项目失败: {str(e)}"}


@mcp.tool()
def list_run_ids(
    treepath: str = "",
    module_type: str = "3d",
    skip_nonparametric: bool = False,
    max_mesh_passes_only: bool = True,
):
    """获取运行 ID 列表

    参数:
    - treepath: 结果树路径；为空时调用 get_all_run_ids
    - module_type: 模块类型，"3d" 或 "schematic"
    - skip_nonparametric: treepath 模式下是否跳过 run_id=0
    - max_mesh_passes_only: 全局模式下是否仅返回最高网格通过次数结果
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)

        treepath = treepath or ""
        if treepath:
            run_ids = result_module.get_run_ids(
                treepath, skip_nonparametric=skip_nonparametric
            )
        else:
            run_ids = result_module.get_all_run_ids(
                max_mesh_passes_only=max_mesh_passes_only
            )

        return {
            "status": "success",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath if treepath else None,
            "count": len(run_ids),
            "run_ids": _serialize_value(run_ids),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取运行 ID 列表失败: {str(e)}"}


@mcp.tool()
def get_parameter_combination(run_id: int, module_type: str = "3d"):
    """获取指定运行 ID 对应的参数组合"""
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        params = result_module.get_parameter_combination(run_id)
        return {
            "status": "success",
            "run_id": run_id,
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "parameters": _serialize_value(params),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取参数组合失败: {str(e)}"}


@mcp.tool()
def get_1d_result(
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
    export_path: str = "",
):
    """获取 0D/1D 结果数据

    对应 cst.results.ResultModule.get_result_item(treepath, run_id, load_impedances)。
    兼容 0D 结果、普通 1D 结果和带参考阻抗的结果。

    参数：
    - treepath: 结果树路径
    - module_type: 模块类型，"3d" 或 "schematic"，默认 "3d"
    - run_id: 运行 ID，默认 0
    - load_impedances: 是否加载参考阻抗，默认 True
    - export_path: 导出文件路径（仅支持 .json）。不提供时自动导出到默认目录。
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        result_item = result_module.get_result_item(
            treepath,
            run_id=run_id,
            load_impedances=load_impedances,
        )

        xdata = result_item.get_xdata()
        ydata = result_item.get_ydata()
        # Local-export-only mode: never return raw arrays to the model.
        if export_path:
            export_file = Path(export_path)
            if export_file.suffix.lower() != ".json":
                return {
                    "status": "error",
                    "message": (
                        f"get_1d_result 的导出仅支持 .json，当前为: {export_file.suffix or '(无扩展名)'}"
                    ),
                }
            export_file.parent.mkdir(parents=True, exist_ok=True)
            export_file = export_file.resolve()
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_file = (
                _default_plot_dir() / f"result_1d_run{run_id}_{timestamp}.json"
            ).resolve()

        with export_file.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "treepath": result_item.treepath,
                    "title": result_item.title,
                    "xlabel": result_item.xlabel,
                    "ylabel": result_item.ylabel,
                    "length": result_item.length,
                    "run_id": result_item.run_id,
                    "parameter_combination": _serialize_value(
                        result_item.get_parameter_combination()
                    ),
                    "xdata": _serialize_value(xdata),
                    "ydata": _serialize_value(ydata),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return {
            "status": "success",
            "mode": "local_export_only",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": result_item.treepath,
            "run_id": result_item.run_id,
            "point_count": len(xdata),
            "export_path": str(export_file),
            "message": f"1D 结果已导出到本地文件: {export_file}",
        }
    except Exception as e:
        return {"status": "error", "message": f"获取 0D/1D 结果失败: {str(e)}"}


@mcp.tool()
def get_2d_result(
    treepath: str,
    module_type: str = "3d",
    include_data: bool = False,
    export_path: str = "",
):
    """获取 2D 结果数据（colormap）

    参数:
    - treepath: 结果树路径
    - module_type: 模块类型，"3d" 或 "schematic"
    - include_data: 兼容保留参数，已忽略（始终本地导出，不直返矩阵）
    - export_path: 导出文件路径（仅支持 .json）。不提供时自动导出到默认目录。
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        result_2d = result_module.get_result2d_item(treepath)
        # Local-export-only mode: never return 2D matrix payload directly.
        if export_path:
            export_file = Path(export_path)
            if export_file.suffix.lower() != ".json":
                return {
                    "status": "error",
                    "message": (
                        f"get_2d_result 的导出仅支持 .json，当前为: {export_file.suffix or '(无扩展名)'}"
                    ),
                }
            export_file.parent.mkdir(parents=True, exist_ok=True)
            export_file = export_file.resolve()
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_file = (
                _default_plot_dir()
                / f"result_2d_{result_2d.ny}x{result_2d.nx}_{timestamp}.json"
            ).resolve()

        with export_file.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "treepath": treepath,
                    "title": result_2d.title,
                    "xlabel": result_2d.xlabel,
                    "ylabel": result_2d.ylabel,
                    "xunit": result_2d.xunit,
                    "yunit": result_2d.yunit,
                    "dataunit": result_2d.dataunit,
                    "xmin": result_2d.xmin,
                    "xmax": result_2d.xmax,
                    "ymin": result_2d.ymin,
                    "ymax": result_2d.ymax,
                    "nx": result_2d.nx,
                    "ny": result_2d.ny,
                    "xpositions": _serialize_value(result_2d.get_xpositions()),
                    "ypositions": _serialize_value(result_2d.get_ypositions()),
                    "data": _serialize_value(result_2d.get_data()),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return {
            "status": "success",
            "mode": "local_export_only",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath,
            "nx": result_2d.nx,
            "ny": result_2d.ny,
            "export_path": str(export_file),
            "message": f"2D 结果已导出到本地文件: {export_file}",
            "include_data_ignored": bool(include_data),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取 2D 结果失败: {str(e)}"}


@mcp.tool()
def plot_project_result(
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
    output_html: str = "",
    page_title: str = "",
):
    """从当前项目直接生成结果预览 HTML

    功能：
    - 自动识别 treepath 是 1D 结果还是 2D 结果
    - 1D 结果生成单点/曲线/实部虚部/幅值dB/相位图
    - 2D 结果生成热图、等值线、中心切片和 3D 表面预览
    - 输出交互式 HTML，便于在 WorkBuddy / 浏览器中查看

    参数：
    - treepath: 结果树路径
    - module_type: "3d" 或 "schematic"
    - run_id: 1D 结果所用 run id，默认 0
    - load_impedances: 1D 结果是否附带参考阻抗
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则自动使用结果标题
    """
    try:
        payload, detected_kind, normalized_module, context = (
            _fetch_plot_payload_from_project(
                treepath=treepath,
                module_type=module_type,
                run_id=run_id,
                load_impedances=load_impedances,
            )
        )
        final_title = (
            page_title or payload.get("title") or f"CST Result Preview - {treepath}"
        )
        html_content, rendered_kind = _build_plot_html_from_payload(
            payload, final_title
        )
        target = _ensure_plot_output_path(output_html, prefix="project_result")
        target.write_text(html_content, encoding="utf-8")

        return {
            "status": "success",
            "source": "project_result",
            "detected_kind": detected_kind,
            "rendered_kind": rendered_kind,
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath,
            "run_id": run_id,
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成项目结果预览失败: {str(e)}"}


@mcp.tool()
def plot_exported_file(file_path: str, output_html: str = "", page_title: str = ""):
    """将导出的结果文件渲染为交互式 HTML 预览

    支持场景：
    - 导出的 CSV / TXT 两列曲线文件
    - 导出的矩阵型文本文件（按规则自动识别为热图）
    - 已整理成 JSON 的 xdata/ydata 或二维 data 数据

    参数：
    - file_path: 导出文件路径
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则自动使用文件名或数据标题
    """
    try:
        payload = _load_exported_payload(file_path)
        payload_title = payload.get("title") if isinstance(payload, dict) else None
        final_title = (
            page_title or payload_title or f"Export Preview - {Path(file_path).name}"
        )
        html_content, rendered_kind = _build_plot_html_from_payload(
            payload, final_title
        )
        target = _ensure_plot_output_path(output_html, prefix="export_preview")
        target.write_text(html_content, encoding="utf-8")

        return {
            "status": "success",
            "source": "exported_file",
            "file_path": str(Path(file_path).resolve()),
            "rendered_kind": rendered_kind,
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成导出文件预览失败: {str(e)}"}


@mcp.tool()
def plot_farfield_multi(
    file_paths: list[str], output_html: str = "", page_title: str = ""
):
    """将多个 CST farfield ASCII 导出文件渲染为多频率交互式 HTML 预览

    参数：
    - file_paths: 多个 farfield ASCII 文件路径列表
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则默认使用“Farfield Multi-Frequency Preview"
    """
    try:
        if not file_paths:
            raise ValueError("file_paths 不能为空")
        items = _load_farfield_payloads(file_paths)
        final_title = page_title or "Farfield Multi-Frequency Preview"
        html_content = _create_farfield_multi_plot_html(items, final_title)
        target = _ensure_plot_output_path(output_html, prefix="farfield_multi")
        target.write_text(html_content, encoding="utf-8")
        return {
            "status": "success",
            "source": "farfield_multi",
            "file_count": len(items),
            "file_paths": [str(Path(p).resolve()) for p in file_paths],
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成多频率远场预览失败: {str(e)}"}


@mcp.tool()
def calculate_farfield_neighborhood_flatness(
    file_paths: list[str], theta_max_deg: float = 15.0, output_json: str = ""
):
    """计算 farfield cut 在法向邻域内的增益平坦度。

    当前仅支持 farfield cut JSON 输入，要求文件包含：
    - angle_deg
    - primary_db

    指标定义：
    - 在 0 <= theta <= theta_max_deg 范围内计算 max(gain) - min(gain)

    参数：
    - file_paths: 一个或多个 farfield cut JSON 文件路径
    - theta_max_deg: 法向邻域半角，默认 15 度
    - output_json: 可选，若提供则将计算结果写入 JSON 文件
    """
    try:
        if not file_paths:
            raise ValueError("file_paths 不能为空")
        if theta_max_deg <= 0:
            raise ValueError("theta_max_deg 必须大于 0")

        per_file = [
            _evaluate_farfield_cut_neighborhood_flatness(
                _parse_farfield_cut_payload(file_path), theta_max_deg
            )
            for file_path in file_paths
        ]
        grouped_summary = _group_farfield_cut_flatness(per_file)
        result = {
            "status": "success",
            "theta_max_deg": float(theta_max_deg),
            "file_count": len(per_file),
            "per_file": per_file,
            "grouped_summary": grouped_summary,
        }

        if output_json:
            target = Path(output_json).expanduser()
            if not target.is_absolute():
                target = (Path.cwd() / target).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result["output_json"] = str(target)

        return result
    except Exception as e:
        return {"status": "error", "message": f"计算邻域平坦度失败: {str(e)}"}


@mcp.tool()
def read_realized_gain_grid_fresh_session(
    project_path: str,
    farfield_name: str,
    run_id: int | None = None,
    theta_step_deg: float = 1.0,
    phi_step_deg: float = 2.0,
    theta_min_deg: float | None = None,
    theta_max_deg: float | None = None,
    phi_min_deg: float | None = None,
    phi_max_deg: float | None = None,
    selection_tree_path: str = "1D Results\\S-Parameters",
    output_json: str = "",
):
    """按 fresh CST session 读取真实 Realized Gain(dBi) 网格与峰值。

    底层使用 FarfieldCalculator，直接读取 CST farfield 结果中的
    Realized Gain，不再复用 Abs(E) 代理链。
    """
    normalized_project = os.path.abspath(project_path)
    if not normalized_project.lower().endswith(".cst"):
        normalized_project += ".cst"
    if not os.path.isfile(normalized_project):
        return {"status": "error", "message": f"项目文件不存在: {normalized_project}"}

    normalized_output_json = ""
    if output_json:
        target = Path(output_json).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized_output_json = str(target)

    flow_log = []
    close_results = _close_results_context_if_matches(normalized_project)
    if close_results is not None:
        flow_log.append({"step": "close_results_context", "result": close_results})

    start_quit = _kill_cst_processes()
    flow_log.append({"step": "quit_before_open", "result": start_quit})
    if start_quit.get("status") != "success":
        return {
            "status": "error",
            "message": "读取前清理 CST 进程失败",
            "flow_log": flow_log,
        }

    open_result = _gui_open_project(normalized_project)
    flow_log.append(
        {
            "step": "open_project",
            "result": {
                k: v
                for k, v in open_result.items()
                if k not in {"project", "design_environment"}
            },
        }
    )
    if open_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"打开项目失败: {normalized_project}",
            "flow_log": flow_log,
        }

    project = open_result["project"]
    try:
        if run_id is not None:
            selection_result = _gui_set_result_navigator_selection(
                project=project,
                run_ids=[int(run_id)],
                selection_tree_path=selection_tree_path,
            )
            flow_log.append(
                {"step": "set_result_navigator_selection", "result": selection_result}
            )
            if selection_result.get("status") != "success":
                return {
                    "status": "error",
                    "message": selection_result.get(
                        "message", f"Result Navigator run_id={run_id} 切换失败"
                    ),
                    "flow_log": flow_log,
                    "project_path": normalized_project,
                    "farfield_name": farfield_name,
                    "run_id": int(run_id),
                    "selection_tree_path": selection_tree_path,
                }

        read_result = _read_realized_gain_grid_via_calculator(
            project=project,
            farfield_name=farfield_name,
            theta_step_deg=theta_step_deg,
            phi_step_deg=phi_step_deg,
            theta_min_deg=theta_min_deg,
            theta_max_deg=theta_max_deg,
            phi_min_deg=phi_min_deg,
            phi_max_deg=phi_max_deg,
        )
        flow_log.append({"step": "read_realized_gain", "result": read_result})
        if read_result.get("status") != "success":
            return {
                "status": "error",
                "message": read_result.get("message", "Realized Gain 读取失败"),
                "flow_log": flow_log,
                "project_path": normalized_project,
                "farfield_name": farfield_name,
            }

        result = {
            "status": "success",
            "project_path": normalized_project,
            "farfield_name": farfield_name,
            "run_id": None if run_id is None else int(run_id),
            "selection_tree_path": selection_tree_path if run_id is not None else None,
            "source": read_result["source"],
            "quantity": read_result["quantity"],
            "unit": read_result["unit"],
            "tree_path": read_result["tree_path"],
            "frequency_ghz": read_result["frequency_ghz"],
            "theta_step_deg": float(theta_step_deg),
            "phi_step_deg": float(phi_step_deg),
            "theta_min_deg": 0.0 if theta_min_deg is None else float(theta_min_deg),
            "theta_max_deg": (
                180.0 if theta_max_deg is None else float(theta_max_deg)
            ),
            "phi_min_deg": 0.0 if phi_min_deg is None else float(phi_min_deg),
            "phi_max_deg": 360.0 if phi_max_deg is None else float(phi_max_deg),
            "theta_count": len(read_result["theta_values_deg"]),
            "phi_count": len(read_result["phi_values_deg"]),
            "sample_count": read_result["sample_count"],
            "peak_realized_gain_dbi": read_result["peak_realized_gain_dbi"],
            "peak_theta_deg": read_result["peak_theta_deg"],
            "peak_phi_deg": read_result["peak_phi_deg"],
            "boresight_realized_gain_dbi": read_result[
                "boresight_realized_gain_dbi"
            ],
            "flow_log": flow_log,
            "message": f"已按 fresh session 读取 Realized Gain: {farfield_name}",
        }

        if normalized_output_json:
            payload = {
                **result,
                "theta_values_deg": read_result["theta_values_deg"],
                "phi_values_deg": read_result["phi_values_deg"],
                "grid_db": read_result["grid_db"],
            }
            Path(normalized_output_json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["output_json"] = normalized_output_json

        return result
    finally:
        if run_id is not None:
            reset_result = _gui_set_result_navigator_selection(
                project=project,
                run_ids=None,
                selection_tree_path=selection_tree_path,
            )
            flow_log.append(
                {"step": "reset_result_navigator_selection", "result": reset_result}
            )
        close_result = _gui_close_project(project, normalized_project, save=False)
        flow_log.append({"step": "close_project", "result": close_result})
        end_quit = _kill_cst_processes()
        flow_log.append({"step": "quit_after_close", "result": end_quit})


@mcp.tool()
def generate_s11_comparison(
    file_paths: list[str],
    output_html: str = "",
    page_title: str = "",
):
    """生成多个 S11 文件的对比图

    读取多个 S11 JSON 数据文件，生成统一对比的交互式 HTML 页面。

    参数：
    - file_paths: S11 数据文件路径列表（仅支持 .json），按顺序对应 Series 1, Series 2, ...
    - output_html: 输出 HTML 路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；默认 "S11 Comparison"

    页面内容：
    - 多条 S11 曲线叠加对比
    - 可选择频点，查看不同 run_id 在该频点下的 S11 变化折线
    - Summary 表格：run_id、文件名、最小 S11、最佳频率
    """
    try:
        if not file_paths:
            raise ValueError("file_paths 不能为空")

        all_series: list[dict[str, Any]] = []
        for idx, file_path in enumerate(file_paths):
            if Path(file_path).suffix.lower() != ".json":
                raise ValueError(
                    f"generate_s11_comparison 仅支持 .json 输入，检测到: {file_path}"
                )
            payload = _load_exported_payload(file_path)

            # 提取频率和幅值数据
            xdata = payload.get("xdata", [])
            ydata = payload.get("ydata", [])

            if not xdata or not ydata:
                raise ValueError(f"文件缺少有效 xdata/ydata: {file_path}")

            # 计算 dB 值
            mag_db_values: list[float | None] = []
            for y_val in ydata:
                real, imag = _complex_components(y_val)
                mag = math.hypot(real, imag)
                mag_db_values.append(_safe_log_db(mag))

            # 转换为有限值，-120 代表无效
            finite_db = [(v if v is not None else -120.0) for v in mag_db_values]

            # 找到最小 dB（最佳匹配）和对应频率
            valid_db = [v for v in finite_db if v > -120]
            min_db = min(valid_db) if valid_db else -120.0
            min_idx = next(i for i, v in enumerate(finite_db) if v == min_db)
            best_freq = xdata[min_idx] if min_idx < len(xdata) else None
            best_freq_unit = "GHz" if best_freq and best_freq > 0.1 else ""
            payload_run_id = payload.get("run_id")
            if payload_run_id is None:
                match = re.search(r"run[_-]?(\d+)", Path(file_path).stem, re.IGNORECASE)
                payload_run_id = int(match.group(1)) if match else idx + 1

            all_series.append(
                {
                    "label": f"Run {payload_run_id}",
                    "run_id": payload_run_id,
                    "file": str(Path(file_path).name),
                    "full_file": str(Path(file_path).resolve()),
                    "xdata": xdata,
                    "ydata": finite_db,
                    "min_db": min_db,
                    "best_freq": best_freq,
                    "best_unit": best_freq_unit,
                }
            )

        # 构造 HTML
        final_title = page_title or "S11 Comparison"
        reference_xdata = all_series[0]["xdata"]
        if not reference_xdata:
            raise ValueError("缺少可用的频率点数据")

        # 计算全局 dB 范围
        all_db = [s["ydata"] for s in all_series]
        global_min = min(min(s) for s in all_db) - 3
        global_max = max(max(s) for s in all_db) + 3

        series_json = _json_dumps(all_series)
        frequencies_json = _json_dumps(reference_xdata)

        script = f"""
const series = {series_json};
const frequencies = {frequencies_json};
const globalMin = {global_min};
const globalMax = {global_max};
const initialFreqIndex = Math.max(0, Math.min(frequencies.length - 1, Math.floor(frequencies.length / 2)));

const palette = ['#38bdf8','#f59e0b','#22c55e','#ef4444','#a78bfa','#f472b6','#14b8a6','#eab308'];
const traces = series.map((s, i) => ({{
  x: s.xdata,
  y: s.ydata,
  type: 'scatter',
  mode: 'lines',
  name: s.label,
  line: {{width: 2, color: palette[i % palette.length]}}
}}));

Plotly.newPlot('plot_main', traces, {{
  template: 'plotly_dark',
  title: 'S11 Comparison',
  xaxis: {{title: 'Frequency (GHz)'}},
  yaxis: {{title: 'S11 (dB)', range: [globalMin, globalMax]}},
  hovermode: 'x unified',
  legend: {{orientation: 'h', y: 1.12}},
  paper_bgcolor: '#1f2937',
  plot_bgcolor: '#1f2937'
}}, {{responsive: true, displaylogo: false}});

const freqSelect = document.getElementById('freq_select');
const selectedFreqText = document.getElementById('selected_freq');
const trendMeta = document.getElementById('trend_meta');

function nearestIndex(values, target) {{
  let bestIndex = 0;
  let bestDelta = Infinity;
  values.forEach((value, index) => {{
    const delta = Math.abs(value - target);
    if (delta < bestDelta) {{
      bestDelta = delta;
      bestIndex = index;
    }}
  }});
  return bestIndex;
}}

function buildTrendSeries(targetFreq) {{
  const sorted = [...series].sort((left, right) => Number(left.run_id) - Number(right.run_id));
  return sorted.map((item, index) => {{
    const pointIndex = nearestIndex(item.xdata, targetFreq);
    return {{
      runId: item.run_id,
      label: item.label,
      file: item.file,
      freq: item.xdata[pointIndex],
      s11: item.ydata[pointIndex],
      color: palette[index % palette.length],
    }};
  }});
}}

function renderTrendChart(targetFreq) {{
  const trend = buildTrendSeries(targetFreq);
  const trendTrace = {{
    x: trend.map(item => item.runId),
    y: trend.map(item => item.s11),
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Selected Frequency',
    line: {{width: 3, color: '#f97316'}},
    marker: {{
      size: 10,
      color: trend.map(item => item.color),
      line: {{color: '#0f172a', width: 1}}
    }},
    customdata: trend.map(item => [item.label, item.file, item.freq]),
    hovertemplate: 'Run %{{x}}<br>S11: %{{y:.2f}} dB<br>Series: %{{customdata[0]}}<br>File: %{{customdata[1]}}<br>Actual Freq: %{{customdata[2]:.3f}} GHz<extra></extra>'
  }};

  Plotly.newPlot('plot_trend', [trendTrace], {{
    template: 'plotly_dark',
    title: `S11 vs Run ID @ ${{targetFreq.toFixed(3)}} GHz`,
    xaxis: {{title: 'Run ID', dtick: 1}},
    yaxis: {{title: 'S11 (dB)', range: [globalMin, globalMax]}},
    hovermode: 'closest',
    paper_bgcolor: '#1f2937',
    plot_bgcolor: '#1f2937'
  }}, {{responsive: true, displaylogo: false}});

  const bestPoint = trend.reduce((best, item) => item.s11 < best.s11 ? item : best, trend[0]);
  selectedFreqText.textContent = `${{targetFreq.toFixed(3)}} GHz`;
  trendMeta.textContent = `当前频点最优 run: ${{bestPoint.runId}}，S11 = ${{bestPoint.s11.toFixed(2)}} dB`;
}}

frequencies.forEach((freq, index) => {{
  const option = document.createElement('option');
  option.value = String(index);
  option.textContent = `${{freq.toFixed(3)}} GHz`;
  freqSelect.appendChild(option);
}});
freqSelect.value = String(initialFreqIndex);
freqSelect.addEventListener('change', (event) => {{
  const selectedIndex = Number(event.target.value);
  renderTrendChart(frequencies[selectedIndex]);
}});
renderTrendChart(frequencies[initialFreqIndex]);

const summaryHtml = '<table class="summary-table"><thead><tr><th>Run ID</th><th>Series</th><th>File</th><th>Min S11 (dB)</th><th>Best Freq</th></tr></thead><tbody>'
  + [...series].sort((left, right) => Number(left.run_id) - Number(right.run_id)).map(s => `<tr><td>${{s.run_id}}</td><td>${{s.label}}</td><td>${{s.file}}</td><td>${{s.min_db.toFixed(2)}}</td><td>${{s.best_freq ? s.best_freq.toFixed(3) + ' ' + s.best_unit : '-'}}</td></tr>`).join('')
  + '</tbody></table>';
document.getElementById('summary').innerHTML = summaryHtml;
"""

        body = """
    <style>
      .toolbar { display:flex; flex-wrap:wrap; gap:14px; align-items:end; margin-bottom:14px; }
      .control { min-width:220px; }
      .control label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px; }
      .control select {
        width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
        background:var(--panel-2); color:var(--text); font-size:14px;
      }
      .metric {
        min-width:220px; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
        background:var(--panel-2);
      }
      .metric .metric-label { color:var(--muted); font-size:12px; margin-bottom:4px; }
      .metric .metric-value { font-size:20px; font-weight:700; }
      .metric .metric-note { color:var(--muted); font-size:12px; margin-top:4px; }
      .summary-table { width:100%; border-collapse:collapse; }
      .summary-table th, .summary-table td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; font-size:13px; }
      .summary-table th { color:var(--muted); font-weight:600; }
    </style>
    <div class="header">
      <div class="title">S11 Comparison</div>
      <div class="subtitle">多 S11 曲线对比，并按指定频点查看不同 run_id 的 S11 变化</div>
    </div>
    <div class="section">
      <h2>S11 曲线对比</h2>
      <div id="plot_main" class="plot"></div>
    </div>
    <div class="section">
      <h2>频点趋势</h2>
      <div class="toolbar">
        <div class="control">
          <label for="freq_select">选择频点</label>
          <select id="freq_select"></select>
        </div>
        <div class="metric">
          <div class="metric-label">当前频点</div>
          <div id="selected_freq" class="metric-value">-</div>
          <div id="trend_meta" class="metric-note">-</div>
        </div>
      </div>
      <div id="plot_trend" class="plot small"></div>
    </div>
    <div class="section">
      <h2>Summary</h2>
      <div id="summary"></div>
    </div>
    """

        html_content = _html_template(final_title, body, script)
        target = _ensure_plot_output_path(output_html, prefix="s11_comparison")
        target.write_text(html_content, encoding="utf-8")

        return {
            "status": "success",
            "series_count": len(all_series),
            "frequency_count": len(reference_xdata),
            "file_paths": [str(Path(p).resolve()) for p in file_paths],
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成 S11 对比失败: {str(e)}"}


def _create_s11_farfield_dashboard_html(
    s11_series: list[dict[str, Any]],
    farfield_runs: list[dict[str, Any]],
    page_title: str,
    initial_farfield_run_id: int | None,
) -> str:
    reference_xdata = s11_series[0]["xdata"]
    global_min = min(min(series["ydata"]) for series in s11_series) - 3
    global_max = max(max(series["ydata"]) for series in s11_series) + 3
    selected_run_id = initial_farfield_run_id or farfield_runs[0]["run_id"]

    body = """
    <style>
      .toolbar { display:flex; flex-wrap:wrap; gap:14px; align-items:end; margin-bottom:14px; }
      .control { min-width:220px; }
      .control label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px; }
      .control select {
        width:100%; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
        background:var(--panel-2); color:var(--text); font-size:14px;
      }
      .metric {
        min-width:220px; padding:10px 12px; border-radius:10px; border:1px solid var(--line);
        background:var(--panel-2);
      }
      .metric .metric-label { color:var(--muted); font-size:12px; margin-bottom:4px; }
      .metric .metric-value { font-size:20px; font-weight:700; }
      .metric .metric-note { color:var(--muted); font-size:12px; margin-top:4px; }
      .summary-table { width:100%; border-collapse:collapse; }
      .summary-table th, .summary-table td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; font-size:13px; }
      .summary-table th { color:var(--muted); font-weight:600; }
    </style>
    <div class="header">
      <div class="title">S11 + Farfield Dashboard</div>
      <div class="subtitle">S 曲线与 3D 方向图合并展示；方向图 run 通过参数或页面控件手动指定，不与 S11 结果绑定。</div>
    </div>
    <div class="section">
      <h2>S11 曲线对比</h2>
      <div id="plot_main" class="plot"></div>
    </div>
    <div class="section">
      <h2>S11 频点趋势</h2>
      <div class="toolbar">
        <div class="control">
          <label for="freq_select">选择频点</label>
          <select id="freq_select"></select>
        </div>
        <div class="metric">
          <div class="metric-label">当前频点</div>
          <div id="selected_freq" class="metric-value">-</div>
          <div id="trend_meta" class="metric-note">-</div>
        </div>
      </div>
      <div id="plot_trend" class="plot small"></div>
    </div>
    <div class="section">
      <h2>方向图展示</h2>
      <div class="toolbar">
        <div class="control">
          <label for="farfield_run_select">选择方向图 Run</label>
          <select id="farfield_run_select"></select>
        </div>
        <div class="control">
          <label for="farfield_freq_select">选择方向图频点</label>
          <select id="farfield_freq_select"></select>
        </div>
        <div class="metric">
          <div class="metric-label">当前方向图</div>
          <div id="farfield_run_label" class="metric-value">-</div>
          <div id="farfield_file_hint" class="metric-note">-</div>
        </div>
      </div>
      <div class="grid-2">
        <div class="section">
          <h2>3D 方向图</h2>
          <div id="plot_surface3d" class="plot"></div>
        </div>
        <div class="section">
          <h2>主平面切面（Phi = 0° / 90°）</h2>
          <div id="plot_single_cuts" class="plot"></div>
        </div>
      </div>
    </div>
    <div class="section">
      <h2>S11 Summary</h2>
      <div id="summary"></div>
    </div>
    """

    script = f"""
const s11Series = {_json_dumps(s11_series)};
const farfieldRuns = {_json_dumps(farfield_runs)};
const frequencies = {_json_dumps(reference_xdata)};
const globalMin = {global_min};
const globalMax = {global_max};
const initialFarfieldRunId = {selected_run_id};
const initialFreqIndex = Math.max(0, Math.min(frequencies.length - 1, Math.floor(frequencies.length / 2)));
const palette = ['#38bdf8','#f59e0b','#22c55e','#ef4444','#a78bfa','#f472b6','#14b8a6','#eab308'];

function buildFarfieldCartesian(thetaDeg, phiDeg, radiusMatrix) {{
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < phiDeg.length; i++) {{
    const xr = [];
    const yr = [];
    const zr = [];
    for (let j = 0; j < thetaDeg.length; j++) {{
      const theta = thetaDeg[j] * Math.PI / 180.0;
      const phi = phiDeg[i] * Math.PI / 180.0;
      const r = radiusMatrix[i][j];
      xr.push(r * Math.sin(theta) * Math.cos(phi));
      yr.push(r * Math.sin(theta) * Math.sin(phi));
      zr.push(r * Math.cos(theta));
    }}
    xs.push(xr);
    ys.push(yr);
    zs.push(zr);
  }}
  return {{x: xs, y: ys, z: zs}};
}}

const s11Traces = s11Series.map((item, index) => ({{
  x: item.xdata,
  y: item.ydata,
  type: 'scatter',
  mode: 'lines',
  name: item.label,
  line: {{width: 2, color: palette[index % palette.length]}}
}}));

Plotly.newPlot('plot_main', s11Traces, {{
  template: 'plotly_dark',
  title: 'S11 Comparison',
  xaxis: {{title: 'Frequency (GHz)'}},
  yaxis: {{title: 'S11 (dB)', range: [globalMin, globalMax]}},
  hovermode: 'x unified',
  legend: {{orientation: 'h', y: 1.12}},
  paper_bgcolor: '#1f2937',
  plot_bgcolor: '#1f2937'
}}, {{responsive: true, displaylogo: false}});

const freqSelect = document.getElementById('freq_select');
const selectedFreqText = document.getElementById('selected_freq');
const trendMeta = document.getElementById('trend_meta');
const farfieldRunSelect = document.getElementById('farfield_run_select');
const farfieldFreqSelect = document.getElementById('farfield_freq_select');
const farfieldRunLabel = document.getElementById('farfield_run_label');
const farfieldFileHint = document.getElementById('farfield_file_hint');

function nearestIndex(values, target) {{
  let bestIndex = 0;
  let bestDelta = Infinity;
  values.forEach((value, index) => {{
    const delta = Math.abs(value - target);
    if (delta < bestDelta) {{
      bestDelta = delta;
      bestIndex = index;
    }}
  }});
  return bestIndex;
}}

function renderTrendChart(targetFreq) {{
  const trend = [...s11Series]
    .sort((left, right) => Number(left.run_id) - Number(right.run_id))
    .map((item, index) => {{
      const pointIndex = nearestIndex(item.xdata, targetFreq);
      return {{
        runId: item.run_id,
        label: item.label,
        file: item.file,
        freq: item.xdata[pointIndex],
        s11: item.ydata[pointIndex],
        color: palette[index % palette.length],
      }};
    }});

  Plotly.newPlot('plot_trend', [{{
    x: trend.map(item => item.runId),
    y: trend.map(item => item.s11),
    type: 'scatter',
    mode: 'lines+markers',
    line: {{width: 3, color: '#f97316'}},
    marker: {{
      size: 10,
      color: trend.map(item => item.color),
      line: {{color: '#0f172a', width: 1}}
    }},
    customdata: trend.map(item => [item.label, item.file, item.freq]),
    hovertemplate: 'Run %{{x}}<br>S11: %{{y:.2f}} dB<br>Series: %{{customdata[0]}}<br>File: %{{customdata[1]}}<br>Actual Freq: %{{customdata[2]:.3f}} GHz<extra></extra>'
  }}], {{
    template: 'plotly_dark',
    title: `S11 vs Run ID @ ${{targetFreq.toFixed(3)}} GHz`,
    xaxis: {{title: 'Run ID', dtick: 1}},
    yaxis: {{title: 'S11 (dB)', range: [globalMin, globalMax]}},
    hovermode: 'closest',
    paper_bgcolor: '#1f2937',
    plot_bgcolor: '#1f2937'
  }}, {{responsive: true, displaylogo: false}});

  const bestPoint = trend.reduce((best, item) => item.s11 < best.s11 ? item : best, trend[0]);
  selectedFreqText.textContent = `${{targetFreq.toFixed(3)}} GHz`;
  trendMeta.textContent = `当前频点最优 run: ${{bestPoint.runId}}，S11 = ${{bestPoint.s11.toFixed(2)}} dB`;
}}

function renderFarfieldItem(item, runLabel) {{
  const ff = buildFarfieldCartesian(item.theta, item.phi, item.radius);
  Plotly.newPlot('plot_surface3d', [{{
    x: ff.x,
    y: ff.y,
    z: ff.z,
    surfacecolor: item.surface_color,
    type: 'surface',
    colorscale: 'Jet',
    cmin: item.min_db,
    cmax: item.max_db,
    colorbar: {{title: 'Norm dB'}}
  }}], {{
    template: 'plotly_dark',
    title: `${{runLabel}} · ${{item.label}} · 3D Polar Farfield`,
    scene: {{
      xaxis: {{title: 'X'}},
      yaxis: {{title: 'Y'}},
      zaxis: {{title: 'Z'}},
      aspectmode: 'data',
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});

  const cutTraces = item.cuts.map((cut, index) => ({{
    x: cut.theta,
    y: cut.gain_db,
    type: 'scatter',
    mode: 'lines',
    name: `Phi=${{cut.phi}}°`,
    line: {{width: 2.5, color: index === 0 ? '#38bdf8' : '#f59e0b'}}
  }}));
  Plotly.newPlot('plot_single_cuts', cutTraces, {{
    template: 'plotly_dark',
    title: `${{runLabel}} · ${{item.label}} · Main Cuts`,
    xaxis: {{title: 'Theta (deg)'}},
    yaxis: {{title: 'Norm Gain (dB)'}},
    hovermode: 'x unified',
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});

  farfieldRunLabel.textContent = `${{runLabel}} / ${{item.label}}`;
  farfieldFileHint.textContent = item.file;
}}

function renderFarfieldRun(runId) {{
  const run = farfieldRuns.find(item => Number(item.run_id) === Number(runId));
  if (!run) {{
    return;
  }}
  farfieldFreqSelect.innerHTML = '';
  run.items.forEach((item, index) => {{
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = item.label;
    farfieldFreqSelect.appendChild(option);
  }});
  farfieldFreqSelect.value = '0';
  renderFarfieldItem(run.items[0], run.label);
}}

frequencies.forEach((freq, index) => {{
  const option = document.createElement('option');
  option.value = String(index);
  option.textContent = `${{freq.toFixed(3)}} GHz`;
  freqSelect.appendChild(option);
}});
freqSelect.value = String(initialFreqIndex);
freqSelect.addEventListener('change', event => {{
  renderTrendChart(frequencies[Number(event.target.value)]);
}});
renderTrendChart(frequencies[initialFreqIndex]);

farfieldRuns.forEach(run => {{
  const option = document.createElement('option');
  option.value = String(run.run_id);
  option.textContent = run.label;
  farfieldRunSelect.appendChild(option);
}});
farfieldRunSelect.value = String(initialFarfieldRunId);
farfieldRunSelect.addEventListener('change', event => {{
  renderFarfieldRun(Number(event.target.value));
}});
farfieldFreqSelect.addEventListener('change', event => {{
  const run = farfieldRuns.find(item => Number(item.run_id) === Number(farfieldRunSelect.value));
  if (!run) {{
    return;
  }}
  renderFarfieldItem(run.items[Number(event.target.value)], run.label);
}});
renderFarfieldRun(initialFarfieldRunId);

const summaryHtml = '<table class="summary-table"><thead><tr><th>Run ID</th><th>Series</th><th>File</th><th>Min S11 (dB)</th><th>Best Freq</th></tr></thead><tbody>'
  + [...s11Series].sort((left, right) => Number(left.run_id) - Number(right.run_id)).map(item => `<tr><td>${{item.run_id}}</td><td>${{item.label}}</td><td>${{item.file}}</td><td>${{item.min_db.toFixed(2)}}</td><td>${{item.best_freq ? item.best_freq.toFixed(3) + ' ' + item.best_unit : '-'}}</td></tr>`).join('')
  + '</tbody></table>';
document.getElementById('summary').innerHTML = summaryHtml;
"""
    return _html_template(page_title, body, script)


@mcp.tool()
def generate_s11_farfield_dashboard(
    s11_file_paths: list[str],
    farfield_file_paths: list[str],
    output_html: str = "",
    page_title: str = "",
    farfield_run_id: int = 0,
):
    """生成 S11 曲线与 3D 方向图合并页面。

    参数：
    - s11_file_paths: S11 JSON 文件列表
    - farfield_file_paths: farfield ASCII/TXT 文件列表
    - output_html: 输出 HTML 路径；为空则自动输出到默认目录
    - page_title: 页面标题
    - farfield_run_id: 手动指定方向图使用的 run_id；0 表示默认使用文件列表中的第一个 run
    """
    try:
        if not s11_file_paths:
            raise ValueError("s11_file_paths 不能为空")
        if not farfield_file_paths:
            raise ValueError("farfield_file_paths 不能为空")

        s11_series = _build_s11_series(s11_file_paths)
        farfield_runs = _group_farfield_items_by_run(farfield_file_paths)
        selected_run_id = farfield_run_id if farfield_run_id > 0 else farfield_runs[0]["run_id"]
        if selected_run_id not in {item["run_id"] for item in farfield_runs}:
            raise ValueError(f"farfield_run_id={selected_run_id} 不在提供的方向图文件列表中")

        final_title = page_title or "S11 + Farfield Dashboard"
        html_content = _create_s11_farfield_dashboard_html(
            s11_series=s11_series,
            farfield_runs=farfield_runs,
            page_title=final_title,
            initial_farfield_run_id=selected_run_id,
        )
        target = _ensure_plot_output_path(output_html, prefix="s11_farfield_dashboard")
        target.write_text(html_content, encoding="utf-8")
        return {
            "status": "success",
            "s11_series_count": len(s11_series),
            "farfield_run_count": len(farfield_runs),
            "selected_farfield_run_id": selected_run_id,
            "output_html": str(target),
            "page_title": final_title,
        }
    except Exception as e:
        return {"status": "error", "message": f"生成 S11/方向图合并页面失败: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
