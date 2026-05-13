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
            "uv run python -m cst_runtime doctor",
            "uv run python -m cst_runtime usage-guide",
            "uv run python -m cst_runtime list-tools",
            "uv run python -m cst_runtime list-pipelines",
            "uv run python -m cst_runtime describe-pipeline --pipeline latest-s11-preview",
            "uv run python -m cst_runtime describe-tool --tool get-1d-result",
            "uv run python -m cst_runtime args-template --tool get-1d-result --output <run-or-task>\\stages\\get_1d_result_args.json",
        ],
        "steps": [
            {"tool": "doctor", "purpose": "Check entrypoint and CST Python import readiness."},
            {"tool": "usage-guide", "purpose": "Read the CLI calling convention and JSON error contract."},
            {"tool": "list-tools", "purpose": "Discover available single-tool commands."},
            {"tool": "list-pipelines", "purpose": "Discover known multi-tool chains."},
            {"tool": "describe-pipeline", "purpose": "Read one pipeline recipe before composing commands."},
            {"tool": "describe-tool", "purpose": "Inspect an unfamiliar tool before calling it."},
            {"tool": "args-template", "purpose": "Generate UTF-8 JSON args files near the task/run."},
        ],
        "stop_rules": [
            "If doctor returns readiness=blocked, stop and report the missing dependency.",
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
            "If cleanup is needed, use cleanup-cst-processes and record Access is denied residuals.",
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
    "latest-s11-preview": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Read latest S11 run_id, export JSON, then render an HTML preview.",
        "when_to_use": "After a simulation has finished and the modeler project has been closed.",
        "required_context": ["working_project", "S11 treepath"],
        "commands": [
            "@{ project_path = \"<run>\\projects\\working.cst\"; treepath = \"1D Results\\S-Parameters\\S1,1\"; module_type = \"3d\"; max_mesh_passes_only = $false } | ConvertTo-Json -Depth 8 | uv run python -m cst_runtime list-run-ids | uv run python -m cst_runtime get-1d-result | uv run python -m cst_runtime plot-exported-file",
        ],
        "steps": [
            {"tool": "list-run-ids", "purpose": "Read available result run IDs for the S11 treepath."},
            {"tool": "get-1d-result", "purpose": "Default to the largest run_id from run_ids and export S11 JSON."},
            {"tool": "plot-exported-file", "purpose": "Use export_path from get-1d-result to create an HTML preview."},
        ],
        "stop_rules": [
            "Do not use export_s_parameter in an optimization loop.",
            "If list-run-ids does not return the expected new run_id, refresh/close/reopen results before reading.",
        ],
    },
    "project-result-preview": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Export a project result through cst.results and render an HTML preview with explicit project_path.",
        "when_to_use": "When replacing current-context MCP plot_project_result with a CLI call that names the .cst file.",
        "required_context": ["working_project", "treepath", "exports_dir"],
        "commands": [
            "uv run python -m cst_runtime args-template --tool plot-project-result --output <stages>\\plot_project_result_args.json",
            "uv run python -m cst_runtime plot-project-result --args-file <stages>\\plot_project_result_args.json",
        ],
        "steps": [
            {"tool": "plot-project-result", "purpose": "Export 1D/2D result JSON and render HTML preview."},
        ],
        "stop_rules": [
            "project_path must point to the run working .cst file.",
            "This tool reads results and writes preview artifacts; it does not replace fresh-session result consistency checks.",
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
    "s11-json-comparison": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Turn one or more exported S11 JSON files into an HTML comparison page.",
        "when_to_use": "After get-1d-result has produced JSON files in the run exports directory.",
        "required_context": ["S11 JSON export_path or file_paths", "output_html optional"],
        "commands": [
            "<get-1d-result JSON output> | uv run python -m cst_runtime generate-s11-comparison",
            "<json-producing-command> | uv run python -m cst_runtime generate-s11-comparison --args-stdin --args-file <stages>\\s11_comparison_args.json",
        ],
        "steps": [
            {"tool": "get-1d-result", "purpose": "Produce JSON inputs; CSV is not allowed."},
            {"tool": "generate-s11-comparison", "purpose": "Render JSON inputs to HTML."},
        ],
        "stop_rules": [
            "Only feed .json inputs produced by get-1d-result.",
            "If multiple files are needed, use --args-file with file_paths and --args-stdin only for explicit merge.",
        ],
    },
    "s11-farfield-dashboard": {
        "category": "results",
        "risk": "filesystem-write",
        "description": "Generate a combined S11 curve and farfield heatmap dashboard from exported files.",
        "when_to_use": "After S11 JSON and farfield TXT/JSON files are already exported into the run exports directory.",
        "required_context": ["s11_json_files", "farfield_files", "exports_dir"],
        "commands": [
            "uv run python -m cst_runtime args-template --tool generate-s11-farfield-dashboard --output <stages>\\s11_farfield_dashboard_args.json",
            "uv run python -m cst_runtime generate-s11-farfield-dashboard --args-file <stages>\\s11_farfield_dashboard_args.json",
        ],
        "steps": [
            {"tool": "get-1d-result", "purpose": "Produce S11 JSON inputs."},
            {"tool": "export-farfield-fresh-session", "purpose": "Produce Realized Gain/Gain/Directivity farfield TXT when needed."},
            {"tool": "generate-s11-farfield-dashboard", "purpose": "Render combined HTML dashboard from exported files."},
        ],
        "stop_rules": [
            "Do not feed CSV into the dashboard.",
            "Do not treat Abs(E) farfield files as dBi gain evidence.",
            "This dashboard generation is file-based and does not replace fresh-session CST validation.",
        ],
    },
    "farfield-realized-gain-preview": {
        "category": "farfield",
        "risk": "long-running",
        "description": "Fresh-session Realized Gain TXT export, grid inspection, and HTML preview.",
        "when_to_use": "At the end of a results workflow when true gain/dBi farfield evidence is required.",
        "required_context": ["working_project", "farfield_name", "exports_dir", "analysis_dir"],
        "commands": [
            "uv run python -m cst_runtime export-farfield-fresh-session --args-file <stages>\\export_farfield_args.json",
            "uv run python -m cst_runtime inspect-farfield-ascii --args-file <stages>\\inspect_farfield_args.json",
            "uv run python -m cst_runtime plot-farfield-multi --args-file <stages>\\plot_farfield_args.json",
            "uv run python -m cst_runtime read-realized-gain-grid-fresh-session --args-file <stages>\\read_gain_grid_args.json",
        ],
        "steps": [
            {"tool": "export-farfield-fresh-session", "purpose": "Export Realized Gain/Gain/Directivity TXT through a fresh CST session."},
            {"tool": "inspect-farfield-ascii", "purpose": "Verify row_count and theta/phi counts before trusting the file."},
            {"tool": "plot-farfield-multi", "purpose": "Render farfield TXT/JSON to HTML."},
            {"tool": "read-realized-gain-grid-fresh-session", "purpose": "Read true Realized Gain dBi grid through FarfieldCalculator."},
        ],
        "stop_rules": [
            "Never use Abs(E) as dBi gain evidence.",
            "Farfield export/read is a terminal results step; close with save=false and do not save after reading.",
            "Validate output_file/output_json existence and grid counts, not only status=success.",
        ],
    },
}
