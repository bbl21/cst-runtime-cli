"""Core screenshot capture for CST models.

Separated from modeling.py to keep capture logic independent of
session management (open/close). Caller is responsible for opening
the project and passing a valid COM project object.
"""
from __future__ import annotations

import base64
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import error_response
from .identity import infer_run_dir_from_project
from .modeling import _set_preset_view, _set_custom_view, _export_image

VALID_PRESETS = {"Front", "Back", "Top", "Bottom", "Left", "Right", "Isometric"}


def capture_3d_view(
    prj: Any,
    preset_name: str = "Isometric",
    output_dir: str = "",
    filename_prefix: str = "view",
    view_type: str = "preset",
    azimuth: float = 45.0,
    elevation: float = 30.0,
    zoom: float = 1.0,
    mode: str = "save",
    project_path: str = "",
    image_width: int = 1920,
    image_height: int = 1080,
) -> dict[str, Any]:
    """Capture 3D view(s) of an already-opened CST model.

    Does NOT manage session (open/close). The caller must open the
    project before calling this function.

    Single preset: returns {status, image_path, metadata_path, …}.
    Comma-separated presets: returns {multi=True, results: [{…}, …]}.

    Args:
        prj: CST COM project object (already opened).
        preset_name: Preset name or comma-separated list for batch.
        output_dir: Output directory (default: project_dir/exports/screenshots/).
        filename_prefix: Filename prefix.
        view_type: "preset" or "custom".
        azimuth: View azimuth in degrees (custom mode only).
        elevation: View elevation in degrees (custom mode only).
        zoom: Zoom scale.
        mode: "save" — save to disk (default),
              "inline" — return base64, no disk write,
              "both" — save + inline.
        project_path: Project file path (needed for default output_dir).
        image_width: Output image width in pixels (default 1920).
        image_height: Output image height in pixels (default 1080).

    Returns:
        Single preset: dict with result fields.
        Multiple presets: dict with multi=True, results list.
    """
    if prj is None:
        return error_response("invalid_project", "prj must be a valid CST project object")

    if zoom <= 0:
        return error_response("invalid_zoom", f"zoom must be > 0, got {zoom}")

    if view_type not in {"custom", "preset"}:
        return error_response("invalid_view_type", "view_type must be 'custom' or 'preset'")

    if mode not in ("save", "inline", "both"):
        return error_response("invalid_mode", "mode must be 'save', 'inline', or 'both'")

    # Determine preset list and batch flag
    presets = (
        [x.strip() for x in preset_name.split(",") if x.strip()]
        if view_type == "preset"
        else [preset_name]
    )
    is_batch = len(presets) > 1

    if view_type == "preset":
        for name in presets:
            if name not in VALID_PRESETS:
                return error_response(
                    "invalid_preset_name",
                    f"Invalid preset '{name}'; must be one of {sorted(VALID_PRESETS)}",
                )

    if not is_batch:
        return _capture_single(
            prj=prj,
            preset_name=presets[0],
            view_type=view_type,
            azimuth=azimuth,
            elevation=elevation,
            zoom=zoom,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            mode=mode,
            project_path=project_path,
            image_width=image_width,
            image_height=image_height,
        )

    # ----- batch mode -----
    out_dir = _resolve_out_dir(project_path, output_dir)
    results: list[dict[str, Any]] = []
    all_ok = True

    for name in presets:
        try:
            r = _capture_single(
                prj=prj,
                preset_name=name,
                view_type="preset",
                azimuth=azimuth,
                elevation=elevation,
                zoom=zoom,
                output_dir=str(out_dir),
                filename_prefix=f"{filename_prefix}_{name.lower()}",
                mode=mode,
                project_path=project_path,
                image_width=image_width,
                image_height=image_height,
            )
            results.append(r)
            if r.get("status") == "error":
                all_ok = False
        except Exception as e:
            all_ok = False
            results.append({"index": len(results), "status": "error", "preset_name": name, "message": str(e)})

    return {
        "status": "success" if all_ok else "partial",
        "multi": True,
        "total": len(presets),
        "success_count": sum(1 for r in results if r.get("status") == "success"),
        "error_count": sum(1 for r in results if r.get("status") == "error"),
        "output_dir": str(out_dir),
        "results": results,
        "tool": "capture-3d-view",
        "adapter": "cst_runtime_cli",
    }


def _capture_single(
    prj: Any,
    preset_name: str,
    view_type: str,
    azimuth: float,
    elevation: float,
    zoom: float,
    output_dir: str,
    filename_prefix: str,
    mode: str,
    project_path: str,
    image_width: int = 1920,
    image_height: int = 1080,
) -> dict[str, Any]:
    """Capture a single 3D view."""
    ts = datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    try:
        if view_type == "preset":
            _set_preset_view(prj, preset_name)
        else:
            _set_custom_view(prj, azimuth, elevation, zoom)
    except Exception as e:
        return error_response("set_view_failed", f"Failed to set view: {e}")

    if mode == "inline":
        return _capture_inline(prj, preset_name, view_type, azimuth, elevation, zoom, image_width, image_height)
    return _capture_disk(prj, preset_name, view_type, azimuth, elevation, zoom, output_dir, filename_prefix, mode, project_path, ts, ts_str, image_width, image_height)


def _capture_inline(
    prj: Any,
    preset_name: str,
    view_type: str,
    azimuth: float,
    elevation: float,
    zoom: float,
    image_width: int = 1920,
    image_height: int = 1080,
) -> dict[str, Any]:
    """Export to temp file, return base64, delete temp."""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        _export_image(prj, tmp_path, image_width, image_height)
        with open(tmp_path, "rb") as f:
            image_bytes = f.read()
        return {
            "status": "success",
            "image_data_base64": base64.b64encode(image_bytes).decode("ascii"),
            "image_size": {"width": image_width, "height": image_height},
            "view_type": view_type,
            "view_params": _view_params(preset_name, view_type, azimuth, elevation, zoom),
            "tool": "capture-3d-view",
            "adapter": "cst_runtime_cli",
        }
    except Exception as e:
        return error_response("export_failed", f"Failed to capture inline image: {e}")
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _capture_disk(
    prj: Any,
    preset_name: str,
    view_type: str,
    azimuth: float,
    elevation: float,
    zoom: float,
    output_dir: str,
    filename_prefix: str,
    mode: str,
    project_path: str,
    ts: datetime,
    ts_str: str,
    image_width: int = 1920,
    image_height: int = 1080,
) -> dict[str, Any]:
    """Export to disk, optionally return base64 as well."""
    out_dir = _resolve_out_dir(project_path, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{filename_prefix}_{ts_str}.png"
    json_path = out_dir / f"{filename_prefix}_{ts_str}.json"

    try:
        _export_image(prj, str(png_path), image_width, image_height)
    except Exception as e:
        return error_response("export_failed", f"Failed to export image: {e}")

    result: dict[str, Any] = {
        "status": "success",
        "image_path": str(png_path.resolve()),
        "view_type": view_type,
        "view_params": _view_params(preset_name, view_type, azimuth, elevation, zoom),
        "tool": "capture-3d-view",
        "adapter": "cst_runtime_cli",
    }

    try:
        metadata = {
            "project_path": str(Path(project_path).resolve()) if project_path else "",
            "timestamp": ts.isoformat(timespec="seconds"),
            "view_type": view_type,
            "view_params": result["view_params"],
            "image_path": str(png_path.resolve()),
            "metadata_path": str(json_path.resolve()),
            "image_size": {"width": 1920, "height": 1080},
            "status": "success",
        }
        json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        result["metadata_path"] = str(json_path.resolve())
    except Exception as e:
        pass

    if mode == "both":
        try:
            with open(png_path, "rb") as f:
                result["image_data_base64"] = base64.b64encode(f.read()).decode("ascii")
        except Exception:
            pass

    return result


def _view_params(
    preset_name: str,
    view_type: str,
    azimuth: float,
    elevation: float,
    zoom: float,
) -> dict[str, Any]:
    """Build view_params dict for result metadata."""
    return {
        "azimuth": azimuth if view_type == "custom" else None,
        "elevation": elevation if view_type == "custom" else None,
        "zoom": zoom,
        "preset_name": preset_name if view_type == "preset" else None,
    }


def _resolve_out_dir(project_path: str, output_dir: str) -> Path:
    """Resolve the output directory path.

    Priority:
    1. Explicit output_dir
    2. Run structure detected → <run_dir>/exports/screenshots/
    3. Fallback → <project_parent>/exports/screenshots/
    4. Last resort → cwd/exports/screenshots/
    """
    if output_dir:
        return Path(output_dir).resolve()
    if project_path:
        p = Path(project_path).resolve()
        run_dir = infer_run_dir_from_project(str(p))
        if run_dir:
            return run_dir / "exports" / "screenshots"
        return p.parent / "exports" / "screenshots"
    return Path.cwd() / "exports" / "screenshots"
