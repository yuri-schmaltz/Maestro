# Maestro — stop local standalone (PowerShell para Windows)
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppDir = Join-Path $ScriptDir 'app'
$PidFile = Join-Path $AppDir '.launcher.pid'
$LogFile = Join-Path $AppDir '.launcher.log'

if (-not (Test-Path $PidFile)) {
    Write-Host "[stop_local.ps1] Sem pidfile — nenhum processo para parar." -ForegroundColor Gray
    if ($Clean -and (Test-Path $LogFile)) {
        Remove-Item $LogFile -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

$pidContent = (Get-Content $PidFile -Raw).Trim()
if ($pidContent -match '^\d+$') {
    $targetPid = [int]$pidContent
    $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "[stop_local.ps1] Parando processo Maestro PID $targetPid..." -ForegroundColor Yellow
        Stop-Process -Id $targetPid -Force
        Start-Sleep -Milliseconds 500
        Write-Host "[stop_local.ps1] Processo finalizado." -ForegroundColor Green
    } else {
        Write-Host "[stop_local.ps1] Processo PID $targetPid já não está ativo." -ForegroundColor Gray
    }
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

if ($Clean -and (Test-Path $LogFile)) {
    Remove-Item $LogFile -Force -ErrorAction SilentlyContinue
}
