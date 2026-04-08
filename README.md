# LovAgent

## 基于企业微信的恋陪Agent,她不仅能认真对待和你的每一次聊天，甚至会主动打扰你，还可以识别图片和pdf,后续有望实现语音聊天的功能，快来试试吧～
 想快速部署直接看“5分钟跑起来”

## 快速导航

| 你想先看什么 | 直接跳转 |
| --- | --- |
| 这是个什么项目 | [这是什么](#这是什么) |
| 它能做什么 | [它能做什么](#它能做什么) |
| 支持哪些模型 | [当前支持哪些模型](#当前支持哪些模型) |
| 为什么默认推荐 cloudflared | [为什么这里几乎离不开 cloudflared](#为什么这里几乎离不开-cloudflared) |
| 怎么最快跑起来 | [5 分钟跑起来](#5-分钟跑起来) |
| Setup 和后台能做什么 | [Setup Wizard 会帮你做什么](#setup-wizard-会帮你做什么) |
| 技术上怎么工作 | [从技术视角看，这个项目怎么工作](#从技术视角看这个项目怎么工作) |
| 详细部署与排障 | [guide.md](/home/zpc/projects/lovagent/guide.md) |

## 这是什么

这不是一个“只能接一句话再吐一句话”的聊天 Demo。

LovAgent 是一个可以直接落地的企业微信 Agent 项目。你把它启动起来，配置好企业微信参数和模型 API Key 后，就可以：

- 在企业微信里和 Agent 对话
- 让它记住用户偏好和长期上下文
- 在后台调角色、人设、语气和回复策略
- 在需要时联网补充信息
- 让不同任务自动选择不同模型
- 让它识别图片和 PDF

如果你是计算机新手，可以把它理解为：
“一个把企业微信、AI 大模型和网页后台连起来的完整应用”。

如果你是技术读者，可以把它理解为：
“基于 FastAPI + LangGraph 风格编排 + 企业微信回调 + 运行时配置系统的 Agent 应用骨架”。

## 它能做什么

| 能力 | 你能看到的效果 |
| --- | --- |
| 企业微信对话 Agent | 用户直接在企业微信里和 Agent 聊天 |
| 角色调音台 | 调整人设、语气、规则、回复长度和风格 |
| 记忆系统 | 保留短期上下文，并提炼长期记忆、偏好和里程碑 |
| 主动消息 | 不只被动回复，也可以按策略主动触达 |
| Web Search | 在需要事实信息时联网补充上下文，当前优先走 Tavily，必要时回退 Exa |
| Auto 模型选择 | 在 OpenAI-compatible 接入下，可按聊天、记忆、主动消息自动路由不同模型 |
| 多模态理解 | 识别图片和 PDF，再结合上下文继续对话，当前基于 GLM-4.6V |
| Setup Wizard | 在网页里完成模型、回调地址、企业微信和管理员配置 |
| 消息聚合与幂等 | 短时间多条消息自动合并，减少重复回复和刷屏 |

## 为什么这里几乎离不开 cloudflared

如果你的目标是真正打通企业微信回调，而不是只在本地打开页面，那么对这个项目当前的默认使用路径来说，`cloudflared` 基本可以视为标配。

原因很直接：

- 企业微信回调需要公网可访问的 `HTTPS` 地址
- 大多数新手的本地电脑并没有现成的公网入口或固定域名
- 这个项目当前默认就是通过 `Cloudflare Quick Tunnel` 把本地 `8000` 端口暴露到公网
- Setup 页面展示的公网地址和最终回调地址，也是围绕这条路径设计的

当前实际行为是：

- 后端启动后会自动尝试拉起 tunnel
- 如果检测到可用的 `cloudflared`，系统会拿到 `https://xxxx.trycloudflare.com`
- 系统会据此生成企业微信回调地址：`https://xxxx.trycloudflare.com/wecom/callback`

你当然也可以不用 `cloudflared`，改用你自己的公网域名、反向代理或其他内网穿透方案。

但对第一次接触这个项目的大多数用户来说，最省事、也最贴合当前脚本与页面设计的方案仍然是：

- 准备好 `cloudflared`
- 启动项目
- 让 Setup 页面自动显示公网地址和回调地址
- 把这个地址回填到企业微信后台

## 当前支持哪些模型

LovAgent 现在不只支持智谱。

### 文本模型

- `GLM`
- `兼容 OpenAI Chat Completions 的模型服务`

这意味着你既可以直接使用智谱，也可以接入其他 OpenAI 风格 API 的模型平台或中转服务。

### 模型选择方式

- `Manual`：所有文本任务统一使用一个模型
- `Auto`：按任务类型自动路由不同模型

当前 `Auto` 会区分三类任务：

- 聊天 `chat_model`
- 记忆提炼 `memory_model`
- 主动消息 `proactive_model`

### 多模态

- 当前图片 / PDF 理解走单独的多模态配置
- 当前项目内的多模态实现基于 `GLM-4.6V`

### 重要说明

- `Web Search` 当前走独立搜索通道，默认推荐 `Tavily 主、Exa 备`，不再依赖单一模型厂商的私有搜索能力
- 想启用 `Web Search`，需要用户自行在 `Setup` 页面填写对应搜索 API Key；至少配置 `Tavily` 或 `Exa` 其中之一
- `Tavily` 当前提供免费额度，通常适合先低成本试跑；如果你希望搜索更稳，建议同时配置 `Exa` 作为回退
- `多模态` 当前不是“任意 OpenAI-compatible 模型都可直接使用”，而是项目内单独配置的 `GLM-4.6V`
- 对企业微信真实回调场景，项目默认最推荐 `cloudflared + Quick Tunnel`

## 适合谁

- 想做一个真实可运行的企业微信 Agent 项目
- 想研究 LangGraph 在消息编排、记忆和工具边界中的落地方式
- 想要一个带后台、带配置页、带多模型接入能力的 Agent 样板
- 想把它继续改造成陪伴型、角色型、客服型或私域运营型项目


## 5 分钟跑起来

### 推荐按行执行命令～

说明：

- 上面这些是独立命令。如果整段一次性粘贴到终端，前一条失败后，终端通常仍会继续尝试下一条
- 但单个脚本内部已经启用严格失败停止策略：Linux/macOS 使用 `set -euo pipefail`，PowerShell 使用 `$ErrorActionPreference = "Stop"`
- 所以最稳妥的方式仍然是按行执行，看到报错先处理，再继续下一步

### Linux / macOS

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
./scripts/check-env.sh --bootstrap
./scripts/bootstrap.sh
./scripts/dev-up.sh
```

启动后打开：

- `http://127.0.0.1:8000/setup`

停止服务：

```bash
./scripts/stop.sh
```

### Windows PowerShell

```powershell
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
Set-ExecutionPolicy -Scope Process Bypass
winget install Cloudflare.cloudflared
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

### Docker

如果你只想尽快试跑，而不是马上改代码：

```bash
git clone https://github.com/freecodetiger/lovagent.git
cd lovagent
docker compose up --build
```

启动后打开：

- `http://127.0.0.1:8000/setup`

## 你需要准备什么

### 基础环境

| 项目 | 说明 |
| --- | --- |
| `Git` | clone 仓库 |
| `Python 3.10+` | 后端运行环境 |
| `Node.js 18+` | 首次安装或前端构建需要 |
| `npm` | 安装和构建前端依赖 |

### 企业微信接入参数

这些参数必须由你自己在企业微信后台准备：

| 参数 | 说明 |
| --- | --- |
| `corp_id` | 企业 ID |
| `agent_id` | 自建应用 AgentId |
| `secret` | 自建应用 Secret |
| `token` | 接收消息服务器配置里的 Token |
| `encoding_aes_key` | 接收消息服务器配置里的 EncodingAESKey |

### 模型侧至少需要一组文本模型配置

你可以二选一：

| 方式 | 至少需要 |
| --- | --- |
| `GLM` | `zhipu_api_key` |
| `OpenAI-compatible` | `openai_api_key` + `openai_base_url` + 模型名 |

如果你只想先体验文本对话，先配置一种文本模型就够了。

图片 / PDF 多模态是单独配置项，后续再补也可以。

### 如果你要启用 Web Search

推荐在 `Setup` 页面里这样配：

- 搜索后端选择 `Tavily 主，Exa 备`
- 至少填写一个可用的 `Tavily API Key` 或 `Exa API Key`
- 如果你希望默认主通道 + 异常回退都可用，建议两个都填

补充说明：

- `Tavily` 当前有免费额度，适合先体验联网检索
- `Exa` 更适合作为补充搜索源和回退通道
- 这些搜索 API 需要你自己准备，并在 `Setup` 页面保存后才会生效

### 关键补充

| 项目 | 说明 |
| --- | --- |
| `cloudflared` | 对企业微信真实回调来说几乎是标配；当前项目默认就是围绕 Quick Tunnel 路径设计 |
| Docker Desktop / Docker Engine | 想用容器方式部署时需要 |

补充说明：

- Linux / macOS 下，[scripts/bootstrap.sh](/home/zpc/projects/lovagent/scripts/bootstrap.sh) 会尽量自动准备 `cloudflared`
- Windows 下建议提前手动安装 `cloudflared`
- 如果你已经有自己的公网 `HTTPS` 域名，也可以不用 Cloudflare Tunnel

## Setup Wizard 会帮你做什么

启动后直接打开：

- `http://127.0.0.1:8000/setup`

推荐按这个顺序完成：

1. 选择模型供应商
2. 配置文本模型和多模态模型
3. 检查 tunnel 状态，确认公网地址
4. 填写企业微信参数
5. 设置管理员密码
6. 点击“校验并进入后台”

Setup 页面当前可以完成的事：

- 显示当前回调地址
- 配置 `GLM` 或 `OpenAI-compatible` 文本模型
- 配置 `Web Search` 的搜索后端，以及 `Tavily / Exa` API Key
- 选择 `manual` 或 `auto` 模型模式
- 单独配置多模态模型
- 保存模型参数后立即生效，不需要重启后端
- 保存企业微信参数
- 自动或手动使用 Cloudflare Tunnel 地址
- 校验本地健康检查、公网地址、模型连通性和企业微信 access token

## 后台里能做什么

初始化完成后，可以进入：

- `http://127.0.0.1:8000/admin`

当前后台支持：

- 调整人设、语气、规则和回复长度
- 预览 Prompt
- 预览实际回复
- 查看和编辑用户记忆
- 配置主动聊天策略
- 查看 Setup、模型和回调设置

## 架构图

```mermaid
flowchart LR
    User[企业微信用户] --> WeCom[企业微信]
    Admin[Setup / Admin UI] --> Runtime[运行时配置]
    Tunnel[cloudflared Quick Tunnel] --> Callback[/wecom/callback]
    WeCom --> Callback
    Callback --> Merge[幂等去重 / 短时消息聚合]
    Merge --> Graph[LangGraph 风格编排]
    Runtime --> Graph
    Graph --> Memory[记忆读取 / 记忆提炼]
    Graph --> Search[Tavily Web Search]
    Search --> SearchFallback[Exa Fallback]
    Graph --> Router[任务级模型路由]
    Router --> GLM[GLM]
    Router --> OAI[OpenAI-compatible]
    Graph --> Deliver[企业微信消息发送]
    Deliver --> WeCom
```

## 功能截图区

这部分可以继续补仓库截图。当前先给出推荐占位，后续你只需要把截图替换进去，就能更像一个完整的开源首页。

| 建议截图位 | 建议展示内容 | 适合传达什么 |
| --- | --- | --- |
| `Setup Wizard` | 模型供应商选择、回调地址、tunnel 状态、校验结果 | 上手门槛低、配置流程清晰 |
| `Admin 控制台` | 角色调音台、回复预览、记忆管理 | 不是只有对话接口，而是完整产品 |
| `企业微信对话效果` | 连续消息聚合、文本回复、多模态示例 | 真实使用体验 |
| `系统架构图` | 回调、编排、记忆、模型路由、发送链路 | 工程完整度 |

## 从技术视角看，这个项目怎么工作

### 核心链路

企业微信消息进入回调后，后端会完成：

1. 验签、解密和消息规范化
2. 短时间消息聚合与幂等去重
3. 上下文加载和记忆读取
4. 按任务选择模型
5. 在需要时补充 Web Search 上下文
6. 生成回复、提炼记忆、发送消息

### 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | `FastAPI` |
| Agent 编排 | `LangGraph` 风格消息图 |
| 数据层 | `SQLAlchemy + SQLite` |
| 前端 | `React + TypeScript + Vite` |
| 接入层 | 企业微信回调验签、解密、消息发送 |
| 模型层 | `GLM` + `OpenAI-compatible` provider 抽象 |

### 这套设计的价值

- 不把模型、企业微信参数和回调地址硬编码在 `.env`
- 不要求每次改模型都重启服务
- 不把 Agent 做成“单轮问答函数”，而是保留记忆、检索和主动触达能力
- 允许同一个项目同时兼顾开源用户的易用性和工程上的可扩展性

## 常用脚本

### Linux / macOS

- [scripts/check-env.sh](/home/zpc/projects/lovagent/scripts/check-env.sh)
  环境检查，告诉你缺什么
- [scripts/bootstrap.sh](/home/zpc/projects/lovagent/scripts/bootstrap.sh)
  创建 `.venv`、安装依赖、构建前端、尝试准备 `cloudflared`
- [scripts/dev-up.sh](/home/zpc/projects/lovagent/scripts/dev-up.sh)
  默认启动后端，并复用已构建的前端
- [scripts/dev-up.sh](/home/zpc/projects/lovagent/scripts/dev-up.sh) `--dev-ui`
  额外启动 `5173`，用于前端热更新开发
- [scripts/stop.sh](/home/zpc/projects/lovagent/scripts/stop.sh)
  停止本地开发进程

### Windows

- [scripts/check-env.ps1](/home/zpc/projects/lovagent/scripts/check-env.ps1)
  Windows 环境检查
- [scripts/bootstrap.ps1](/home/zpc/projects/lovagent/scripts/bootstrap.ps1)
  Windows 首次安装脚本
- [scripts/dev-up.ps1](/home/zpc/projects/lovagent/scripts/dev-up.ps1)
  Windows 默认启动脚本
- [scripts/stop.ps1](/home/zpc/projects/lovagent/scripts/stop.ps1)
  Windows 停服入口
- [scripts/stop.bat](/home/zpc/projects/lovagent/scripts/stop.bat)
  Windows 双击停服入口

## `.env` 和网页配置是什么关系

这个项目现在有两层配置来源：

1. 环境变量
2. 数据库里的运行时配置

实际运行时策略是：

- 优先读取 Setup 页面保存的运行时配置
- 环境变量作为兜底

这意味着：

- 你可以不先写 `.env`，直接启动后去 `/setup`
- 也可以继续把 `.env` 作为默认值
- Setup 页面保存后，大多数配置会立即生效，不需要重启

## 常见问题

### 1. `127.0.0.1:8000` 打不开

先看日志：

- Linux / macOS：`./.run/backend.log`
- Windows：`.run\\backend.log`

最常见原因：

- Python 版本低于 `3.10`
- Python 缺少 `venv / ensurepip`
- 首次安装依赖没装完整
- `8000` 端口已被占用

### 2. 没装 `cloudflared` 能不能先启动

可以。

不装 `cloudflared` 的情况下：

- 本地服务照样能启动
- `/setup` 和 `/admin` 照样能用
- 只是企业微信公网回调暂时打不进来

但如果你的目标是“真的在企业微信里收到消息并完成回调联通”，那它基本还是必需项，除非你已经有其他公网 `HTTPS` 暴露方案。

### 3. 回调地址为什么会变

如果你使用的是 Cloudflare Quick Tunnel，它的公网域名可能会变化。域名一变，企业微信后台里的回调地址也要一起更新。

### 4. 为什么我连续发几句，它只回一条

这是当前项目的设计之一。

为了减少刷屏和重复回复，后端会把短时间内连续发送的多条文本、图片或 PDF 聚合成一次输入，再统一回复一条消息。

### 5. 为什么同一条消息以前会被重复回复

企业微信在回调响应不够快时可能会重试投递。项目现在已经做了：

- 入站消息幂等去重
- 短时间窗口聚合

所以正常情况下，同一条消息不会再被重复回复多次。

## 更多文档

如果你想看更详细的部署说明、回调配置和排障过程，可以继续看：

- [guide.md](/home/zpc/projects/lovagent/guide.md)

## 你可以把它继续扩展成什么

- 角色陪伴型 Agent
- 私域用户运营 / 陪聊项目
- 企业微信助手
- 客服前置问答 Agent
- 带记忆和多模态能力的个人实验项目
