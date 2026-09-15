# Maestro — launcher local standalone (PowerShell para Windows)
[CmdletBinding()]
param(
    [int]$Port = 7860,
    [switch]$Compile,
    [switch]$Share,
    [switch]$NoBuild,
    [switch]$Force,
    [switch]$NoOpen,
    [string]$ApiKey = ''
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppDir = Join-Path $ScriptDir 'app'
$PidFile = Join-Path $AppDir '.launcher.pid'
$LogFile = Join-Path $AppDir '.launcher.log'
$VersionFile = Join-Path $ScriptDir 'VERSION'

$ExpectedVersion = '0.0.0+unknown'
if (Test-Path $VersionFile) {
    $ExpectedVersion = (Get-Content $VersionFile -Raw).Trim()
}

$BindHost = if ($Share) { '0.0.0.0' } else { '127.0.0.1' }
Write-Host "[start_local.ps1] Maestro launcher (Windows) - porta $Port ($BindHost); versao: $ExpectedVersion" -ForegroundColor Cyan

# 1. Detectar venv
$Py = $null
foreach ($cand in @('env-sol', 'env-rtx50', 'env')) {
    $candidatePath = Join-Path $AppDir "$cand\Scripts\python.exe"
    if (Test-Path $candidatePath) {
        $Py = $candidatePath
        Write-Host "[start_local.ps1] Usando venv: $cand ($Py)" -ForegroundColor Green
        break
    }
}

if (-not $Py) {
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPy) {
        $Py = $sysPy.Source
        Write-Host "[start_local.ps1] Usando python do sistema: $Py" -ForegroundColor Yellow
    } else {
        Write-Error "[start_local.ps1] ERRO: nenhum ambiente Python encontrado em app/env*/ ou no PATH."
        exit 1
    }
}

# 2. Sanity: UI buildada
if (-not $NoBuild) {
    $IndexHtml = Join-Path $ScriptDir 'ui\dist\index.html'
    if (-not (Test-Path $IndexHtml)) {
        Write-Host "[start_local.ps1] UI dist nao encontrada. Compilando com npm..." -ForegroundColor Yellow
        Push-Location (Join-Path $ScriptDir 'ui')
        try {
            if (-not (Test-Path 'node_modules')) { npm install }
            npm run build
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[start_local.ps1] UI dist ok." -ForegroundColor Gray
    }
}

# 3. Verificar processo anterior
if (Test-Path $PidFile) {
    $oldPid = (Get-Content $PidFile -Raw).Trim()
    if ($oldPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($proc) {
            if ($Force) {
                Write-Host "[start_local.ps1] Encerrando processo anterior PID $oldPid..." -ForegroundColor Yellow
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
            } else {
                Write-Host "[start_local.ps1] Processo PID $oldPid ja esta em execucao. Use -Force para reiniciar." -ForegroundColor Yellow
                exit 0
            }
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# 4. Iniciar backend
$argsList = @('launch.py')
if ($Compile) { $argsList += '--compile' }
if ($Share) { $argsList += '--share' }
if ($ApiKey) { $argsList += @('--api-key', $ApiKey) }

$env:SERVER_NAME = $BindHost
$env:SERVER_PORT = "$Port"

Write-Host "[start_local.ps1] Lancando backend..." -ForegroundColor Cyan

$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $Py
$processInfo.Arguments = ($argsList -join ' ')
$processInfo.WorkingDirectory = $AppDir
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.UseShellExecute = $false
$processInfo.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::Start($processInfo)
$process.Id | Out-File -FilePath $PidFile -Encoding ascii

Write-Host "[start_local.ps1] Backend iniciado com PID $($process.Id)" -ForegroundColor Green
Write-Host "  UI:   http://127.0.0.1:$Port/" -ForegroundColor Cyan
Write-Host "  Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
Write-Host "  Logs: $LogFile" -ForegroundColor Gray

if (-not $NoOpen) {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:$Port/"
}
