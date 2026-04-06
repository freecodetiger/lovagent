# LovAgent 部署指南

这份文档面向开源用户，目标不是解释企业微信原理，而是尽可能把“从 clone 到可用”压缩成一条稳定路径。

## 1. 你要准备的外部信息

LovAgent 已经支持：

- 浏览器 setup wizard
- 运行时配置持久化到数据库
- Cloudflare Quick Tunnel 自动拉起
- 启动后的一键连通性校验

但企业微信有一部分配置必须由部署者本人提供，无法在开源仓库里代办：

- 企业 ID `corp_id`
- 自建应用 `agent_id`
- 自建应用 `secret`
- 接收消息服务器配置里的 `token`
- 接收消息服务器配置里的 `encoding_aes_key`

如果缺少这些参数，项目可以启动，但无法通过企业微信回调验证，也无法完成消息收发。

## 2. 推荐路径

### 2.1 Docker Compose

适合第一次试跑和长期自托管。

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
docker compose up --build
```

然后访问：

- `http://127.0.0.1:8000/setup`

### 2.2 本地脚本

适合你要改代码或联调前后端。

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
./scripts/bootstrap.sh
./scripts/dev-up.sh
```

会启动：

- FastAPI：`http://127.0.0.1:8000`
- Vite 前端：`http://127.0.0.1:5173`
- Setup Wizard：`http://127.0.0.1:8000/setup`

停止命令：

```bash
./scripts/dev-down.sh
```

## 3. Setup Wizard 的实际流程

首次打开 `/setup` 后，建议按这个顺序操作：

1. 保存 GLM API Key 和模型名
2. 确认 tunnel 状态，拿到公网 `public_base_url`
3. 保存企业微信参数
4. 保存管理员密码
5. 点“校验并进入后台”

### 3.1 GLM

至少填写：

- `zhipu_api_key`
- `zhipu_model`

默认模型是 `glm-5`。

当前代码已经支持 Web Search 触发逻辑。当用户提到“是什么 / 最新 / 新闻 / 价格 / 某个概念”等内容时，后端会根据启发式规则尝试走检索能力。

### 3.2 Tunnel

如果 `cloudflared` 可用，后端会尝试自动拉起 Quick Tunnel，并把检测到的公网地址写入运行时配置。

Setup 页面会显示：

- `cloudflared` 是否可用
- tunnel 是否在运行
- 当前公网地址
- 最终回调地址

如果 tunnel 地址失效或变更，直接在 setup 页点“重启 Tunnel”，再把新回调 URL 回填到企业微信后台。

### 3.3 企业微信

需要输入：

- `corp_id`
- `agent_id`
- `secret`
- `token`
- `encoding_aes_key`

其中：

- `corp_id` 是企业 ID，不是应用 ID
- `agent_id` 是自建应用的 AgentId
- `token` 和 `encoding_aes_key` 必须与企业微信后台“接收消息服务器配置”保持完全一致

### 3.4 管理员密码

管理员密码会写入数据库中的运行时配置，不需要写进 `.env`。

注意：

- Session Secret 仍然建议在生产环境通过环境变量 `ADMIN_SESSION_SECRET` 固定下来
- 如果不设置，也可以运行，只是更适合本地或轻量部署

## 4. 企业微信后台应该怎么填

在企业微信后台创建自建应用后，把 setup 页面显示的回调地址填入：

```text
https://<你的公网地址>/wecom/callback
```

然后把后台生成或要求填写的：

- `Token`
- `EncodingAESKey`

同步填回 LovAgent 的 setup wizard。

关键点只有一个：

- 回调 URL、Token、EncodingAESKey 三者必须成套一致

只要 tunnel 换了域名，回调 URL 就必须重新保存。

## 5. 为什么做不到完全一键配置企业微信

如果仓库公开，真正的“clone 后零操作完成企业微信接入”基本不可行，原因是：

- 企业微信应用属于用户自己的企业主体
- `corp_id`、`secret`、`agent_id` 只能由用户自己创建或提供
- 回调配置涉及企业微信控制台里的安全参数，不适合仓库端自动生成并托管
- 回调 URL 往往依赖部署机器当前的公网地址或 tunnel 地址

所以现实可行的最佳实践不是“全自动”，而是：

- 应用自动启动
- 通过网页收集参数
- 自动保存运行时配置
- 自动生成回调地址
- 自动做健康检查和参数校验

当前仓库已经按这个方向落地。

## 6. 目录里的部署辅助文件

### 6.1 `docker-compose.yml`

用途：

- 一条命令启动 FastAPI
- 持久化 SQLite 到 Docker volume
- 镜像内置已构建的前端和 `cloudflared`

### 6.2 `scripts/bootstrap.sh`

用途：

- 创建 `.venv`
- 安装 Python 依赖
- 安装前端依赖
- 在本地下载 `cloudflared` 到 `.tools/bin/cloudflared`（如果系统里没有）

### 6.3 `scripts/dev-up.sh`

用途：

- 启动后端
- 启动前端 Vite
- 记录 PID 和日志文件

### 6.4 `scripts/dev-down.sh`

用途：

- 关闭 `dev-up.sh` 启动的本地进程

## 7. 运行时配置和 `.env` 的关系

现在有两套来源：

1. 环境变量 `app/config.py`
2. 数据库里的运行时配置 `runtime_configs`

服务实际读取的是“运行时配置优先，环境变量兜底”。

这意味着：

- 开源用户第一次部署时可以完全不写 `.env`
- 已有部署也可以继续用 `.env`
- setup wizard 保存后，无需重启就能让模型和企业微信服务读到新值

## 8. 最少需要检查的接口

### 本地健康检查

```bash
curl http://127.0.0.1:8000/health
```

### Setup 状态

```bash
curl http://127.0.0.1:8000/setup/status
```

### 已构建的后台页面

```bash
curl -I http://127.0.0.1:8000/admin
curl -I http://127.0.0.1:8000/setup
```

如果 tunnel 正常，再检查：

```bash
curl https://<public-base-url>/health
```

## 9. 常见问题

### 9.1 setup 页面里 tunnel 一直没有公网地址

排查顺序：

1. 本机是否安装了 `cloudflared`
2. `cloudflared` 是否可执行
3. 当前机器网络是否能连到 Cloudflare
4. 查看后端日志是否有 tunnel 启动输出

### 9.2 企业微信后台保存回调失败

优先检查：

- URL 是否是 `https`
- URL 是否真能公网访问
- `corp_id` 是否正确
- `token` 是否与后台一致
- `encoding_aes_key` 是否与后台一致

### 9.3 用户发消息后没有回复

先不要猜测模型问题，按顺序查：

1. 服务是否收到 `POST /wecom/callback`
2. GLM 调用是否成功
3. 企业微信发送接口是否报错
4. 是否被企业微信 IP 白名单拦截

## 10. 开源仓库建议保留的默认实践

如果你接下来要把仓库公开，这些实践已经比较重要：

- 不在 `.env.example` 里放任何真实密钥
- 让项目在没有 `.env` 的情况下也能启动 setup wizard
- 给出 Docker 路径和本地路径两套启动方式
- 把 Cloudflare Tunnel 做成默认公共入口
- 用浏览器保存配置，而不是要求用户手改多个环境变量
- 在 setup 页直接显示最终回调 URL
- 内置一键校验，减少企业微信和模型排障成本

## 11. 生产环境补充建议

如果不是本地调试，而是长期运行，建议额外做这些事：

- 显式设置 `ADMIN_SESSION_SECRET`
- 给 SQLite 或 MySQL 做持久化备份
- 若对域名稳定性有要求，改用固定 Cloudflare Tunnel 或固定 HTTPS 域名
- 为企业微信出口 IP 做稳定化处理，避免发送接口偶发被拦

## 12. 一句话总结

这个项目已经从“必须手改 `.env` + 手动拼回调地址”改成了“先启动，再进 `/setup` 做一次网页配置”。真正还需要用户自己补的，只剩企业微信应用参数本身，以及把最终回调地址保存到企业微信后台。
