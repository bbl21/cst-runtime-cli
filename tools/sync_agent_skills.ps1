param(
    [ValidateSet("Copy", "Junction")]
    [string]$Mode = "Copy",

    [ValidateSet("codex_user", "opencode_user", "trae_cn")]
    [string[]]$Targets = @("codex_user", "opencode_user", "trae_cn"),

    [string[]]$SkillName = @(),

    [switch]$DryRun,

    [switch]$PruneRemoved
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SourceRoot = Join-Path $RepoRoot "skills"

$TargetRoots = @{
    codex_user     = Join-Path $env:USERPROFILE ".codex\skills"
    opencode_user  = Join-Path $env:USERPROFILE ".config\opencode\skills"
    trae_cn        = Join-Path $env:USERPROFILE ".trae-cn\skills"
}

$AllowOutOfRoot = @("codex_user", "opencode_user", "trae_cn")

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

$ExcludedDirectoryNames = @("__pycache__")
$ExcludedFileExtensions = @(".pyc", ".pyo")

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-UnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [string]$TargetName = ""
    )

    if ($AllowOutOfRoot -contains $TargetName) {
        return (Get-FullPath $Path).TrimEnd("\", "/")
    }

    $fullPath = (Get-FullPath $Path).TrimEnd("\", "/")
    $fullRoot = (Get-FullPath $Root).TrimEnd("\", "/")
    $rootPrefix = $fullRoot + [System.IO.Path]::DirectorySeparatorChar

    if ($fullPath -ne $fullRoot -and -not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside expected root: path=$fullPath root=$fullRoot"
    }

    return $fullPath
}

function Remove-TargetDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Operations
    )

    $safePath = Assert-UnderRoot -Path $Path -Root $Root
    if (-not (Test-Path -LiteralPath $safePath)) {
        return
    }

    $Operations.Add([ordered]@{ action = "remove"; path = $safePath }) | Out-Null
    if ($DryRun) {
        return
    }

    $item = Get-Item -LiteralPath $safePath -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        Remove-Item -LiteralPath $safePath -Force
    } else {
        Remove-Item -LiteralPath $safePath -Recurse -Force
    }
}

function Copy-SkillDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Operations
    )

    $sourceFull = Get-FullPath $Source
    $destinationFull = Assert-UnderRoot -Path $Destination -Root $DestinationRoot
    $Operations.Add([ordered]@{ action = "copy"; source = $sourceFull; destination = $destinationFull }) | Out-Null

    if ($DryRun) {
        return
    }

    New-Item -ItemType Directory -Path $destinationFull -Force | Out-Null

    $directories = Get-ChildItem -LiteralPath $sourceFull -Directory -Recurse -Force |
        Where-Object {
            $ExcludedDirectoryNames -notcontains $_.Name -and
            $_.FullName -notmatch "\\__pycache__(\\|$)"
        }
    foreach ($directory in $directories) {
        $relative = $directory.FullName.Substring($sourceFull.Length).TrimStart("\", "/")
        New-Item -ItemType Directory -Path (Join-Path $destinationFull $relative) -Force | Out-Null
    }

    $files = Get-ChildItem -LiteralPath $sourceFull -File -Recurse -Force |
        Where-Object {
            $ExcludedFileExtensions -notcontains $_.Extension.ToLowerInvariant() -and
            $_.FullName -notmatch "\\__pycache__(\\|$)"
        }
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($sourceFull.Length).TrimStart("\", "/")
        $targetFile = Join-Path $destinationFull $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $targetFile) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $targetFile -Force
    }
}

function New-SkillJunction {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Operations
    )

    $sourceFull = Get-FullPath $Source
    $destinationFull = Assert-UnderRoot -Path $Destination -Root $DestinationRoot
    $Operations.Add([ordered]@{ action = "junction"; source = $sourceFull; destination = $destinationFull }) | Out-Null

    if ($DryRun) {
        return
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $destinationFull) -Force | Out-Null
    New-Item -ItemType Junction -Path $destinationFull -Target $sourceFull | Out-Null
}

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "Source skills directory not found: $SourceRoot"
}

$allSourceSkills = @(Get-ChildItem -LiteralPath $SourceRoot -Directory)
$allSourceSkillNames = @($allSourceSkills | ForEach-Object { $_.Name })

$skills = if ($SkillName.Count -gt 0) {
    foreach ($name in $SkillName) {
        $source = Join-Path $SourceRoot $name
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "Skill not found under repo skills: $name"
        }
        Get-Item -LiteralPath $source
    }
} else {
    $allSourceSkills
}

$operations = [System.Collections.Generic.List[object]]::new()

foreach ($target in $Targets) {
    $targetRoot = $TargetRoots[$target]
    $safeTargetRoot = Assert-UnderRoot -Path $targetRoot -Root $RepoRoot -TargetName $target

    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $safeTargetRoot -Force | Out-Null
    }

    if ($PruneRemoved -and $target -ne "opencode_user" -and (Test-Path -LiteralPath $safeTargetRoot -PathType Container)) {
        $staleSkills = Get-ChildItem -LiteralPath $safeTargetRoot -Directory -Force |
            Where-Object {
                $allSourceSkillNames -notcontains $_.Name -and
                (Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") -PathType Leaf)
            }
        foreach ($staleSkill in $staleSkills) {
            Remove-TargetDirectory -Path $staleSkill.FullName -Root $safeTargetRoot -Operations $operations
        }
    }

    foreach ($skill in $skills) {
        $destination = Join-Path $safeTargetRoot $skill.Name
        Remove-TargetDirectory -Path $destination -Root $safeTargetRoot -Operations $operations
        if ($Mode -eq "Junction") {
            New-SkillJunction -Source $skill.FullName -Destination $destination -DestinationRoot $safeTargetRoot -Operations $operations
        } else {
            Copy-SkillDirectory -Source $skill.FullName -Destination $destination -DestinationRoot $safeTargetRoot -Operations $operations
        }
    }
}

[ordered]@{
    status = "success"
    mode = $Mode
    dry_run = [bool]$DryRun
    prune_removed = [bool]$PruneRemoved
    source_root = (Get-FullPath $SourceRoot)
    targets = $Targets
    skills = @($skills | ForEach-Object { $_.Name })
    operations = $operations
} | ConvertTo-Json -Depth 8
