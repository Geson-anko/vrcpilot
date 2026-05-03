# vrcpilot CLI completion bootstrap for PowerShell.
#
# Usage (must be dot-sourced, not executed):
#     . .\CliComp.ps1
#
# Steps:
#   1. If `.venv` exists, activate it.
#   2. If `vrcpilot` is still not on PATH, run `just setup` and re-activate
#      (`just setup` calls `uv venv --clear`, so re-sourcing is required).
#   3. Register argcomplete for `vrcpilot` in the current session.
#   4. After this script returns, the venv stays activated and completion
#      stays enabled in your current PowerShell session.

# Refuse to be executed: a child scope would lose the venv and completion.
if ($MyInvocation.InvocationName -ne '.') {
    Write-Error "CliComp.ps1: must be dot-sourced, not executed.  Run:  . .\CliComp.ps1"
    return
}

$_clicompDir = $PSScriptRoot

# uv venv places Activate.ps1 under Scripts\ on Windows and bin\ on POSIX.
function _Clicomp-FindActivate {
    $candidates = @(
        (Join-Path $_clicompDir '.venv\Scripts\Activate.ps1'),
        (Join-Path $_clicompDir '.venv/bin/Activate.ps1')
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

$activate = _Clicomp-FindActivate
if ($activate) {
    . $activate
}

if (-not (Get-Command vrcpilot -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command just -ErrorAction SilentlyContinue)) {
        Write-Error "CliComp.ps1: 'just' is required but not found on PATH."
        return
    }
    Write-Host "CliComp.ps1: 'vrcpilot' not found - running 'just setup' in $_clicompDir"
    Push-Location -LiteralPath $_clicompDir
    try {
        just setup
        if ($LASTEXITCODE -ne 0) {
            Write-Error "CliComp.ps1: 'just setup' failed."
            return
        }
    } finally {
        Pop-Location
    }
    $activate = _Clicomp-FindActivate
    if (-not $activate) {
        Write-Error "CliComp.ps1: venv Activate.ps1 not found under $_clicompDir\.venv after setup"
        return
    }
    . $activate
}

if (-not (Get-Command register-python-argcomplete -ErrorAction SilentlyContinue)) {
    Write-Error "CliComp.ps1: 'register-python-argcomplete' not found (argcomplete missing?)."
    return
}

# Enable argcomplete-driven completion for `vrcpilot` in this session.
$completionScript = (& register-python-argcomplete --shell powershell vrcpilot) -join "`n"
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($completionScript)) {
    Write-Error "CliComp.ps1: failed to register argcomplete for vrcpilot."
    return
}
Invoke-Expression $completionScript

Write-Host "CliComp.ps1: vrcpilot completion enabled in this shell."
