# 恋爱 Agent

通过企业微信接入个人微信的恋爱伴侣 Agent

## 功能特点

- 智能对话：基于智谱 GLM-5 大模型
- 情绪引擎：多维度情绪状态管理
- 记忆系统：短期记忆 + 长期用户画像
- 时间感知：根据不同时间段调整回应风格

## 快速开始

1. 配置企业微信应用（参考 guide.md）
2. 安装依赖：`pip install -r requirements.txt`
3. 配置环境变量：复制 `.env.example` 为 `.env` 并填写配置
4. 启动服务：`uvicorn app.main:app --host 0.0.0.0 --port 8000`

## 企业微信回调调试

- 企业微信回调地址使用 `PUBLIC_BASE_URL` 拼接 `/wecom/callback`
- 本地调试可先启动服务：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 再启动 Cloudflare Tunnel：`cloudflared tunnel --url http://localhost:8000`
- 拿到 Cloudflare 提供的 HTTPS 地址后，设置 `PUBLIC_BASE_URL=https://<你的域名>`
- 保存企业微信回调地址前，先验证 `https://<你的域名>/health` 可访问
