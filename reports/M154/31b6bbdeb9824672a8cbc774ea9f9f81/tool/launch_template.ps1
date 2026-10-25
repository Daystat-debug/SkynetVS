#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Repo = 'C:\Project\SkynetVS',
    [switch]$NewRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$knownProject = 'C:\Project\SkynetVS'
$expectedSha256 = '__PACKAGE_SHA256__'
$embeddedPackage = @'
__PACKAGE_BASE64__
'@
$runRoot = $null

function Quote-Argument([string]$Value) {
    $quoted = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '$1$1')
    return '"' + $quoted + '"'
}

function Invoke-ExperimentPython([string]$Executable, [string[]]$Arguments) {
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $Executable
    $start.Arguments = ($Arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $start.UseShellExecute = $false
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        [void]$process.Start()
        $process.WaitForExit()
        return [int]$process.ExitCode
    }
    finally { $process.Dispose() }
}

function Get-FullFileSystemPath([string]$Value) {
    $providerPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Value)
    $full = [IO.Path]::GetFullPath($providerPath)
    $root = [IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $root.Length) { return $full.TrimEnd('\', '/') }
    return $root
}

function Assert-SeparatePath([string]$GeneratedPath, [string]$SourcePath) {
    $generated = (Get-FullFileSystemPath $GeneratedPath).TrimEnd('\', '/')
    $source = (Get-FullFileSystemPath $SourcePath).TrimEnd('\', '/')
    $comparison = [StringComparison]::OrdinalIgnoreCase
    if ($generated.Equals($source, $comparison) -or
        $generated.StartsWith(($source + '\'), $comparison) -or
        $source.StartsWith(($generated + '\'), $comparison)) {
        throw 'The diagnostic output directory overlaps an input repository. Choose an external run location before continuing.'
    }
}

function Get-GitWorktreeRoot([string]$GitExecutable, [string]$Repository) {
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $GitExecutable
    $arguments = @('--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL', '-c', 'protocol.allow=never', '-C', $Repository, 'rev-parse', '--show-toplevel')
    $start.Arguments = ($arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
    $start.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
    foreach ($name in @($start.EnvironmentVariables.Keys)) {
        if ([string]$name -imatch '^GIT_') { $start.EnvironmentVariables.Remove([string]$name) }
    }
    $start.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
    $start.EnvironmentVariables['GCM_INTERACTIVE'] = 'Never'
    $start.EnvironmentVariables['GIT_OPTIONAL_LOCKS'] = '0'
    $start.EnvironmentVariables['GIT_NO_LAZY_FETCH'] = '1'
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) {
            $process.Kill()
            [void]$process.WaitForExit(2000)
            throw 'Git worktree-root lookup timed out before diagnostic files were created.'
        }
        $rootText = $stdout.GetAwaiter().GetResult().Trim()
        [void]$stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -eq 0 -and $rootText.Length -gt 0) { return (Get-FullFileSystemPath $rootText) }
        return $null
    }
    finally { $process.Dispose() }
}

try {
    $selectedRepo = Get-FullFileSystemPath $Repo
    $knownProject = Get-FullFileSystemPath $knownProject
    $gitExecutable = (Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $inputRoots = @($selectedRepo, $knownProject) | Select-Object -Unique
    $protectedRoots = @($inputRoots)
    foreach ($inputRoot in $inputRoots) {
        $actualRoot = Get-GitWorktreeRoot -GitExecutable $gitExecutable -Repository $inputRoot
        if ($null -ne $actualRoot) { $protectedRoots += $actualRoot }
    }
    $queueDirectory = Join-Path $env:LOCALAPPDATA 'SkynetVS\WorkspaceChecks'
    foreach ($sourcePath in $protectedRoots) {
        Assert-SeparatePath -GeneratedPath $queueDirectory -SourcePath $sourcePath
    }

    $packageBytes = [Convert]::FromBase64String($embeddedPackage)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $actualSha256 = ([BitConverter]::ToString($sha.ComputeHash($packageBytes))).Replace('-', '').ToLowerInvariant()
        $repoIdentityBytes = [Text.Encoding]::UTF8.GetBytes($selectedRepo.ToLowerInvariant())
        $repoIdentitySha256 = ([BitConverter]::ToString($sha.ComputeHash($repoIdentityBytes))).Replace('-', '').ToLowerInvariant()
    }
    finally { $sha.Dispose() }
    if ($actualSha256 -cne $expectedSha256) { throw ('Package SHA256 mismatch: ' + $actualSha256) }
    $pointer = Join-Path $queueDirectory ($expectedSha256 + '.' + $repoIdentitySha256 + '.json')

    $candidates = @(
        (Join-Path $knownProject '.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'SkynetVS\ModelLab\venv-torch210-cu128\Scripts\python.exe')
    )
    $python = $null
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $python = $candidate; break }
    }
    if ($null -eq $python) { throw 'An existing SkynetVS Python interpreter is required. Nothing was installed.' }

    $resume = $false
    if (-not $NewRun -and (Test-Path -LiteralPath $pointer -PathType Leaf)) {
        $saved = Get-Content -LiteralPath $pointer -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($saved.package_sha256 -cne $expectedSha256 -or
            $saved.repo_identity_sha256 -cne $repoIdentitySha256 -or
            -not ([string]$saved.repo_path).Equals($selectedRepo, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Saved run is bound to another package or selected repository.'
        }
        $runRoot = [IO.Path]::GetFullPath([string]$saved.run_root)
        $expectedParent = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
        if ([IO.Path]::GetDirectoryName($runRoot) -ine $expectedParent -or [IO.Path]::GetFileName($runRoot) -cnotmatch '^m154w_[0-9a-f]{12}$') {
            throw 'Saved run directory does not match the short user-profile run layout.'
        }
        if (-not (Test-Path -LiteralPath $runRoot -PathType Container)) { throw 'The saved run directory is missing. Use -NewRun only if a new observation is intended.' }
        if (((Get-Item -LiteralPath $runRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'The saved run directory must not be a reparse point.' }
        $resume = $true
    }
    else {
        $runRoot = Join-Path $env:USERPROFILE ('m154w_' + [guid]::NewGuid().ToString('N').Substring(0, 12))
        if (Test-Path -LiteralPath $runRoot) { throw 'Run directory already exists.' }
    }

    foreach ($sourcePath in $protectedRoots) {
        Assert-SeparatePath -GeneratedPath $runRoot -SourcePath $sourcePath
    }
    if (Test-Path -LiteralPath $queueDirectory -PathType Container) {
        if (((Get-Item -LiteralPath $queueDirectory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'The diagnostic queue directory must not be a reparse point.' }
    }
    else { New-Item -ItemType Directory -Path $queueDirectory -Force | Out-Null }
    if (-not $resume) { New-Item -ItemType Directory -Path $runRoot | Out-Null }

    $extractionId = [guid]::NewGuid().ToString('N').Substring(0, 8)
    $package = Join-Path $runRoot ('package_' + $extractionId + '.zip')
    [IO.File]::WriteAllBytes($package, $packageBytes)
    $bundle = Join-Path $runRoot ('p_' + $extractionId)
    Expand-Archive -LiteralPath $package -DestinationPath $bundle -ErrorAction Stop
    if (-not $resume) {
        $record = @{ package_sha256 = $expectedSha256; repo_path = $selectedRepo; repo_identity_sha256 = $repoIdentitySha256; run_root = $runRoot } | ConvertTo-Json
        $utf8 = New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText(($pointer + '.new'), $record, $utf8)
        Move-Item -LiteralPath ($pointer + '.new') -Destination $pointer -Force
    }
    $stateDirectory = Join-Path $runRoot 'r'
    $runner = Join-Path $bundle 'workspace_check.py'
    if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'The workspace diagnostic runner is missing.' }
    Write-Host ('RUN_DIRECTORY=' + $stateDirectory)
    Write-Host ('PACKAGE_SHA256=' + $actualSha256)
    Write-Host ('SELECTED_REPOSITORY=' + $selectedRepo)
    Write-Host 'ACTION=M154_WORKSPACE_DIAGNOSTIC_COMMIT_AND_PUSH'
    Write-Host 'PURPOSE=WORKSPACE_DIAGNOSTIC; REAL_REMOTE_REPORT_PUSH=TRUE; PIPELINE=NOT_RUN'
    $arguments = @('-I', '-S', '-B', $runner, '--repo', $selectedRepo, '--bundle', $bundle, '--run-dir', $stateDirectory)
    if ($resume -and (Test-Path -LiteralPath (Join-Path $stateDirectory 'state.json') -PathType Leaf)) {
        Write-Host 'MODE=RETRY_SAVED_REPORT_WITHOUT_RESCAN'
    }
    else { Write-Host 'MODE=NEW_WORKSPACE_OBSERVATION' }
    $code = Invoke-ExperimentPython -Executable $python -Arguments $arguments
    Write-Host ('RUNNER_EXIT_CODE=' + $code)
    if ($code -ne 0) { Write-Host 'Observation and publication results are separate. The diagnostic run remains available.' }
    exit $code
}
catch {
    Write-Host ('M154_WORKSPACE_LAUNCHER_STOP=' + $_.Exception.Message)
    if ($null -ne $runRoot) { Write-Host ('PRESERVED_RUN_ROOT=' + $runRoot) }
    throw
}
