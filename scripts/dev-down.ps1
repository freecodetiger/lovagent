$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RunDir = Join-Path $RootDir ".run"

function Stop-PidFile {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    $pidValue = Get-Content $PidFile -Raw
    if ($pidValue) {
        $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force
        }
    }

    Remove-Item -Force $PidFile
}

Stop-PidFile (Join-Path $RunDir "frontend.pid")
Stop-PidFile (Join-Path $RunDir "backend.pid")

Write-Host "本地开发进程已停止。"
