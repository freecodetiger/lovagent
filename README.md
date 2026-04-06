# LovAgent

基于企业微信回调、GLM 大模型和本地记忆系统的恋爱 Agent。仓库内置独立前端控制台，可直接在浏览器里调整系统人设、回复长度、用户记忆、主动聊天策略，以及首次部署所需的运行参数。

## 现在的部署方式

这个仓库已经改成了“网页向导为主，命令行为辅”的启动流：

- 首次启动后访问 `http://127.0.0.1:8000/setup`
- 在网页里填写 GLM API Key、企业微信参数、管理员密码
- 如本机存在 `cloudflared`，后端会自动拉起 Quick Tunnel，并把公网地址写入运行时配置
- 配置保存在数据库里，默认不要求手改 `.env`

仍然需要你手动提供的企业微信信息：

- 企业 ID `corp_id`
- 自建应用 `agent_id`
- 自建应用 `secret`
- 回调配置里的 `token`
- 回调配置里的 `encoding_aes_key`

企业微信后台本身不提供完整的一键自动配置能力，所以真正的“零操作”不可行；但本仓库已经把本地部署、参数保存、连通性校验和回调地址生成尽量收敛成一次 setup wizard。

## 快速开始

### 方式 1：Docker Compose

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
docker compose up --build
```

启动后打开：

- `http://127.0.0.1:8000/setup`

容器内会构建前端并运行 FastAPI，SQLite 数据库默认持久化在 `lovagent_data` volume 中。

### 方式 2：本地脚本

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
./scripts/bootstrap.sh
./scripts/dev-up.sh
```

启动后打开：

- `http://127.0.0.1:8000/setup`
- `http://127.0.0.1:5173`（前端开发服务器）

停止本地开发进程：

```bash
./scripts/dev-down.sh
```

## Setup Wizard 里需要填什么

### GLM

- `zhipu_api_key`
- `zhipu_model`，默认 `glm-5`

### 企业微信

- `corp_id`
- `agent_id`
- `secret`
- `token`
- `encoding_aes_key`

### 回调地址

向导会展示：

- 当前 Tunnel 公网地址
- 最终回调地址 `https://<public-base-url>/wecom/callback`

你只需要把这个完整 URL 回填到企业微信后台的“接收消息服务器配置”。

## Cloudflare Tunnel

项目默认优先使用 `cloudflared` Quick Tunnel。

如果本机已安装 `cloudflared`，或者你运行过 `./scripts/bootstrap.sh` 下载了二进制，后端启动时会尝试自动拉起 tunnel，并在 setup 页面展示当前公网地址。

如果 tunnel 地址变了，需要重新到企业微信后台保存新的回调 URL。

## 独立前端控制台

初始化完成后，访问：

- `http://127.0.0.1:8000/admin`

可视化控制项包括：

- 系统 Prompt / 全局人格
- 回复字数档位
- 单用户记忆
- 主动聊天策略
- 回复预览

## 环境变量

仓库保留了 [`.env.example`](/home/zpc/projects/lovagent/.env.example)，但它现在只作为可选覆盖项：

- 你可以完全依赖 setup wizard
- 也可以继续用 `.env` 做传统部署

生产环境建议至少显式设置：

- `DATABASE_PATH`
- `ADMIN_SESSION_SECRET`

## 验证与排障

Setup Wizard 内置一键校验，会检查：

- 本地 `/health`
- 公网 `/health`
- GLM 调用
- 企业微信 `access_token`
- 回调地址是否已生成

更完整的部署步骤、企业微信侧说明和排障建议见 [guide.md](/home/zpc/projects/lovagent/guide.md)。
