param(
    [Parameter(Mandatory = $true)]
    [string]$TaskFile,

    [ValidateSet("codex-scout", "codex-sandbox-worker", "codex-doc-worker", "codex-code-worker")]
    [string]$Agent = "codex-scout",

    [string]$Model = "",

    [string]$SessionId = "",

    [string]$Title = "",

    [string]$Message = "Execute the attached task card exactly. Return status, evidence, changed paths, risks, and blockers.",

    [string]$OutDir = ".agent_handoff\opencode\outbox",

    [switch]$AllowWrites,

    [switch]$DryRun,

    [switch]$Async,

    [string]$BaseName = ""
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$opencodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
if (-not $opencodeCmd) {
    throw "opencode was not found on PATH."
}

if (-not (Test-Path -LiteralPath $TaskFile -PathType Leaf)) {
    throw "TaskFile not found: $TaskFile"
}

if ($Agent -ne "codex-scout" -and -not $AllowWrites) {
    throw "Agent '$Agent' may write files. Re-run with -AllowWrites after confirming the task card names the allowed write paths."
}

$taskPath = (Resolve-Path -LiteralPath $TaskFile).Path
$outDirPath = Join-Path $repoRoot $OutDir
if (-not (Test-Path -LiteralPath $outDirPath)) {
    New-Item -ItemType Directory -Path $outDirPath -Force | Out-Null
}

function New-SafeSlug {
    param([string]$Value)
    $slug = $Value -replace '[^\w.-]+', '-'
    $slug = $slug.Trim("-._")
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return "opencode-worker"
    }
    return $slug.ToLowerInvariant()
}

$taskStem = [System.IO.Path]::GetFileNameWithoutExtension($taskPath)
if ([string]::IsNullOrWhiteSpace($Title)) {
    $Title = "opencode-$Agent-$taskStem"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($BaseName)) {
    $baseName = "$stamp-$Agent-$(New-SafeSlug -Value $Title)"
}
else {
    $baseName = $BaseName
}
$jsonlPath = Join-Path $outDirPath "$baseName.jsonl"
$markdownPath = Join-Path $outDirPath "$baseName.md"
$summaryPath = Join-Path $outDirPath "$baseName.summary.json"
$asyncPath = Join-Path $outDirPath "$baseName.async.json"
$stdoutPath = Join-Path $outDirPath "$baseName.async.stdout.txt"
$stderrPath = Join-Path $outDirPath "$baseName.async.stderr.txt"

$beforeStatus = git status --short 2>$null

$argsList = @("run", "--agent", $Agent, "--format", "json", "--file", $taskPath, "--title", $Title)
if (-not [string]::IsNullOrWhiteSpace($SessionId)) {
    $argsList = @("run", "--session", $SessionId, "--agent", $Agent, "--format", "json", "--file", $taskPath, "--title", $Title)
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argsList = @("run", "--agent", $Agent, "--model", $Model, "--format", "json", "--file", $taskPath, "--title", $Title)
    if (-not [string]::IsNullOrWhiteSpace($SessionId)) {
        $argsList = @("run", "--session", $SessionId, "--agent", $Agent, "--model", $Model, "--format", "json", "--file", $taskPath, "--title", $Title)
    }
}
$argsList += $Message

$commandPreview = "opencode " + (($argsList | ForEach-Object {
    if ($_ -match '\s') {
        '"' + ($_ -replace '"', '\"') + '"'
    } else {
        $_
    }
}) -join " ")

if ($DryRun) {
    [pscustomobject]@{
        status = "dry_run"
        command = $commandPreview
        agent = $Agent
        model = $Model
        task_file = $taskPath
        out_dir = $outDirPath
        async = [bool]$Async
        jsonl_path = $jsonlPath
        markdown_path = $markdownPath
        summary_path = $summaryPath
        async_path = $asyncPath
    } | ConvertTo-Json -Depth 6
    exit 0
}

function Join-ProcessArguments {
    param([string[]]$Arguments)
    return (($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        }
        else {
            $_
        }
    }) -join " ")
}

function ConvertTo-PowerShellLiteral {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

if ($Async) {
    $scriptPath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($scriptPath)) {
        $scriptPath = $MyInvocation.MyCommand.Path
    }

    $powershellPath = "powershell.exe"
    try {
        $currentProcess = Get-Process -Id $PID -ErrorAction Stop
        if ($currentProcess.Path) {
            $powershellPath = $currentProcess.Path
        }
    }
    catch {
        $powershellPath = "powershell.exe"
    }

    $childCommandParts = @(
        "&",
        (ConvertTo-PowerShellLiteral -Value $scriptPath),
        "-TaskFile", (ConvertTo-PowerShellLiteral -Value $taskPath),
        "-Agent", (ConvertTo-PowerShellLiteral -Value $Agent),
        "-Title", (ConvertTo-PowerShellLiteral -Value $Title),
        "-Message", (ConvertTo-PowerShellLiteral -Value $Message),
        "-OutDir", (ConvertTo-PowerShellLiteral -Value $OutDir),
        "-BaseName", (ConvertTo-PowerShellLiteral -Value $baseName)
    )
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $childCommandParts += @("-Model", (ConvertTo-PowerShellLiteral -Value $Model))
    }
    if (-not [string]::IsNullOrWhiteSpace($SessionId)) {
        $childCommandParts += @("-SessionId", (ConvertTo-PowerShellLiteral -Value $SessionId))
    }
    if ($AllowWrites) {
        $childCommandParts += "-AllowWrites"
    }

    $childScript = ($childCommandParts -join " ") + " 1> " + (ConvertTo-PowerShellLiteral -Value $stdoutPath) + " 2> " + (ConvertTo-PowerShellLiteral -Value $stderrPath)
    $encodedChildScript = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($childScript))
    $childArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-EncodedCommand", $encodedChildScript
    )
    $childCommand = "$powershellPath -NoProfile -ExecutionPolicy Bypass -EncodedCommand <base64:$($encodedChildScript.Length)>"
    $runningSummary = [ordered]@{
        status = "running"
        mode = "async"
        async_pid = $null
        agent = $Agent
        model_override = $Model
        input_session_id = $SessionId
        task_file = $taskPath
        title = $Title
        command = $commandPreview
        child_command = $childCommand
        jsonl_path = $jsonlPath
        markdown_path = $markdownPath
        summary_path = $summaryPath
        async_path = $asyncPath
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        started_at = (Get-Date).ToString("o")
        git_status_before = @($beforeStatus)
    }
    $runningSummary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

    $process = Start-Process `
        -FilePath $powershellPath `
        -ArgumentList (Join-ProcessArguments -Arguments $childArgs) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    $launchSummary = [ordered]@{}
    foreach ($key in $runningSummary.Keys) {
        $launchSummary[$key] = $runningSummary[$key]
    }
    $launchSummary.async_pid = $process.Id
    $launchSummary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $asyncPath -Encoding UTF8
    $launchJson = $launchSummary | ConvertTo-Json -Depth 8
    [Console]::Out.WriteLine($launchJson)
    exit 0
}

$rawOutput = & $opencodeCmd.Source @argsList 2>&1
$exitCode = $LASTEXITCODE
$rawOutput | Set-Content -LiteralPath $jsonlPath -Encoding UTF8

$textParts = New-Object System.Collections.Generic.List[string]
$eventTypes = New-Object System.Collections.Generic.List[string]
$sessionIds = New-Object System.Collections.Generic.List[string]
$parseErrors = New-Object System.Collections.Generic.List[string]

foreach ($line in $rawOutput) {
    $lineText = [string]$line
    if ([string]::IsNullOrWhiteSpace($lineText)) {
        continue
    }

    try {
        $event = $lineText | ConvertFrom-Json -ErrorAction Stop
        if ($event.type) {
            $eventTypes.Add([string]$event.type)
        }
        if ($event.sessionID) {
            $sessionIds.Add([string]$event.sessionID)
        }
        if ($event.part -and $event.part.sessionID) {
            $sessionIds.Add([string]$event.part.sessionID)
        }
        if ($event.type -eq "text" -and $event.part -and $event.part.text) {
            $textParts.Add([string]$event.part.text)
        }
        elseif ($event.type -eq "error" -and $event.message) {
            $textParts.Add("ERROR: " + [string]$event.message)
        }
    }
    catch {
        $parseErrors.Add($lineText)
    }
}

$markdownText = ($textParts -join "`r`n").Trim()
if ([string]::IsNullOrWhiteSpace($markdownText)) {
    $markdownText = "No text event was emitted. Inspect raw JSONL: $jsonlPath"
}
$markdownText | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$afterStatus = git status --short 2>$null
$uniqueSessionIds = @($sessionIds | Select-Object -Unique)
$primarySessionId = ""
if ($uniqueSessionIds.Count -gt 0) {
    $primarySessionId = [string]$uniqueSessionIds[0]
}

$summary = [ordered]@{
    status = $(if ($exitCode -eq 0) { "success" } else { "error" })
    exit_code = $exitCode
    agent = $Agent
    model_override = $Model
    input_session_id = $SessionId
    task_file = $taskPath
    title = $Title
    command = $commandPreview
    jsonl_path = $jsonlPath
    markdown_path = $markdownPath
    session_id = $primarySessionId
    session_ids = $uniqueSessionIds
    session_list_command = "opencode session list"
    session_export_command = $(if ($primarySessionId) { "opencode export $primarySessionId" } else { "" })
    session_continue_command = $(if ($primarySessionId) { "opencode run --session $primarySessionId" } else { "" })
    session_tui_command = $(if ($primarySessionId) { "opencode --session $primarySessionId" } else { "" })
    event_types = @($eventTypes | Select-Object -Unique)
    parse_error_count = $parseErrors.Count
    git_status_before = @($beforeStatus)
    git_status_after = @($afterStatus)
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 8

if ($exitCode -ne 0) {
    exit $exitCode
}
