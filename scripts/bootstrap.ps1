$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ToolsDir = Join-Path $RootDir ".tools\bin"
$VenvDir = Join-Path $RootDir ".venv"
$AdminDir = Join-Path $RootDir "admin-ui"
$DistIndex = Join-Path $AdminDir "dist\index.html"

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

function Test-PythonVersion {
    param([string[]]$CommandParts)

    try {
        $arguments = @()
        if ($CommandParts.Length -gt 1) {
            $arguments += $CommandParts[1..($CommandParts.Length - 1)]
        }
        $arguments += @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)")
        & $CommandParts[0] @arguments | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-PythonCommand {
    $candidates = @(
        @("py", "-3.13"),
        @("py", "-3.12"),
        @("py", "-3.11"),
        @("py", "-3.10"),
        @("python3.13"),
        @("python3.12"),
        @("python3.11"),
        @("python3.10"),
        @("python")
    )

    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
            continue
        }
        if (Test-PythonVersion -CommandParts $candidate) {
            return $candidate
        }
    }

    return $null
}

function Run-PythonCommand {
    param(
        [string[]]$CommandParts,
        [string[]]$Arguments
    )

    $prefixArguments = @()
    if ($CommandParts.Length -gt 1) {
        $prefixArguments += $CommandParts[1..($CommandParts.Length - 1)]
    }
    & $CommandParts[0] @prefixArguments @Arguments
}

$pythonCommand = Get-PythonCommand
if (-not $pythonCommand) {
    throw "未找到可用的 Python 3.10+。请先安装 Python 3.10 或更高版本。"
}

if (Test-Path $VenvDir) {
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Remove-Item -Recurse -Force $VenvDir
    } else {
        try {
            & $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" | Out-Null
        } catch {
            Remove-Item -Recurse -Force $VenvDir
        }
    }
}

if (-not (Test-Path $VenvDir)) {
    Run-PythonCommand -CommandParts $pythonCommand -Arguments @("-m", "venv", $VenvDir)
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $RootDir "requirements.txt")

if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $AdminDir "package-lock.json")) {
        npm.cmd --prefix $AdminDir ci
    } else {
        npm.cmd --prefix $AdminDir install
    }
    npm.cmd --prefix $AdminDir run build
} elseif (-not (Test-Path $DistIndex)) {
    throw "未检测到 npm，且 admin-ui/dist 不存在。请先安装 Node.js 18+。"
}

$cloudflaredInPath = Get-Command cloudflared -ErrorAction SilentlyContinue
$localCloudflared = Join-Path $ToolsDir "cloudflared.exe"
if (-not $cloudflaredInPath -and -not (Test-Path $localCloudflared)) {
    Write-Warning "未检测到 cloudflared。需要企业微信公网回调时，请手动安装：winget install Cloudflare.cloudflared"
}

Write-Host ""
Write-Host "Bootstrap 完成。"
Write-Host "下一步："
Write-Host "1. 运行 .\scripts\dev-up.ps1"
Write-Host "2. 打开 http://127.0.0.1:8000/setup"
Write-Host "3. 在网页向导里填写 GLM、企业微信和管理员密码"
Write-Host ""
Write-Host "如需前端热更新开发，再运行：.\scripts\dev-up.ps1 -DevUI"
