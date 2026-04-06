# LovAgent

基于企业微信回调、GLM 和本地记忆系统的恋爱 Agent。项目现在默认提供网页安装向导，启动后直接打开 `/setup` 完成配置即可。

## 依赖清单

必需：

- `Git`
- `Python 3.10+`

构建前端或首次安装时需要：

- `Node.js 18+`
- `npm`

按需：

- `cloudflared`
  需要企业微信公网回调时建议安装。没有它也能先本地启动、进入 `/setup`、配置参数，只是暂时收不到公网回调。
- `Docker Desktop` 或 `Docker Engine + Docker Compose`
  如果你想走容器部署。

## 环境准备

### Linux / macOS

建议先执行环境检查：

```bash
./scripts/check-env.sh --bootstrap
```

常见依赖安装：

macOS（Homebrew）：

```bash
brew install python@3.12 node
```

Ubuntu / Debian：

```bash
sudo apt update && \
sudo apt install -y python3.12 python3.12-venv python3-pip nodejs npm
```

如果你需要企业微信公网回调，再额外安装 `cloudflared`，或让 `bootstrap.sh` 自动下载。

### Windows PowerShell

建议先执行环境检查：

```powershell
.\scripts\check-env.ps1 -Mode Bootstrap
```

常见依赖安装：

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
```

如果你需要企业微信公网回调，再额外安装：

```powershell
winget install Cloudflare.cloudflared
```

## 使用脚本启动

### Linux / macOS

推荐顺序：

```bash
git clone https://github.com/freecodetiger/lovagent.git && \
cd lovagent && \
./scripts/check-env.sh --bootstrap && \
./scripts/bootstrap.sh && \
./scripts/dev-up.sh
```

启动后打开：

- `http://127.0.0.1:8000/setup`

停止服务：

```bash
./scripts/stop.sh
```

如果你在做前端热更新开发：

```bash
./scripts/check-env.sh --dev-ui && \
./scripts/dev-up.sh --dev-ui
```

额外可用：

- `http://127.0.0.1:5173`

### Windows PowerShell

建议使用 PowerShell 运行。

```powershell
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\check-env.ps1 -Mode Bootstrap
.\scripts\bootstrap.ps1
.\scripts\dev-up.ps1
```

启动后打开：

- `http://127.0.0.1:8000/setup`

停止服务：

```powershell
.\scripts\stop.ps1
```

也可以直接双击：

```text
scripts\stop.bat
```

如果你在做前端热更新开发：

```powershell
.\scripts\check-env.ps1 -Mode DevUI
.\scripts\dev-up.ps1 -DevUI
```

## 脚本说明

- [check-env.sh](/home/zpc/projects/lovagent/scripts/check-env.sh)
  Linux / macOS 环境检查。会告诉你缺什么、怎么装。
- [bootstrap.sh](/home/zpc/projects/lovagent/scripts/bootstrap.sh)
  创建虚拟环境、安装 Python 依赖、安装并构建前端、尝试下载 `cloudflared`。
- [dev-up.sh](/home/zpc/projects/lovagent/scripts/dev-up.sh)
  默认只启动后端 `8000`，直接复用已构建前端。
- [dev-up.sh](/home/zpc/projects/lovagent/scripts/dev-up.sh) `--dev-ui`
  额外启动 `5173` 供前端热更新开发。
- [stop.sh](/home/zpc/projects/lovagent/scripts/stop.sh)
  Linux / macOS 停服入口，直接关闭这个项目启动的前后端进程。
- [check-env.ps1](/home/zpc/projects/lovagent/scripts/check-env.ps1)
  Windows 环境检查。
- [bootstrap.ps1](/home/zpc/projects/lovagent/scripts/bootstrap.ps1)
  Windows 首次安装脚本。
- [dev-up.ps1](/home/zpc/projects/lovagent/scripts/dev-up.ps1)
  Windows 默认启动脚本。
- [stop.ps1](/home/zpc/projects/lovagent/scripts/stop.ps1)
  Windows 停服入口。
- [stop.bat](/home/zpc/projects/lovagent/scripts/stop.bat)
  Windows 双击停服入口。

## Docker 启动

```bash
git clone https://github.com/freecodetiger/lovagent.git && \
cd lovagent && \
docker compose up --build
```

启动后打开：

- `http://127.0.0.1:8000/setup`

如果 Docker 报 `Cannot connect to the Docker daemon`，先启动 Docker Desktop 或 Docker daemon。

## 业务参数准备

企业微信部分仍需用户自己提供：

- `corp_id`
- `agent_id`
- `secret`
- `token`
- `encoding_aes_key`

GLM 部分需要：

- `zhipu_api_key`

## Setup Wizard 做什么

打开 `http://127.0.0.1:8000/setup` 后，按顺序完成：

1. 填 GLM API Key 和模型
2. 填企业微信参数
3. 确认公网回调地址
4. 设置管理员密码
5. 点“校验并进入后台”

如果本机有 `cloudflared`，后端会优先尝试自动拉起 Quick Tunnel，并把公网地址显示在 setup 页面中。

## 管理后台

初始化完成后，使用：

- `http://127.0.0.1:8000/admin`

可视化调整：

- 系统 Prompt / 人设
- 回复长度
- 用户记忆
- 主动聊天策略
- 回复预览

## 常见问题

### `127.0.0.1:8000` 拒绝连接

通常是后端没起来。先看：

- `./.run/backend.log`

Windows：

- `.run\backend.log`

最常见原因是：

- Python 版本低于 `3.10`
- Python 缺少 `venv / ensurepip`
- 首次安装时依赖没装完整

### `tsc: not found`

通常说明：

- `bootstrap` 没成功执行完
- 或机器缺少 `node / npm`

先执行：

```bash
./scripts/check-env.sh --bootstrap && \
./scripts/bootstrap.sh
```

或 Windows：

```powershell
.\scripts\check-env.ps1 -Mode Bootstrap
.\scripts\bootstrap.ps1
```

### 没装 `cloudflared` 能不能先启动

可以。你仍然可以：

- 打开 `/setup`
- 配置 GLM
- 配置企业微信参数
- 进入后台

只是没有公网 HTTPS 地址时，企业微信回调暂时无法联通。

## 额外说明

- `.env.example` 现在是可选覆盖项，不是必填前置步骤
- 更详细的部署说明和排障可看 [guide.md](/home/zpc/projects/lovagent/guide.md)
