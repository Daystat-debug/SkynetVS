# SCM01-WSB01-BEN01 source template. No live grant issuer exists in this delivery.
# This unconditional closure occurs before file reads, native calls or interpreter launch.
Write-Output '{"result":"RUNTIME_CLOSED_SOURCE_ONLY","runtime_authorized":false,"guest_bootstrap":false}'
exit 92

# Unreachable preparation body: retained for review, not executable permission.
# The closed Python byte-graph loader is now prepared as source. A future reviewed
# guest issuer/entry integration is still required; deleting exit 92 is NOT admission.
$ErrorActionPreference = 'Stop'
$InputRoot = 'C:\SkynetVSBenignInput'
$RuntimeRoot = 'C:\SkynetVSBenignRuntime'
$ControlRoot = 'C:\SkynetVSBenignControl'
$OutputRoot = 'C:\SkynetVSBenignOutput'
$InterpreterReturned = $false

function Assert-PlainPath {
    param([string] $Path)
    $Full = [System.IO.Path]::GetFullPath($Path)
    if ($Full -cne $Path -or $Path.StartsWith('\\') -or $Path.Substring(2).Contains(':')) {
        throw 'Non-canonical path.'
    }
    $Current = $Path
    while ($Current.Length -gt 3) {
        $Item = Get-Item -LiteralPath $Current -Force -ErrorAction Stop
        if (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Reparse path is forbidden.'
        }
        $Current = [System.IO.Path]::GetDirectoryName($Current)
    }
}

function Read-BoundedBytes {
    param([string] $Path, [long] $Cap)
    Assert-PlainPath $Path
    $Stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        if ($Stream.Length -lt 1 -or $Stream.Length -gt $Cap) { throw 'Input size limit.' }
        $Bytes = New-Object byte[] $Stream.Length
        $Offset = 0
        while ($Offset -lt $Bytes.Length) {
            $Count = $Stream.Read($Bytes, $Offset, $Bytes.Length - $Offset)
            if ($Count -le 0) { throw 'Unexpected EOF.' }
            $Offset += $Count
        }
        if ($Stream.ReadByte() -ne -1) { throw 'Input changed during read.' }
        return ,$Bytes
    } finally { $Stream.Dispose() }
}

function Get-ByteHash {
    param([byte[]] $Bytes)
    $Hash = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($Hash.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $Hash.Dispose() }
}

function Copy-ExactNew {
    param([string] $From, [string] $To, [long] $Size, [string] $Sha256)
    if ($Sha256 -cnotmatch '^[0-9a-f]{64}$' -or $Size -lt 0 -or $Size -gt 33554432) {
        throw 'Invalid member identity.'
    }
    Assert-PlainPath $From
    if ($Size -eq 0) {
        if ((Get-Item -LiteralPath $From).Length -ne 0) { throw 'Empty member mismatch.' }
        [byte[]] $Data = @()
    } else { [byte[]] $Data = Read-BoundedBytes $From 33554432 }
    if ($Data.Length -ne $Size -or (Get-ByteHash $Data) -cne $Sha256) { throw 'Source hash mismatch.' }
    $Parent = [System.IO.Path]::GetDirectoryName($To)
    if (-not [System.IO.Directory]::Exists($Parent)) { [System.IO.Directory]::CreateDirectory($Parent) | Out-Null }
    Assert-PlainPath $Parent
    $Stream = [System.IO.File]::Open($To, [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $Stream.Write($Data, 0, $Data.Length); $Stream.Flush($true) }
    finally { $Stream.Dispose() }
    if ((Get-Item -LiteralPath $To).Length -ne $Size -or
        (Get-FileHash -LiteralPath $To -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Sha256) {
        throw 'Local copy identity mismatch.'
    }
}

try {
    $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        if (-not $Identity.Name.EndsWith('\WDAGUtilityAccount', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unexpected guest identity.'
        }
    } finally { $Identity.Dispose() }
    foreach ($Root in @($InputRoot, $RuntimeRoot, $ControlRoot, $OutputRoot)) { Assert-PlainPath $Root }
    [byte[]] $RequestBytes = Read-BoundedBytes ($InputRoot + '\request.json') 32768
    $Request = [System.Text.Encoding]::ASCII.GetString($RequestBytes) | ConvertFrom-Json
    if ($Request.run_id -cnotmatch '^[0-9a-f]{32}$' -or $Request.nonce -cnotmatch '^[0-9a-f]{64}$' -or
        $Request.schema -cne 'SKYNETVS_SCM01_WSB01_BENIGN_V1' -or
        $Request.experiment -cne 'SCM01-WSB01-BEN01' -or $Request.scenario -cne 'fixed_digest_roundtrip') {
        throw 'Request identity mismatch.'
    }
    [byte[]] $CapsuleBytes = Read-BoundedBytes ($InputRoot + '\capsule.manifest.json') 32768
    if ((Get-ByteHash $CapsuleBytes) -cne $Request.capsule_sha256) { throw 'Capsule manifest mismatch.' }
    $Capsule = [System.Text.Encoding]::ASCII.GetString($CapsuleBytes) | ConvertFrom-Json
    [byte[]] $RuntimeBytes = Read-BoundedBytes ($RuntimeRoot + '\runtime_manifest.json') 65536
    if ((Get-ByteHash $RuntimeBytes) -cne '41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d') {
        throw 'Retained runtime manifest mismatch.'
    }
    $Runtime = [System.Text.Encoding]::UTF8.GetString($RuntimeBytes) | ConvertFrom-Json
    if (@($Runtime.payload_files).Count -ne 36) { throw 'Retained runtime inventory mismatch.' }
    $GuestRoot = 'C:\SkynetVSBenign\' + $Request.run_id
    if (Test-Path -LiteralPath $GuestRoot) { throw 'Guest-local run already exists.' }
    [System.IO.Directory]::CreateDirectory($GuestRoot) | Out-Null
    Assert-PlainPath $GuestRoot
    $LocalRuntime = $GuestRoot + '\Runtime'
    $LocalCapsule = $GuestRoot + '\Capsule'
    foreach ($Member in @($Runtime.payload_files)) {
        $Name = [string] $Member.path
        if ($Name -cnotmatch '^[A-Za-z0-9_.-]{1,100}$' -or $Name -in @('.', '..')) { throw 'Runtime member path.' }
        Copy-ExactNew ($RuntimeRoot + '\' + $Name) ($LocalRuntime + '\' + $Name) $Member.size_bytes $Member.sha256
    }
    Copy-ExactNew ($RuntimeRoot + '\runtime_manifest.json') ($LocalRuntime + '\runtime_manifest.json') `
        $RuntimeBytes.Length '41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d'
    $Allowed = @(
        'app/native/scm01_wsb01_benign_v1/__init__.py',
        'app/native/scm01_wsb01_benign_v1/benign_capsule.py',
        'app/native/scm01_wsb01_benign_v1/benign_contract.py',
        'app/native/scm01_wsb01_benign_v1/benign_layout.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_fs.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_crypto.py',
        'app/native/scm01_wsb01_benign_v1/benign_runtime_gate.py',
        'app/native/scm01_wsb01_benign_v1/payload/guest_entry.py'
    )
    if (@($Capsule.files).Count -ne $Allowed.Count -or
        @($Capsule.files | ForEach-Object { $_.path } | Sort-Object -Unique).Count -ne $Allowed.Count) {
        throw 'Capsule inventory mismatch.'
    }
    foreach ($Member in @($Capsule.files)) {
        if ($Allowed -cnotcontains ([string] $Member.path)) { throw 'Unexpected capsule member.' }
        $Relative = ([string]$Member.path).Replace('/', '\')
        Copy-ExactNew ($InputRoot + '\Capsule\' + $Relative) ($LocalCapsule + '\' + $Relative) `
            $Member.bytes $Member.sha256
    }
    $Python = $LocalRuntime + '\python.exe'
    $Entry = $LocalCapsule + '\app\native\scm01_wsb01_benign_v1\payload\guest_entry.py'
    # Positional hashes bind data only. The local first-process issuer remains absent;
    # the checked route is _guest_first_process, never an argv approved=true switch.
    $RequestSha = Get-ByteHash $RequestBytes
    $CapsuleSha = Get-ByteHash $CapsuleBytes
    [byte[]] $BootstrapBytes = Read-BoundedBytes ($InputRoot + '\guest_bootstrap.ps1') 262144
    $BootstrapSha = Get-ByteHash $BootstrapBytes
    [string] $RunId = $Request.run_id
    foreach ($Hash in @($RequestSha, $CapsuleSha, $BootstrapSha)) {
        if ($Hash -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid startup hash.' }
    }
    & $Python -I -S -B -X utf8 $Entry $RunId $RequestSha $CapsuleSha $BootstrapSha
    $GuestExitCode = $LASTEXITCODE
    $InterpreterReturned = $true
    if ($GuestExitCode -ne 0) { throw 'Fixed guest entry did not return success.' }
} finally {
    # One fixed shutdown only AFTER interpreter return; no privilege repair or retry.
    if ($InterpreterReturned) { & 'C:\Windows\System32\shutdown.exe' /s /t 0 }
}
