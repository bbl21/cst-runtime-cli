from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from .errors import error_response


_COMMON_CST_PATHS = [
    r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    r"C:\Program Files\CST Studio Suite 2025\AMD64\python_cst_libraries",
    r"C:\Program Files (x86)\CST Studio Suite 2026\AMD64\python_cst_libraries",
]


def _probe_path(path_str: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    result: dict[str, Any] = {
        "path": str(p),
        "exists": p.is_dir(),
        "has_interface": False,
        "has_results": False,
        "files_accessible": False,
    }
    if p.is_dir():
        cst_pkg = p / "cst"
        result["has_interface"] = (cst_pkg / "interface").is_dir() if cst_pkg.is_dir() else False
        result["has_results"] = (cst_pkg / "results.py").is_file() if cst_pkg.is_dir() else False
        try:
            next(p.iterdir())
            result["files_accessible"] = True
        except PermissionError:
            pass
    return result


def _scan_registry() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CST AG\CST Studio Suite")
        i = 0
        while True:
            try:
                version = winreg.EnumKey(key, i)
                vk = winreg.OpenKey(key, version)
                try:
                    install_dir, _ = winreg.QueryValueEx(vk, "Installation Directory")
                    py_lib = Path(install_dir) / "AMD64" / "python_cst_libraries"
                    if py_lib.is_dir():
                        info = _probe_path(str(py_lib))
                        info["source"] = f"registry:CST Studio Suite {version}"
                        found.append(info)
                except FileNotFoundError:
                    pass
                winreg.CloseKey(vk)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except (FileNotFoundError, ImportError):
        pass
    return found


def scan_cst_installations() -> dict[str, Any]:
    found: list[dict[str, Any]] = []

    for raw_path in _COMMON_CST_PATHS:
        info = _probe_path(raw_path)
        info["source"] = "common_path"
        if info["exists"]:
            found.append(info)

    found.extend(_scan_registry())

    active_path = _read_active_cst_path()
    return {
        "status": "success",
        "found_count": len(found),
        "installations": found,
        "active_path": active_path,
        "active_valid": bool(active_path and Path(active_path).is_dir()),
    }


def _read_active_cst_path() -> str | None:
    try:
        pyproject = Path.cwd().resolve() / "pyproject.toml"
        if not pyproject.exists():
            pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if not pyproject.exists():
            return None
        import tomllib
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        source = data.get("tool", {}).get("uv", {}).get("sources", {}).get("cst-studio-suite-link", {})
        if isinstance(source, dict):
            return source.get("path")
    except Exception:
        pass
    return None


def _write_pyproject_cst_path(cst_path: str) -> dict[str, Any]:
    pyproject = Path.cwd().resolve() / "pyproject.toml"
    if not pyproject.exists():
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if not pyproject.exists():
        return error_response("pyproject_not_found", "No pyproject.toml found in workspace or repo root")

    original = pyproject.read_text(encoding="utf-8")

    toml_path = cst_path.replace("\\", "\\\\")
    entry = f'cst-studio-suite-link = {{ path = "{toml_path}", editable = true }}'

    entry_start = "cst-studio-suite-link = {"
    idx = original.find(entry_start)
    if idx >= 0:
        line_end = original.find("\n", idx)
        if line_end == -1:
            line_end = len(original)
        new_content = original[:idx] + entry + original[line_end:]
    else:
        heading = "[tool.uv.sources]"
        hidx = original.find(heading)
        if hidx >= 0:
            insert_at = original.find("\n", hidx) + 1
            new_content = original[:insert_at] + entry + "\n" + original[insert_at:]
        else:
            uv_heading = "[tool.uv]"
            uvidx = original.find(uv_heading)
            if uvidx >= 0:
                insert_at = original.find("\n", uvidx) + 1
                new_content = original[:insert_at] + f"\n{heading}\n" + entry + "\n" + original[insert_at:]
            else:
                new_content = original.rstrip() + f"\n\n{uv_heading}\n\n{heading}\n" + entry + "\n"

    if new_content == original:
        return error_response("pyproject_update_failed", "Failed to modify pyproject.toml; check file format")

    pyproject.write_text(new_content, encoding="utf-8")
    return {"status": "success", "cst_path": cst_path, "updated_file": str(pyproject)}


def install_cst_libraries(cst_path: str = "", dry_run: bool = False) -> dict[str, Any]:
    scan_result = scan_cst_installations()

    if cst_path:
        target_path = cst_path
        probe = _probe_path(target_path)
        if not probe["exists"]:
            return {
                **error_response("path_not_found", f"CST Python library path does not exist: {target_path}"),
                "scan": scan_result,
            }
    else:
        valid = [inst for inst in scan_result["installations"] if inst["has_interface"] and inst["has_results"]]
        if not valid:
            return {
                **error_response(
                    "cst_not_found",
                    "No CST Studio Suite 2026 Python libraries found. Install CST or provide --cst-path.",
                ),
                "scan": scan_result,
            }
        target_path = valid[0]["path"]

    if dry_run:
        return {
            "status": "success",
            "dry_run": True,
            "target_path": target_path,
            "active_path_matches": target_path == scan_result.get("active_path"),
            "scan": scan_result,
        }

    if target_path == scan_result.get("active_path"):
        verify = _verify_cst_imports()
        return {
            "status": "success",
            "cst_path": target_path,
            "already_configured": True,
            "pyproject_updated": False,
            "import_verification": verify,
            "scan": scan_result,
        }

    write_result = _write_pyproject_cst_path(target_path)
    if write_result.get("status") == "error":
        return {**write_result, "scan": scan_result}

    verify = _verify_cst_imports()
    return {
        "status": "success",
        "cst_path": target_path,
        "already_configured": False,
        "pyproject_updated": True,
        "import_verification": verify,
        "scan": scan_result,
    }


def _verify_cst_imports() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for mod in ("cst", "cst.interface", "cst.results"):
        try:
            __import__(mod)
            results[mod] = "success"
        except Exception as exc:
            results[mod] = f"error: {exc}"
    return results


def _check_item(name: str, status: str, message: str = "", auto_fixed: bool = False, user_action: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "auto_fixed": auto_fixed,
        "user_action": user_action,
    }


def health_check(workspace: str = "", auto_fix: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    fixes_applied: list[str] = []
    remaining_issues: list[dict[str, Any]] = []

    # 1. Python version
    py_ok = sys.version_info >= (3, 13)
    checks.append(_check_item(
        "python_version",
        "pass" if py_ok else "error",
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}" if py_ok else f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.13",
        user_action="Install Python 3.13 or later from https://python.org" if not py_ok else "",
    ))
    if not py_ok:
        remaining_issues.append(checks[-1])

    # 2. uv
    uv_path = shutil.which("uv")
    checks.append(_check_item(
        "uv",
        "pass" if uv_path else "warning",
        f"uv found at {uv_path}" if uv_path else "uv not on PATH",
        user_action="Install uv: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" if not uv_path else "",
    ))
    if not uv_path:
        remaining_issues.append(checks[-1])

    # 3. Workspace
    from . import workspace as ws_mod
    ws_info = ws_mod.workspace_status(workspace)
    ws_ok = ws_info["workspace_initialized"]
    ws_fixed = False
    if not ws_ok and auto_fix:
        try:
            fix = ws_mod.init_workspace(workspace)
            if fix.get("status") == "success":
                ws_fixed = True
                fixes_applied.append("workspace: initialized workspace")
                ws_info = ws_mod.workspace_status(workspace)
                ws_ok = True
        except Exception:
            pass
    checks.append(_check_item(
        "workspace",
        "pass" if ws_ok else "error",
        f"Workspace at {ws_info['workspace_root']}" if ws_ok else "Workspace not initialized",
        auto_fixed=ws_fixed,
        user_action="Run: python <skill-root>/scripts/cst_runtime_cli.py init-workspace --workspace <path>" if not ws_ok and not auto_fix else "",
    ))
    if not ws_ok:
        remaining_issues.append(checks[-1])

    # 4. CST library scan
    scan = scan_cst_installations()
    cst_found = scan["found_count"] > 0
    cst_valid = any(inst["has_interface"] and inst["has_results"] for inst in scan["installations"])
    cst_configured = scan["active_valid"]

    cst_fixed = False
    if not cst_configured and cst_valid and auto_fix:
        try:
            install_result = install_cst_libraries()
            if install_result.get("status") == "success":
                cst_fixed = True
                fixes_applied.append(f"cst_libraries: configured {install_result.get('cst_path', '')}")
                scan = scan_cst_installations()
                cst_configured = True
        except Exception:
            pass

    if not cst_found:
        cst_status = "error"
        cst_msg = "No CST Studio Suite installation detected"
        cst_action = "Install CST Studio Suite 2026 or higher, then re-run health-check"
    elif not cst_valid:
        cst_status = "error"
        cst_msg = f"CST found at {scan['installations'][0]['path']} but Python libraries incomplete"
        cst_action = "Reinstall CST Studio Suite with Python libraries option"
    elif not cst_configured:
        cst_status = "warning"
        cst_msg = "CST libraries found but not configured in pyproject.toml"
        cst_action = f"Run: python <skill-root>/scripts/cst_runtime_cli.py install-cst-libraries --cst-path \"{scan['installations'][0]['path']}\""
    else:
        cst_status = "pass"
        cst_msg = f"CST libraries at {scan['active_path']}"
        cst_action = ""

    checks.append(_check_item(
        "cst_libraries",
        cst_status,
        cst_msg,
        auto_fixed=cst_fixed,
        user_action=cst_action,
    ))
    if cst_status != "pass":
        remaining_issues.append(checks[-1])

    # 5. Import verification
    if cst_configured or (cst_fixed and auto_fix):
        v = _verify_cst_imports()
        imp_ok = all(val == "success" for val in v.values())
        failed_imports = [mod for mod, status in v.items() if status != "success"]
        checks.append(_check_item(
            "import_cst",
            "pass" if imp_ok else "error",
            f"All CST imports OK" if imp_ok else f"Failed: {', '.join(failed_imports)}",
            user_action="Check CST installation or PYTHONPATH configuration" if not imp_ok else "",
        ))
        if not imp_ok:
            remaining_issues.append(checks[-1])
    else:
        checks.append(_check_item(
            "import_cst",
            "skipped",
            "CST libraries not configured, skipping import verification",
        ))

    # 6. Encoding
    encoding = getattr(sys.stdout, "encoding", "unknown") or "unknown"
    checks.append(_check_item("encoding", "pass" if encoding.lower() in ("utf-8", "utf8") else "info", f"stdout encoding: {encoding}"))

    overall = "pass"
    for c in checks:
        if c["status"] == "error":
            overall = "blocked"
            break
        if c["status"] == "warning" and overall == "pass":
            overall = "degraded"

    return {
        "status": "success",
        "overall": overall,
        "checks": checks,
        "fixes_applied": fixes_applied,
        "remaining_issues": [
            {k: v for k, v in issue.items() if v}
            for issue in remaining_issues
        ],
        "readiness_summary": (
            "All systems ready." if overall == "pass" else
            f"Auto-fixed {len(fixes_applied)} issue(s); {len(remaining_issues)} remaining."
        ),
        "user_instructions": (
            "\n".join(
                f"- [{issue['name']}] {issue['user_action']}"
                for issue in remaining_issues if issue.get("user_action")
            ) if remaining_issues else "No manual action needed."
        ),
    }
