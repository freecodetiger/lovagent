$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

param(
    [ValidateSet("Bootstrap", "Run", "DevUI")]
    [string]$Mode = "Run"
)

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DistIndex = Join-Path $RootDir "admin-ui\dist\index.html"

$PassCount = 0
$WarnCount = 0
$FailCount = 0

function Add-Pass($Message) {
    $script:PassCount++
    Write-Host "[OK] $Message"
}

function Add-Warn($Message) {
    $script:WarnCount++
    Write-Host "[WARN] $Message"
}

function Add-Fail($Message) {
    $script:FailCount++
    Write-Host "[FAIL] $Message"
}

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

function Test-PythonVenvSupport {
    param([string[]]$CommandParts)

    try {
        $arguments = @()
        if ($CommandParts.Length -gt 1) {
            $arguments += $CommandParts[1..($CommandParts.Length - 1)]
        }
        $arguments += @("-c", "import ensurepip, venv")
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
        if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) {
            continue
        }
        if (Test-PythonVersion -CommandParts $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-CommandTailArguments {
    param([string[]]$CommandParts)

    if ($CommandParts.Length -le 1) {
        return @()
    }

    return $CommandParts[1..($CommandParts.Length - 1)]
}

Write-Host "LovAgent 环境检查模式：$Mode"

if (Get-Command git -ErrorAction SilentlyContinue) {
    Add-Pass ((git --version) | Select-Object -First 1)
} else {
    Add-Fail "缺少 Git。"
}

$pythonCommand = Get-PythonCommand
if (-not $pythonCommand) {
    Add-Fail "未找到可用的 Python 3.10+。"
    Write-Host "  安装示例：winget install Python.Python.3.12"
} else {
    $pythonVersion = & $pythonCommand[0] @(Get-CommandTailArguments -CommandParts $pythonCommand) --version 2>&1
    Add-Pass "Python 可用：$pythonVersion"
    if (Test-PythonVenvSupport -CommandParts $pythonCommand) {
        Add-Pass "Python 自带 venv / ensurepip。"
    } else {
        Add-Fail "当前 Python 缺少 venv / ensurepip。"
    }
}

$needNode = $Mode -in @("Bootstrap", "DevUI") -or -not (Test-Path $DistIndex)
if ($needNode) {
    if ((Get-Command node -ErrorAction SilentlyContinue) -and (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        Add-Pass "Node.js 可用：$(node --version)"
        Add-Pass "npm 可用：$(npm.cmd --version)"
    } else {
        Add-Fail "缺少 Node.js 18+ 或 npm。"
        Write-Host "  安装示例：winget install OpenJS.NodeJS.LTS"
    }
} else {
    if ((Get-Command node -ErrorAction SilentlyContinue) -and (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        Add-Pass "Node.js / npm 可用。"
    } else {
        Add-Warn "未检测到 Node.js / npm，但已存在 admin-ui/dist，默认启动仍可继续。"
    }
}

if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    Add-Pass "curl 可用。"
} else {
    Add-Warn "未检测到 curl，公网 IP 检查和下载流程可能受影响。"
}

if ((Get-Command cloudflared -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $RootDir ".tools\bin\cloudflared.exe"))) {
    Add-Pass "cloudflared 可用。"
} else {
    Add-Warn "未检测到 cloudflared。可以先本地启动，但企业微信公网回调需要它或其他 HTTPS 暴露方式。"
    Write-Host "  安装示例：winget install Cloudflare.cloudflared"
}

Write-Host ""
Write-Host "检查结果：$PassCount 通过，$WarnCount 警告，$FailCount 失败"

if ($FailCount -gt 0) {
    exit 1
}
