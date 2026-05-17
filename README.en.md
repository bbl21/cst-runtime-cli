**English** | [中文](README.md)

# CST Runtime CLI

An AI automation toolchain for CST Studio Suite. Provides modeling, simulation, parameter optimization, results reading, and farfield export through a unified CLI entry point, enabling AI agents to reliably operate CST for electromagnetic simulation tasks.

The repository contains two skills:

- **`cst-runtime-cli`** — Infrastructure skill providing CLI tool implementations (session management, modeling, simulation, results reading, farfield export, etc.). The底层 layer that directly interfaces with CST.
- **`cst-runtime-optimization`** — Optimization skill focused on parameter optimization loops. Depends on `cst-runtime-cli` for CLI execution; contains only the workflow logic defined in its SKILL.md.

---

## Prerequisites

| Dependency | Notes |
|---|---|
| CST Studio Suite 2026 | **Must be installed manually**; select "Python libraries" component during installation |
| Python 3.12+ | Can be auto-installed by health-check |
| uv | Can be auto-installed by health-check |

> For complete environment setup instructions (including bootstrap, manual Python installation, and common troubleshooting), see [`skills/cst-runtime-cli/references/setup_guide.md`](skills/cst-runtime-cli/references/setup_guide.md).

## Installing the Skills

The repository contains two skills; install each separately:

### Option A: Release Download (skill only, recommended)

Download the latest archive from [Releases](https://github.com/anomalyco/cst-runtime-cli/releases) and extract to your tool's skills directory:

| AI Tool | Skills Directory |
|---------|-----------------|
| OpenCode | `%USERPROFILE%\.config\opencode\skills\` |
| Claude Code | `%USERPROFILE%\.claude\skills\` |
| Cursor | `%USERPROFILE%\.cursor\skills\` |
| Trae / Codex | `%USERPROFILE%\.trae\skills\` |
| Generic | Point your tool's skills directory to the extracted path |

Extracted structure:
```
skills\
├── cst-runtime-cli\
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── tests/
└── cst-runtime-optimization\
    └── SKILL.md
```

On Windows you may also use a junction to link the extracted directory:
```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.config\opencode\skills\cst-runtime-cli" -Target "extracted\skills\cst-runtime-cli"
```

### Option B: Clone Full Repository

```powershell
git clone https://github.com/anomalyco/cst-runtime-cli.git
```

Create symlinks to your tool's skills directory (example for OpenCode; adjust path prefix for other tools):

```powershell
# Infrastructure skill
New-Item -ItemType Junction -Path "$env:USERPROFILE%\.config\opencode\skills\cst-runtime-cli" -Target ".\skills\cst-runtime-cli"

# Optimization skill
New-Item -ItemType Junction -Path "$env:USERPROFILE%\.config\opencode\skills\cst-runtime-optimization" -Target ".\skills\cst-runtime-optimization"
```

> Option B is suitable when you need to modify the skill source code simultaneously.

The skills take effect after restarting opencode or starting a new session.

## Quick Start

### Step 1: Environment Setup

Tell the agent:

> Initialize the CST runtime environment, create a workspace, and let me know when done.

The agent will automatically run: `health-check --auto-fix true` → `uv sync` → `doctor` to confirm.

**After auto-fix completes, all subsequent commands must use `uv run` mode.** Do not use system Python directly, or unexpected library conflicts may occur.

For details, see [`skills/cst-runtime-cli/references/setup_guide.md`](skills/cst-runtime-cli/references/setup_guide.md).

### Step 2: Tell the Agent Your Requirements

```
Source project: C:\path\to\your_project.cst
Optimization target: e.g., S11 ≤ -40 dB from 9-11 GHz
Adjustable parameters: e.g., g (20-30, step 0.5)
```

If you are unsure about parameter names, the agent will first read the project's parameter list for your confirmation.

### Common Scenarios

| Scenario | Example Request |
|---|---|
| Optimize S11 | Source project at `C:\antennas\my_horn.cst`, optimize S11 ≤ -40 dB from 9-11 GHz |
| Run a single simulation | Run simulation for `C:\antennas\my_horn.cst` and show the S11 curve |
| Export farfield | Export the farfield pattern at 10 GHz, Realized Gain |
| Compare S11 | Compare S11 results from two runs and generate a comparison page |

---

## Project Structure

```
cst-runtime-cli/                          # Full repository
├── README.md                             # This file (Chinese)
├── README.en.md                          # English version
├── LICENSE
├── pyproject.toml                        # Root project (optional)
├── uv.lock
├── .gitignore
│
├── skills/
│   ├── cst-runtime-cli/                  # ← Infrastructure skill (same as release contents)
│   │   ├── SKILL.md                      # Agent execution manual
│   │   ├── scripts/
│   │   │   ├── cst_runtime_cli.py        # CLI entry point (used by bootstrap)
│   │   │   ├── pyproject.toml            # cst-runtime package definition
│   │   │   └── cst_runtime/              # All tool implementations
│   │   ├── references/
│   │   │   ├── setup_guide.md            # Complete first-time setup guide
│   │   │   ├── task_card_template.md
│   │   │   ├── pipeline_mode_guide.md
│   │   │   └── materials_name_list.txt
│   │   └── tests/
│   │
│   └── cst-runtime-optimization/         # ← Optimization skill
│       └── SKILL.md                      # Optimization loop workflow definition
│
└── tests/                                # Integration tests
```

## License

MIT
