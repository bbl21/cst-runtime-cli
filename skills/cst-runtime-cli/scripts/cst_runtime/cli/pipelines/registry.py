from __future__ import annotations
from typing import Any


PIPELINES: dict[str, dict[str, Any]] = {
    "self-learn-cli": {
        "category": "meta",
        "risk": "read",
        "description": "No-CST-start discovery path for a low-context agent learning the CLI.",
        "when_to_use": "First contact in a fresh shell, migrated workspace, or external coding agent.",
        "required_context": ["skill_root", "workspace"],
        "commands": [
            "uv run python -m cst_runtime health-check --auto-fix false",
            "uv run python -m cst_runtime --help",
            "uv run python -m cst_runtime list-tools",
            "uv run python -m cst_runtime list-pipelines",
            "uv run python -m cst_runtime describe-pipeline --pipeline prepare-experiment",
            "uv run python -m cst_runtime describe-tool --tool get-1d-result",
            "uv run python -m cst_runtime args-template --tool get-1d-result --output <run-or-task>\\stages\\get_1d_result_args.json",
        ],
        "steps": [
            {"tool": "health-check", "purpose": "Check environment readiness (replaces former doctor)."},
            {"tool": "--help", "purpose": "Read the CLI calling convention and JSON error contract."},
            {"tool": "list-tools", "purpose": "Discover available single-tool commands."},
            {"tool": "list-pipelines", "purpose": "Discover known multi-tool chains."},
            {"tool": "describe-pipeline", "purpose": "Read one pipeline recipe before composing commands."},
            {"tool": "describe-tool", "purpose": "Inspect an unfamiliar tool before calling it."},
            {"tool": "args-template", "purpose": "Generate UTF-8 JSON args files near the task/run."},
        ],
        "stop_rules": [
            "If health-check returns overall=blocked, stop and report the missing dependency.",
            "If any command returns status=error, inspect error_type/message before continuing.",
        ],
    },
    "args-file-tool-call": {
        "category": "meta",
        "risk": "read",
        "description": "Generate an args file, edit it, then call a tool without inline JSON.",
        "when_to_use": "Windows paths or complex parameters make inline --args-json fragile.",
        "required_context": ["tool_name", "task_or_run_stages_dir"],
        "commands": [
            "uv run python -m cst_runtime describe-tool --tool <tool>",
            "uv run python -m cst_runtime args-template --tool <tool> --output <stages>\\<tool>_args.json",
            "uv run python -m cst_runtime <tool> --args-file <stages>\\<tool>_args.json",
        ],
        "steps": [
            {"tool": "describe-tool", "purpose": "Read required fields, runbook, risk, and output style."},
            {"tool": "args-template", "purpose": "Create a concrete JSON args skeleton."},
            {"tool": "<tool>", "purpose": "Run the target tool with --args-file."},
        ],
        "stop_rules": [
            "Do not hand-write complex inline JSON in PowerShell.",
            "Only continue when the target tool returns status=success.",
        ],
    },
    "project-unlock-check": {
        "category": "project-identity",
        "risk": "read",
        "description": "Infer the run directory from working.cst and verify the project is unlocked.",
        "when_to_use": "Before copying, reopening, fresh-session export, or cleanup decisions.",
        "required_context": ["working_project"],
        "commands": [
            "@{ project_path = \"<run>\\projects\\working.cst\" } | ConvertTo-Json -Depth 8 | uv run python -m cst_runtime infer-run-dir | uv run python -m cst_runtime wait-project-unlocked",
        ],
        "steps": [
            {"tool": "infer-run-dir", "purpose": "Verify that project_path belongs to a standard run."},
            {"tool": "wait-project-unlocked", "purpose": "Check that the companion CST directory has no .lok lock files."},
        ],
        "recovery": [
            "If wait-project-unlocked reports a lock, close the matching CST project before retrying.",
            "If cleanup is needed, use cst-session-quit or close_project (kill_processes=True) and record Access is denied residuals.",
        ],
        "stop_rules": [
            "Do not copy or reopen a locked project.",
            "Do not claim Access is denied processes were killed.",
        ],
    },
    "cst-session-management-gate": {
        "category": "session_manager",
        "risk": "process-control",
        "description": "Full CST lifecycle gate for process management validation before copying, reopening, or full migration tests.",
        "when_to_use": "Before any workflow that depends on reliable CST open, close, reattach, lock release, or quit cleanup behavior.",
        "required_context": ["working_project"],
        "commands": [
            "uv run python -m cst_runtime cst-session-inspect --project-path <run>\\projects\\working.cst",
            "uv run python -m cst_runtime cst-session-open --project-path <run>\\projects\\working.cst",
            "uv run python -m cst_runtime cst-session-reattach --project-path <run>\\projects\\working.cst",
            "uv run python -m cst_runtime cst-session-close --project-path <run>\\projects\\working.cst --save false --wait-unlock true",
            "uv run python -m cst_runtime cst-session-quit --project-path <run>\\projects\\working.cst --dry-run true",
            "uv run python -m cst_runtime cst-session-quit --project-path <run>\\projects\\working.cst --dry-run false",
            "uv run python -m cst_runtime cst-session-inspect --project-path <run>\\projects\\working.cst",
        ],
        "steps": [
            {"tool": "cst-session-inspect", "purpose": "Record initial allowlisted processes, lock files, open projects, and attach readiness."},
            {"tool": "cst-session-open", "purpose": "Open the explicit working .cst through the central manager."},
            {"tool": "cst-session-reattach", "purpose": "Verify the expected project is the only attach target."},
            {"tool": "cst-session-close", "purpose": "Close save=false and verify lock release."},
            {"tool": "cst-session-quit", "purpose": "Dry-run, then real allowlist-only process cleanup when the project is closed."},
            {"tool": "cst-session-inspect", "purpose": "Confirm final lock/process/readiness state."},
        ],
        "stop_rules": [
            "Do not run the non-dry-run quit step until close returned status=success and lock files are clear.",
            "If Access is denied remains after locks clear, record it as nonblocking_access_denied_residual with PID/name; do not claim it was killed.",
            "If multiple CST projects are open, stop before write or close actions unless the expected project is isolated.",
        ],
    },
    "async-simulation-refresh-results": {
        "category": "modeler-results",
        "risk": "long-running",
        "description": "Start async simulation, wait for completion, close modeler, then refresh results before reading latest run_id.",
        "when_to_use": "When a low-context agent needs the async solver path without hand-written polling loops.",
        "required_context": ["working_project", "S11 treepath"],
        "commands": [
            "uv run python -m cst_runtime start-simulation-async --project-path <run>\\projects\\working.cst",
            "uv run python -m cst_runtime wait-simulation --project-path <run>\\projects\\working.cst --timeout-seconds 3600 --poll-interval-seconds 10",
            "uv run python -m cst_runtime cst-session-close --project-path <run>\\projects\\working.cst --save false",
            "uv run python -m cst_runtime list-run-ids --project-path <run>\\projects\\working.cst --treepath \"1D Results\\S-Parameters\\S1,1\" --module-type 3d --allow-interactive true --max-mesh-passes-only false",
            "uv run python -m cst_runtime get-1d-result --args-file <stages>\\get_1d_result_args.json",
        ],
        "steps": [
            {"tool": "start-simulation-async", "purpose": "Start the solver without blocking the process."},
            {"tool": "wait-simulation", "purpose": "Poll is-simulation-running until running=false or timeout."},
            {"tool": "cst-session-close", "purpose": "Release the modeler project with save=false before results refresh."},
            {"tool": "list-run-ids", "purpose": "Open/refresh results and discover the latest run_id."},
            {"tool": "get-1d-result", "purpose": "Read the latest run_id and export JSON."},
        ],
        "stop_rules": [
            "Do not read results before wait-simulation reports running=false.",
            "Do not save after reading results.",
            "If the latest run_id is missing, mark needs_validation instead of reading stale data.",
        ],
    },

    "first-run": {
        "category": "meta",
        "risk": "read",
        "description": "First-time environment setup: health-check with auto-fix, then discover CLI tools and pipelines.",
        "when_to_use": "When using the CLI for the first time in a new environment, or after installing/upgrading CST.",
        "required_context": [],
        "commands": [
            "uv run python -m cst_runtime health-check --auto-fix true",
            "uv run python -m cst_runtime --help",
            "uv run python -m cst_runtime list-tools",
            "uv run python -m cst_runtime list-pipelines",
        ],
        "steps": [
            {"tool": "health-check", "purpose": "Diagnose environment, auto-fix what's possible, report remaining issues."},
            {"tool": "--help", "purpose": "Read the CLI calling convention and help categories."},
            {"tool": "list-tools", "purpose": "Discover available commands."},
            {"tool": "list-pipelines", "purpose": "Discover known multi-tool chains."},
        ],
        "stop_rules": [
            "If health-check returns overall=blocked, stop and follow user_instructions.",
        ],
    },
    "inspect-project": {
        "category": "project-ops",
        "risk": "read",
        "description": "Open a CST project, list all parameters, entities, and farfield monitors, then close.",
        "when_to_use": "First exploration of an unknown project to understand all available tuning knobs and farfield monitors.",
        "required_context": ["working_project"],
        "commands": [
            "uv run python -m cst_runtime inspect-project --project-path <run>\\projects\\working.cst",
        ],
        "steps": [
            {"tool": "cst-session-open", "purpose": "Open the CST project."},
            {"tool": "list-parameters", "purpose": "Discover all tunable parameters with current values."},
            {"tool": "list-entities", "purpose": "Discover all geometric entities."},
            {"tool": "inspect-farfield-monitors", "purpose": "Find all farfield monitors for later export."},
            {"tool": "cst-session-close", "purpose": "Close with save=false (no changes were made)."},
        ],
        "stop_rules": [
            "If open fails, check that the .cst file exists and is not locked.",
        ],
    },
    "prepare-experiment": {
        "category": "project-ops",
        "risk": "write",
        "description": "Open a CST project, change a parameter, confirm the change, then save and close.",
        "when_to_use": "Before each simulation round to update parameter values.",
        "required_context": ["working_project", "param_name", "param_value"],
        "commands": [
            "uv run python -m cst_runtime prepare-experiment --project-path <run>\\projects\\working.cst --param-name g --param-value 23.5",
        ],
        "steps": [
            {"tool": "cst-session-open", "purpose": "Open the CST project."},
            {"tool": "change-parameter", "purpose": "Change the parameter to the new value."},
            {"tool": "list-parameters", "purpose": "Confirm the parameter change took effect."},
            {"tool": "save-project", "purpose": "Persist the change to disk."},
            {"tool": "cst-session-close", "purpose": "Close with save=false (already saved)."},
        ],
        "stop_rules": [
            "If change-parameter fails, stop and report the error before simulation.",
            "param_name must exactly match one of the names from list-parameters.",
        ],
    },
    "run-experiment": {
        "category": "simulation",
        "risk": "long-running",
        "description": "Run a simulation, wait for completion, then export S11 and farfield (auto-discovered) results.",
        "when_to_use": "After prepare-experiment to execute the simulation round and collect results.",
        "required_context": ["working_project"],
        "commands": [
            "uv run python -m cst_runtime run-experiment --project-path <run>\\projects\\working.cst",
        ],
        "steps": [
            {"tool": "cst-session-open", "purpose": "Open the CST project for simulation."},
            {"tool": "start-simulation-async", "purpose": "Start the solver without blocking."},
            {"tool": "wait-simulation", "purpose": "Poll until running=false or timeout."},
            {"tool": "cst-session-close", "purpose": "Close modeler with save=false to release the project."},
            {"tool": "export-run-results", "purpose": "Export S11 JSON + auto-discovered farfield TXT to exports/."},
        ],
        "stop_rules": [
            "If simulation times out, close modeler and record the timeout.",
            "After export, read s11_metric from output (no need to read JSON file manually).",
            "farfield_names is optional — all monitors are auto-discovered when omitted.",
        ],
    },
}
