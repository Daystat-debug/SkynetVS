#requires -Version 5.1
[CmdletBinding()]
param([switch]$NewRun)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = 'C:\Project\SkynetVS'
$expectedSha256 = '__PACKAGE_SHA256__'
$embeddedPackage = @'
__PACKAGE_BASE64__
'@
$queueDirectory = Join-Path $env:LOCALAPPDATA 'SkynetVS\AutoExperiments'
$pointer = Join-Path $queueDirectory ($expectedSha256 + '.json')
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

try {
    $packageBytes = [Convert]::FromBase64String($embeddedPackage)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $actualSha256 = ([BitConverter]::ToString($sha.ComputeHash($packageBytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($actualSha256 -cne $expectedSha256) { throw ('Package SHA256 mismatch: ' + $actualSha256) }
    $candidates = @(
        (Join-Path $repo '.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'SkynetVS\ModelLab\venv-torch210-cu128\Scripts\python.exe')
    )
    $python = $null
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $python = $candidate; break }
    }
    if ($null -eq $python) { throw 'An existing SkynetVS Python interpreter is required. Nothing was installed.' }
    if (-not (Test-Path -LiteralPath $queueDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $queueDirectory -Force | Out-Null
    }
    $resume = $false
    if (-not $NewRun -and (Test-Path -LiteralPath $pointer -PathType Leaf)) {
        $saved = Get-Content -LiteralPath $pointer -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($saved.package_sha256 -cne $expectedSha256) { throw 'Saved run is bound to another package.' }
        $runRoot = [IO.Path]::GetFullPath([string]$saved.run_root)
        $expectedParent = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
        if ([IO.Path]::GetDirectoryName($runRoot) -ine $expectedParent -or [IO.Path]::GetFileName($runRoot) -cnotmatch '^m154a_[0-9a-f]{12}$') {
            throw 'Saved run directory does not match the short user-profile run layout.'
        }
        if (-not (Test-Path -LiteralPath $runRoot -PathType Container)) { throw 'The saved run directory is missing. Use -NewRun only if a new test execution is intended.' }
        $resume = $true
    }
    else {
        $runRoot = Join-Path $env:USERPROFILE ('m154a_' + [guid]::NewGuid().ToString('N').Substring(0, 12))
        if (Test-Path -LiteralPath $runRoot) { throw 'Run directory already exists.' }
        New-Item -ItemType Directory -Path $runRoot | Out-Null
    }
    $extractionId = [guid]::NewGuid().ToString('N').Substring(0, 8)
    $package = Join-Path $runRoot ('package_' + $extractionId + '.zip')
    [IO.File]::WriteAllBytes($package, $packageBytes)
    $bundle = Join-Path $runRoot ('p_' + $extractionId)
    Expand-Archive -LiteralPath $package -DestinationPath $bundle -ErrorAction Stop
    if (-not $resume) {
        $record = @{ package_sha256 = $expectedSha256; run_root = $runRoot } | ConvertTo-Json
        $utf8 = New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText(($pointer + '.new'), $record, $utf8)
        Move-Item -LiteralPath ($pointer + '.new') -Destination $pointer -Force
    }
    $stateDirectory = Join-Path $runRoot 'r'
    $runner = Join-Path $bundle 'run.py'
    if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'The preserved runner is missing.' }
    Write-Host ('RUN_DIRECTORY=' + $stateDirectory)
    Write-Host ('PACKAGE_SHA256=' + $actualSha256)
    Write-Host 'ACTION=M154_AUTOMATIC_EXPERIMENT_COMMIT_CHECK_AND_PUSH'
    Write-Host 'PURPOSE=AUTOMATION_SELFTEST; REAL_REMOTE_PUSH=TRUE; USER_PROJECT_APPLY=FALSE'
    $arguments = @('-I', '-B', $runner, '--source', $repo, '--bundle', $bundle, '--run-dir', $stateDirectory)
    if ($resume -and (Test-Path -LiteralPath (Join-Path $stateDirectory 'state.json') -PathType Leaf)) {
        $arguments += '--retry'
        Write-Host 'MODE=RETRY_SAVED_RESULT_WITHOUT_RETEST'
    }
    else { Write-Host 'MODE=NEW_EXPERIMENT' }
    $code = Invoke-ExperimentPython -Executable $python -Arguments $arguments
    Write-Host ('RUNNER_EXIT_CODE=' + $code)
    if ($code -ne 0) { Write-Host 'The test result and publication result are printed separately above. The run remains available.' }
    exit $code
}
catch {
    Write-Host ('M154_AUTORUN_LAUNCHER_STOP=' + $_.Exception.Message)
    if ($null -ne $runRoot) { Write-Host ('PRESERVED_RUN_ROOT=' + $runRoot) }
    throw
}
