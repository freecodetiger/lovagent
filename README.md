# LovAgent

基于企业微信回调、GLM 和本地记忆系统的恋爱 Agent。项目现在默认提供网页安装向导，用户不需要先手改 `.env`，启动后直接打开 `/setup` 完成配置即可。

## 依赖清单

必需：

- `Git`
- `Python 3.10+`
- `Node.js 18+`

按需：

- `cloudflared`
  需要企业微信公网回调时建议安装。没有它也能先本地启动、进入 `/setup`、配置参数，只是暂时收不到公网回调。
- `Docker Desktop` 或 `Docker Engine + Docker Compose`
  如果你想走容器部署而不是本地脚本。

默认启动时，项目会直接使用已构建的前端静态文件并由 FastAPI 提供页面：

- 日常启动只需要 Python 虚拟环境
- 只有在你想跑前端热更新开发时，才需要额外启动 `5173`

## 你需要提前准备的业务参数

企业微信部分不能自动代办，用户仍需自己提供：

- `corp_id`
- `agent_id`
- `secret`
- `token`
- `encoding_aes_key`

GLM 部分需要：

- `zhipu_api_key`

## 最简启动

### Linux / macOS

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
./scripts/bootstrap.sh
./scripts/dev-up.sh
```

启动后打开：

- `http://127.0.0.1:8000/setup`

停止服务：

```bash
./scripts/dev-down.sh
```

如果你在做前端开发，需要热更新，再用：

```bash
./scripts/dev-up.sh --dev-ui
```

此时额外可用：

- `http://127.0.0.1:5173`

### Windows PowerShell

建议使用 PowerShell 运行。

```powershell
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap.ps1
.\scripts\dev-up.ps1
```

启动后打开：

- `http://127.0.0.1:8000/setup`

停止服务：

```powershell
.\scripts\dev-down.ps1
```

如果你在做前端开发，需要热更新：

```powershell
.\scripts\dev-up.ps1 -DevUI
```

## Docker 启动

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
docker compose up --build
```

启动后打开：

- `http://127.0.0.1:8000/setup`

如果 Docker 报 `Cannot connect to the Docker daemon`，先启动 Docker Desktop 或 Docker daemon。

## Setup Wizard 做什么

打开 `http://127.0.0.1:8000/setup` 后，按顺序完成：

1. 填 GLM API Key 和模型
2. 填企业微信参数
3. 确认公网回调地址
4. 设置管理员密码
5. 点“校验并进入后台”

如果本机有 `cloudflared`，后端会优先尝试自动拉起 Quick Tunnel，并把公网地址显示在 setup 页面中。

## Cloudflare Tunnel

如果你需要真正接收企业微信回调，建议安装 `cloudflared`。

Linux / macOS：

- `scripts/bootstrap.sh` 会尝试自动下载一份到 `.tools/bin/cloudflared`

Windows：

- 建议手动安装
- 可直接执行：

```powershell
winget install Cloudflare.cloudflared
```

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

或 Windows：

- `.run\backend.log`

最常见原因是：

- Python 版本低于 `3.10`
- 首次安装时依赖没装完整

### `127.0.0.1:5173` 能打开，但 `/setup` 打不开

说明 Vite 起了，但 FastAPI 没起。正常使用时请优先访问：

- `http://127.0.0.1:8000/setup`

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
