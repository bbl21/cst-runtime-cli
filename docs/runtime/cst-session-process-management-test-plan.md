# CST Session/Process Management Test Plan

> Scope: validate the CST process-management system itself before expanding MCP/CLI migration tests.
> This document is an execution plan, not a project rule source.

## Principle

Process management is a prerequisite gate. Do not start full migration or workflow validation until the session/process manager can reliably handle:

- inspect current CST processes, lock files, open projects, and attach readiness;
- open the explicit run `working.cst`;
- reattach only when the expected project is the sole open project;
- close with `save=false` and verify lock release;
- quit/cleanup only allowlisted CST processes;
- record `Access is denied` residuals with PID/name and lock-file evidence.

The centralized control plane is `cst_runtime/session_manager.py`. Low-level helpers remain split by responsibility:

- `cst_runtime/modeler.py`: modeler open/close/read/write actions.
- `cst_runtime/project_identity.py`: explicit `project_path`, attach verification, open-project listing, lock-file checks.
- `cst_runtime/process_cleanup.py`: allowlisted process discovery and cleanup.

## CLI Gate

Use this pipeline recipe first:

```powershell
uv run python -m cst_runtime describe-pipeline --pipeline cst-session-management-gate
```

Expected lifecycle commands:

```powershell
uv run python -m cst_runtime cst-session-inspect --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-open --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-reattach --project-path "$run\projects\working.cst"
uv run python -m cst_runtime cst-session-close --project-path "$run\projects\working.cst" --save false --wait-unlock true
uv run python -m cst_runtime cst-session-quit --project-path "$run\projects\working.cst" --dry-run true
uv run python -m cst_runtime cst-session-quit --project-path "$run\projects\working.cst" --dry-run false
uv run python -m cst_runtime cst-session-inspect --project-path "$run\projects\working.cst"
```

Stop before the non-dry-run quit step unless close succeeded and lock files are clear.

## Automated No-CST-Start Checks

Run:

```powershell
uv run python -m unittest discover -s skills\cst-runtime-cli-optimization\tests
```

Coverage:

- `cst-session-*` tools are discoverable through `describe-tool`;
- args templates include required lifecycle fields;
- `cst-session-inspect` returns structured JSON without a project;
- `cst-session-quit --dry-run true` does not kill processes and returns a dry-run cleanup record;
- `cst-session-management-gate` is discoverable through `describe-pipeline`.

Passing this layer does not validate real CST COM behavior.

## Full Real-Machine Matrix

Use one disposable run working copy. Never use a reference project directly.

| Case | Setup | Command focus | Pass condition |
| --- | --- | --- | --- |
| PM-01 clean inspect | no CST project intentionally opened | `cst-session-inspect` | JSON success; readiness is `clear` or `attention_required`; no broad process scan outside allowlist |
| PM-02 open explicit project | disposable `working.cst` | `cst-session-open` | status success; post inspect names the expected project or attach readiness |
| PM-03 reattach expected project | only expected project open | `cst-session-reattach` | status success; open project list has exactly the expected `.cst` |
| PM-04 multi-project reattach | expected project plus unrelated CST project open, possibly across different DE PIDs | `cst-session-reattach` | expected-open case returns success with matching `design_environment_pid`; missing-expected case returns `project_not_open` |
| PM-05 close and unlock | expected project open | `cst-session-close --save false --wait-unlock true` | status success; lock files clear; post inspect has `lock_count=0` |
| PM-06 dry-run quit | after close | `cst-session-quit --dry-run true` | no process is killed; cleanup status is `dry_run`; allowlist recorded |
| PM-07 real quit | after close and dry-run | `cst-session-quit --dry-run false` | allowlisted processes are gone, or Access denied residuals are explicitly recorded |
| PM-08 Access denied residual | Windows refuses Stop-Process | `cst-session-quit --dry-run false` | if locks are clear, status may be success with `nonblocking_access_denied_residual`; PID/name/error retained |
| PM-09 lock remains | create or preserve `.lok` under companion dir | `cst-session-close` / `cst-session-inspect` | status error or readiness blocked; no copy/reopen is permitted |
| PM-10 final inspect | after cleanup | `cst-session-inspect` | lock_count is 0; no unsafe open project state remains; remaining processes are classified |

## Evidence

Record each real-machine case in the current run:

- command line;
- stdout JSON;
- `status`, `readiness`, `session_action`;
- open project list;
- lock files before/after;
- allowlisted processes before/after;
- any `Access is denied` PID/name/error.

If any case is not run, mark the process-management gate as `needs_validation`, not `validated`.

## 2026-05-03 Run Record

Run:

```text
tasks/task_010_ref0_fresh_session_farfield_validation/runs/run_002
```

Validated:

- PM-01 clean/initial inspect on a disposable `working.cst` copy.
- PM-02 open explicit project.
- PM-03 reattach expected project as the only open project.
- PM-05 close with `save=false` and lock-release verification.
- PM-06 dry-run quit.
- PM-07 real allowlist-only quit.
- PM-08 `Access is denied` residual recording.
- PM-09 lock-remains blocking behavior using a temporary synthetic `Model.lok`, then removal.
- PM-10 final inspect.

Evidence is in:

- `runs/run_002/logs/tool_calls.jsonl`
- `runs/run_002/stages/cli_*.json`
- `runs/run_002/status.json`

Result:

- `CST DESIGN ENVIRONMENT_AMD64` PID `51756` was killed by the allowlist cleanup.
- `CSTDCSolverServer_AMD64` PID `8584`, `CSTDCMainController_AMD64` PID `8644`, and `cstd` PID `10228` remained with `Access is denied`.
- The working project had `lock_count=0` after close/cleanup and no open CST project remained.
- PM-04 was initially left unvalidated, then retested after the CST COM API discovery below.

## 2026-05-03 PM-04 Update

API findings:

- `activate_project()` is not available in the CST COM API.
- Correct activation is `de.active_project = de.get_open_project(path)`.
- Active project path verification must use `active.filename()`, not `get_absolute_path()`.
- `DesignEnvironment.connect_to_any()` may attach to a different DE than the one containing the expected project. The runtime now enumerates CST Design Environment PIDs and connects to each candidate with `DesignEnvironment.connect(pid)`.

Updated PM-04 pass condition:

| Case | Setup | Command focus | Pass condition |
| --- | --- | --- | --- |
| PM-04A multi-DE reattach expected project | expected project is open in one DE while unrelated projects are open in another DE | `cst-session-reattach --project-path <expected>` | status success; response includes the matching `design_environment_pid`; active `filename()` matches expected |
| PM-04B missing expected project | unrelated projects are open but expected path is not open | `cst-session-reattach --project-path <missing>` | status error; `error_type=project_not_open`; no activation/write action performed |

Additional evidence:

- `run_002` reattached successfully through DE PID `36676`.
- `run_003` reattached successfully through DE PID `45380`.
- A missing expected project returned `project_not_open`.
- `run_002` and `run_003` were closed with `save=false`; both lock directories ended with no `.lok`.
- Empty test DE processes PID `36676` and PID `45380` were explicitly killed after their projects were closed and locks were clear.
- Pre-existing DE PID `37484` with `task_001` and `task_009` remained open and was not touched.
