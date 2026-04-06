$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

param(
    [switch]$DevUI
)

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CheckScript = Join-Path $RootDir "scripts\check-env.ps1"
$RunDir = Join-Path $RootDir ".run"
$AdminDir = Join-Path $RootDir "admin-ui"
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$DistIndex = Join-Path $AdminDir "dist\index.html"

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Remove-StalePid {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    $pidValue = Get-Content $PidFile -Raw
    if (-not $pidValue) {
        Remove-Item -Force $PidFile
        return
    }

    $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -Force $PidFile
    }
}

Remove-StalePid (Join-Path $RunDir "backend.pid")
Remove-StalePid (Join-Path $RunDir "frontend.pid")

if (-not (Test-Path $VenvPython)) {
    throw "缺少 .venv，请先执行 .\scripts\bootstrap.ps1"
}

if ($DevUI) {
    & $CheckScript -Mode DevUI
} else {
    & $CheckScript -Mode Run
}

& $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" | Out-Null

if (-not (Test-Path $DistIndex)) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "缺少 admin-ui/dist，且未检测到 npm。请先安装 Node.js 18+ 并执行 .\scripts\bootstrap.ps1"
    }
    npm.cmd --prefix $AdminDir run build
}

$backendPidFile = Join-Path $RunDir "backend.pid"
$frontendPidFile = Join-Path $RunDir "frontend.pid"

if (Test-Path $backendPidFile) {
    throw "后端已经在运行。"
}

if ($DevUI -and (Test-Path $frontendPidFile)) {
    throw "前端开发服务器已经在运行。"
}

$backendLog = Join-Path $RunDir "backend.log"
$backendProcess = Start-Process -FilePath $VenvPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") `
    -WorkingDirectory $RootDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLog `
    -PassThru
$backendProcess.Id | Set-Content $backendPidFile

if ($DevUI) {
    $frontendLog = Join-Path $RunDir "frontend.log"
    $frontendProcess = Start-Process -FilePath "npm.cmd" `
        -ArgumentList @("--prefix", $AdminDir, "run", "dev", "--", "--host", "0.0.0.0") `
        -WorkingDirectory $RootDir `
        -RedirectStandardOutput $frontendLog `
        -RedirectStandardError $frontendLog `
        -PassThru
    $frontendProcess.Id | Set-Content $frontendPidFile
}

Start-Sleep -Seconds 2

if (-not (Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue)) {
    throw "后端启动失败，请检查 $backendLog"
}

if ($DevUI -and -not (Get-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue)) {
    throw "前端启动失败，请检查 $frontendLog"
}

Write-Host ""
Write-Host "开发环境已启动。"
Write-Host "- Setup Wizard: http://127.0.0.1:8000/setup"
Write-Host "- Admin UI: http://127.0.0.1:8000/admin"
Write-Host "- Backend API: http://127.0.0.1:8000"
if ($DevUI) {
    Write-Host "- Vite Dev UI: http://127.0.0.1:5173"
}
