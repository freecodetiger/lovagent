import { useEffect, useState } from "react";

import { api } from "../api";
import type { SetupModelMode, SetupModelProvider, SetupStatus, SetupValidationResult } from "../types";

const GLM_PLATFORM_URL = "https://open.bigmodel.cn/";
const WECOM_ADMIN_URL = "https://work.weixin.qq.com/";

type SetupWizardProps = {
  initialStatus: SetupStatus;
  authenticated: boolean;
  onStatusChange: (status: SetupStatus) => void;
  onEnterAdmin: () => void;
};

type SetupFormState = {
  model_provider: SetupModelProvider;
  zhipu_api_key: string;
  zhipu_model: string;
  openai_api_key: string;
  openai_base_url: string;
  openai_model_mode: SetupModelMode;
  openai_model: string;
  chat_model: string;
  memory_model: string;
  proactive_model: string;
  corp_id: string;
  agent_id: string;
  secret: string;
  token: string;
  encoding_aes_key: string;
  public_base_url: string;
  admin_password: string;
};

const DEFAULT_FORM_STATE: SetupFormState = {
  model_provider: "glm",
  zhipu_api_key: "",
  zhipu_model: "glm-5",
  openai_api_key: "",
  openai_base_url: "",
  openai_model_mode: "manual",
  openai_model: "",
  chat_model: "",
  memory_model: "",
  proactive_model: "",
  corp_id: "",
  agent_id: "",
  secret: "",
  token: "",
  encoding_aes_key: "",
  public_base_url: "",
  admin_password: "",
};

function buildFormState(status: SetupStatus): SetupFormState {
  return {
    ...DEFAULT_FORM_STATE,
    model_provider: status.current.model_provider || "glm",
    zhipu_model: status.current.zhipu_model || "glm-5",
    openai_base_url: status.current.openai_base_url || status.raw.model.openai_base_url || "",
    openai_model_mode: status.current.openai_model_mode || status.raw.model.openai_model_mode || "manual",
    openai_model: status.current.openai_model || status.raw.model.openai_model || "",
    chat_model: status.current.openai_models?.chat_model || status.raw.model.openai_models?.chat_model || "",
    memory_model: status.current.openai_models?.memory_model || status.raw.model.openai_models?.memory_model || "",
    proactive_model: status.current.openai_models?.proactive_model || status.raw.model.openai_models?.proactive_model || "",
    corp_id: status.current.wecom_corp_id || status.raw.wecom.corp_id || "",
    agent_id: status.current.wecom_agent_id || status.raw.wecom.agent_id || "",
    public_base_url: status.current.public_base_url || status.tunnel.public_url || "",
  };
}

function buildModelSummary(status: SetupStatus): string {
  if (status.current.model_provider === "openai_compatible") {
    if (status.current.openai_model_mode === "auto") {
      return `OpenAI-compatible / auto`;
    }
    return `OpenAI-compatible / ${status.current.openai_model || "未设置模型"}`;
  }
  return `GLM / ${status.current.zhipu_model || "glm-5"}`;
}

function buildModelDraftSummary(form: SetupFormState): string[] {
  if (form.model_provider === "glm") {
    return [`当前将使用 GLM`, `主模型：${form.zhipu_model || "未填写"}`, "保存后即时生效，无需重启后端"];
  }

  if (form.openai_model_mode === "auto") {
    return [
      "当前将使用 OpenAI-compatible / Auto 路由",
      `聊天：${form.chat_model || "未填写"} / 记忆：${form.memory_model || "未填写"} / 主动消息：${form.proactive_model || "未填写"}`,
      "保存后即时生效，无需重启后端",
    ];
  }

  return [
    "当前将使用 OpenAI-compatible / 手动模式",
    `统一模型：${form.openai_model || "未填写"}`,
    "保存后即时生效，无需重启后端",
  ];
}

export function SetupWizard({ initialStatus, authenticated, onStatusChange, onEnterAdmin }: SetupWizardProps) {
  const [form, setForm] = useState<SetupFormState>(() => buildFormState(initialStatus));
  const [statusMessage, setStatusMessage] = useState("");
  const [savingSection, setSavingSection] = useState<"" | "model" | "wecom" | "admin">("");
  const [validationResult, setValidationResult] = useState<SetupValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [tunnelBusy, setTunnelBusy] = useState(false);

  useEffect(() => {
    setForm((current) => ({
      ...current,
      model_provider: initialStatus.current.model_provider || current.model_provider || "glm",
      zhipu_model: initialStatus.current.zhipu_model || current.zhipu_model || "glm-5",
      openai_base_url: current.openai_base_url || initialStatus.current.openai_base_url || initialStatus.raw.model.openai_base_url || "",
      openai_model_mode: initialStatus.current.openai_model_mode || current.openai_model_mode || "manual",
      openai_model: current.openai_model || initialStatus.current.openai_model || initialStatus.raw.model.openai_model || "",
      chat_model:
        current.chat_model || initialStatus.current.openai_models?.chat_model || initialStatus.raw.model.openai_models?.chat_model || "",
      memory_model:
        current.memory_model || initialStatus.current.openai_models?.memory_model || initialStatus.raw.model.openai_models?.memory_model || "",
      proactive_model:
        current.proactive_model ||
        initialStatus.current.openai_models?.proactive_model ||
        initialStatus.raw.model.openai_models?.proactive_model ||
        "",
      corp_id: current.corp_id || initialStatus.current.wecom_corp_id || initialStatus.raw.wecom.corp_id || "",
      agent_id: current.agent_id || initialStatus.current.wecom_agent_id || initialStatus.raw.wecom.agent_id || "",
      public_base_url:
        current.public_base_url || initialStatus.current.public_base_url || initialStatus.tunnel.public_url || "",
    }));
  }, [initialStatus]);

  function updateField<K extends keyof SetupFormState>(field: K, value: SetupFormState[K]) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function validateModelForm(): string {
    if (form.model_provider === "glm") {
      if (!form.zhipu_api_key.trim() && !initialStatus.current.has_zhipu_api_key) {
        return "GLM 模式下请先填写 API Key。";
      }
      if (!form.zhipu_model.trim()) {
        return "GLM 模式下请填写模型名称。";
      }
      return "";
    }

    if (!form.openai_api_key.trim() && !initialStatus.current.has_openai_api_key) {
      return "OpenAI-compatible 模式下请先填写 API Key。";
    }
    if (!form.openai_base_url.trim()) {
      return "OpenAI-compatible 模式下请填写 Base URL。";
    }
    if (form.openai_model_mode === "manual" && !form.openai_model.trim()) {
      return "手动模式下请填写模型名称。";
    }
    if (form.openai_model_mode === "auto") {
      if (!form.chat_model.trim()) {
        return "Auto 模式下请填写聊天模型。";
      }
      if (!form.memory_model.trim()) {
        return "Auto 模式下请填写记忆模型。";
      }
      if (!form.proactive_model.trim()) {
        return "Auto 模式下请填写主动消息模型。";
      }
    }
    return "";
  }

  async function refreshStatus() {
    const nextStatus = await api.getSetupStatus();
    onStatusChange(nextStatus);
    return nextStatus;
  }

  async function handleSaveModel() {
    setSavingSection("model");
    setStatusMessage("");
    const validationMessage = validateModelForm();
    if (validationMessage) {
      setStatusMessage(validationMessage);
      setSavingSection("");
      return;
    }
    try {
      const nextStatus = await api.saveSetupModel({
        model_provider: form.model_provider,
        zhipu_api_key: form.zhipu_api_key,
        zhipu_model: form.zhipu_model,
        zhipu_thinking_type: "disabled",
        openai_api_key: form.openai_api_key,
        openai_base_url: form.openai_base_url,
        openai_model_mode: form.openai_model_mode,
        openai_model: form.openai_model,
        openai_models: {
          chat_model: form.chat_model,
          memory_model: form.memory_model,
          proactive_model: form.proactive_model,
        },
      });
      onStatusChange(nextStatus);
      setStatusMessage("模型配置已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setSavingSection("");
    }
  }

  async function handleSaveWecom() {
    setSavingSection("wecom");
    setStatusMessage("");
    try {
      const nextStatus = await api.saveSetupWecom({
        corp_id: form.corp_id,
        agent_id: form.agent_id,
        secret: form.secret,
        token: form.token,
        encoding_aes_key: form.encoding_aes_key,
        public_base_url: form.public_base_url,
      });
      onStatusChange(nextStatus);
      setStatusMessage("企业微信与回调地址已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setSavingSection("");
    }
  }

  async function handleSaveAdmin() {
    setSavingSection("admin");
    setStatusMessage("");
    try {
      const nextStatus = await api.saveSetupAdmin({ password: form.admin_password });
      onStatusChange(nextStatus);
      setStatusMessage("管理员密码已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setSavingSection("");
    }
  }

  async function handleRestartTunnel() {
    setTunnelBusy(true);
    setStatusMessage("");
    try {
      await api.restartTunnel();
      const nextStatus = await refreshStatus();
      if (!form.public_base_url && nextStatus.tunnel.public_url) {
        updateField("public_base_url", nextStatus.tunnel.public_url);
      }
      setStatusMessage(nextStatus.tunnel.public_url ? "Tunnel 已重启并拿到新的公网地址。" : "Tunnel 已重启。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setTunnelBusy(false);
    }
  }

  async function handleValidateAndEnter() {
    setValidating(true);
    setStatusMessage("");
    try {
      const result = await api.validateSetup();
      setValidationResult(result);
      onStatusChange(result.status);

      if (result.all_passed && form.admin_password) {
        await api.login(form.admin_password);
        onEnterAdmin();
        return;
      }

      setStatusMessage(result.all_passed ? "环境校验通过，可以进入后台。" : "校验未全部通过，请先处理失败项。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setValidating(false);
    }
  }

  const callbackUrl = `${(form.public_base_url || initialStatus.current.public_base_url || "").replace(/\/$/, "")}/wecom/callback`;
  const setupCompleted = initialStatus.setup_completed;

  if (setupCompleted && !authenticated) {
    return (
      <main className="shell setup-shell">
        <section className="hero-panel setup-hero">
          <p className="eyebrow">LovAgent Setup</p>
          <h1>当前实例已经初始化完成</h1>
          <p className="hero-copy">
            当前运行时参数已经生效。如果你要继续调整模型、回调地址或企业微信参数，请先进入后台登录管理员账号。
          </p>
          <div className="setup-progress single-column">
            <article className="setup-step-card done">
              <strong>回调地址</strong>
              <span>{initialStatus.current.callback_url}</span>
            </article>
            <article className="setup-step-card done">
              <strong>当前模型</strong>
              <span>{buildModelSummary(initialStatus)}</span>
            </article>
          </div>
          <div className="setup-inline-actions">
            <button className="primary-button" onClick={onEnterAdmin}>
              进入后台登录
            </button>
            <button className="ghost-button" onClick={() => void refreshStatus()}>
              刷新状态
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="shell setup-shell">
      <section className="hero-panel setup-hero">
        <p className="eyebrow">LovAgent Setup</p>
        <h1>五分钟把恋爱 Agent 接起来</h1>
        <p className="hero-copy">
          {setupCompleted
            ? "当前实例已经初始化完成。你现在看到的是可继续编辑的运行时配置页，保存后立即生效，不需要重启后端。"
            : "只填模型、企业微信和管理员密码。公网地址默认优先走 Cloudflare Tunnel，保存后立即写入数据库，不需要手改"}
          <code> .env </code>。
        </p>
        <div className="setup-progress">
          <article className={`setup-step-card ${initialStatus.sections.model_configured ? "done" : ""}`}>
            <strong>1. 模型</strong>
            <span>{initialStatus.sections.model_configured ? "已配置" : "待填写 API Key"}</span>
          </article>
          <article className={`setup-step-card ${initialStatus.sections.wecom_configured ? "done" : ""}`}>
            <strong>2. 企业微信</strong>
            <span>{initialStatus.sections.wecom_configured ? "参数完整" : "导入 Corp/Agent/Secret"}</span>
          </article>
          <article className={`setup-step-card ${initialStatus.sections.deployment_configured ? "done" : ""}`}>
            <strong>3. 回调地址</strong>
            <span>{initialStatus.current.callback_url}</span>
          </article>
          <article className={`setup-step-card ${initialStatus.sections.admin_configured ? "done" : ""}`}>
            <strong>4. 后台入口</strong>
            <span>{initialStatus.sections.admin_configured ? "已设置密码" : "创建管理员密码"}</span>
          </article>
        </div>
      </section>

      <section className="setup-board">
        <header className="setup-board-header">
          <div>
            <p className="section-kicker">Quick Deploy</p>
            <h2>{setupCompleted ? "环境已就绪" : "初始化向导"}</h2>
          </div>
          <div className="setup-board-actions">
            <button className="ghost-button" onClick={() => void refreshStatus()}>
              刷新状态
            </button>
            {setupCompleted ? (
              <button className="primary-button" onClick={onEnterAdmin}>
                返回后台
              </button>
            ) : null}
          </div>
        </header>

        {statusMessage ? <p className="status-banner setup-status-banner">{statusMessage}</p> : null}

        <div className="setup-grid">
          <section className="panel setup-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">Model</p>
                <h3>模型接入</h3>
              </div>
              <button className="primary-button" onClick={() => void handleSaveModel()} disabled={savingSection === "model"}>
                {savingSection === "model" ? "保存中..." : "保存模型配置"}
              </button>
            </div>
            <div className="field-grid">
              <label className="field">
                <span>Provider</span>
                <select
                  value={form.model_provider}
                  onChange={(event) => updateField("model_provider", event.target.value as SetupModelProvider)}
                >
                  <option value="glm">GLM</option>
                  <option value="openai_compatible">OpenAI-compatible</option>
                </select>
              </label>
              {form.model_provider === "glm" ? (
                <>
                  <label className="field field-span">
                    <span>GLM API Key</span>
                    <input
                      type="password"
                      value={form.zhipu_api_key}
                      onChange={(event) => updateField("zhipu_api_key", event.target.value)}
                      placeholder={initialStatus.current.has_zhipu_api_key ? "已配置，可重新覆盖" : "输入智谱 API Key"}
                    />
                  </label>
                  <label className="field">
                    <span>模型名称</span>
                    <select value={form.zhipu_model} onChange={(event) => updateField("zhipu_model", event.target.value)}>
                      <option value="glm-5">glm-5</option>
                      <option value="glm-4.5">glm-4.5</option>
                      <option value="glm-4.5-air">glm-4.5-air</option>
                    </select>
                  </label>
                  <div className="setup-hint-card">
                    <strong>联网检索</strong>
                    <span>GLM provider 下会继续启用现有 Web Search 触发逻辑。</span>
                  </div>
                </>
              ) : (
                <>
                  <label className="field field-span">
                    <span>OpenAI-compatible API Key</span>
                    <input
                      type="password"
                      value={form.openai_api_key}
                      onChange={(event) => updateField("openai_api_key", event.target.value)}
                      placeholder={initialStatus.current.has_openai_api_key ? "已配置，可重新覆盖" : "输入兼容接口 API Key"}
                    />
                  </label>
                  <label className="field field-span">
                    <span>Base URL</span>
                    <input
                      value={form.openai_base_url}
                      onChange={(event) => updateField("openai_base_url", event.target.value)}
                      placeholder="https://api.example.com/v1"
                    />
                  </label>
                  <label className="field">
                    <span>模型模式</span>
                    <select
                      value={form.openai_model_mode}
                      onChange={(event) => updateField("openai_model_mode", event.target.value as SetupModelMode)}
                    >
                      <option value="manual">手动指定</option>
                      <option value="auto">Auto 按任务路由</option>
                    </select>
                  </label>
                  {form.openai_model_mode === "manual" ? (
                    <label className="field">
                      <span>模型名称</span>
                      <input
                        value={form.openai_model}
                        onChange={(event) => updateField("openai_model", event.target.value)}
                        placeholder="gpt-4o-mini / qwen-plus / deepseek-chat"
                      />
                    </label>
                  ) : (
                    <>
                      <label className="field">
                        <span>聊天模型</span>
                        <input
                          value={form.chat_model}
                          onChange={(event) => updateField("chat_model", event.target.value)}
                          placeholder="普通对话 / 回复预览"
                        />
                      </label>
                      <label className="field">
                        <span>记忆模型</span>
                        <input
                          value={form.memory_model}
                          onChange={(event) => updateField("memory_model", event.target.value)}
                          placeholder="结构化记忆提炼"
                        />
                      </label>
                      <label className="field">
                        <span>主动消息模型</span>
                        <input
                          value={form.proactive_model}
                          onChange={(event) => updateField("proactive_model", event.target.value)}
                          placeholder="主动聊天文案"
                        />
                      </label>
                    </>
                  )}
                  <div className="setup-hint-card">
                    <strong>兼容接口说明</strong>
                    <span>支持 OpenAI 风格 `/chat/completions` 接口。auto 模式会按聊天、记忆、主动消息三类任务分别选模型。</span>
                  </div>
                </>
              )}
            </div>
            <div className="setup-model-summary">
              {buildModelDraftSummary(form).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            <div className="setup-guide-card">
              <div className="setup-guide-header">
                <strong>{form.model_provider === "glm" ? "先去官方平台获取 API Key" : "准备兼容接口参数"}</strong>
                {form.model_provider === "glm" ? (
                  <a className="setup-link" href={GLM_PLATFORM_URL} target="_blank" rel="noreferrer">
                    打开智谱开放平台
                  </a>
                ) : null}
              </div>
              <p>
                {form.model_provider === "glm"
                  ? "登录后在智谱开放平台控制台中创建或查看 API Key，再回到这里粘贴即可。"
                  : "填写任何 OpenAI 风格兼容接口的 Base URL、API Key 和模型名称即可，模型名称支持自由输入。"}
              </p>
            </div>
          </section>

          <section className="panel setup-panel contrast-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">Tunnel</p>
                <h3>公网回调入口</h3>
              </div>
              <button className="ghost-button light-button" onClick={() => void handleRestartTunnel()} disabled={tunnelBusy}>
                {tunnelBusy ? "重启中..." : "重启 Tunnel"}
              </button>
            </div>
            <div className="setup-metrics">
              <div className="metric-tile">
                <span>cloudflared</span>
                <strong>{initialStatus.tunnel.available ? "已就绪" : "未安装"}</strong>
              </div>
              <div className="metric-tile">
                <span>运行状态</span>
                <strong>{initialStatus.tunnel.running ? "运行中" : "未运行"}</strong>
              </div>
            </div>
            <label className="field">
              <span>Public Base URL</span>
              <input
                value={form.public_base_url}
                onChange={(event) => updateField("public_base_url", event.target.value)}
                placeholder="https://xxxx.trycloudflare.com"
              />
            </label>
            <div className="setup-inline-actions">
              <button
                className="ghost-button light-button"
                onClick={() => updateField("public_base_url", initialStatus.tunnel.public_url)}
                disabled={!initialStatus.tunnel.public_url}
              >
                使用当前 Tunnel 地址
              </button>
              <span className="tiny-tag">{initialStatus.tunnel.public_url || "等待 tunnel 返回公网地址"}</span>
            </div>
            <p className="setup-code-line">{callbackUrl === "/wecom/callback" ? "回调地址待生成" : callbackUrl}</p>
            <div className="setup-guide-card dark-guide-card">
              <strong>企业微信白名单提醒</strong>
              <p>
                如果客户端消息能进来，但 Agent 回复发送失败，优先检查企业微信的可信 IP / IP 白名单。
              </p>
              <p>
                在当前部署机器执行 <code>curl https://api.ipify.org</code>，拿到公网出口 IP 后，再去企业微信后台补到白名单。
              </p>
            </div>
          </section>

          <section className="panel setup-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">WeCom</p>
                <h3>企业微信参数</h3>
              </div>
              <button className="primary-button" onClick={() => void handleSaveWecom()} disabled={savingSection === "wecom"}>
                {savingSection === "wecom" ? "保存中..." : "保存企业微信配置"}
              </button>
            </div>
            <div className="field-grid">
              <label className="field">
                <span>企业 ID</span>
                <input value={form.corp_id} onChange={(event) => updateField("corp_id", event.target.value)} />
              </label>
              <label className="field">
                <span>Agent ID</span>
                <input value={form.agent_id} onChange={(event) => updateField("agent_id", event.target.value)} />
              </label>
              <label className="field field-span">
                <span>Secret</span>
                <input
                  type="password"
                  value={form.secret}
                  onChange={(event) => updateField("secret", event.target.value)}
                  placeholder={initialStatus.current.has_wecom_secret ? "已配置，可重新覆盖" : "输入 Secret"}
                />
              </label>
              <label className="field">
                <span>Token</span>
                <input
                  type="password"
                  value={form.token}
                  onChange={(event) => updateField("token", event.target.value)}
                  placeholder={initialStatus.current.has_wecom_token ? "已配置，可重新覆盖" : "企业微信后台 Token"}
                />
              </label>
              <label className="field">
                <span>EncodingAESKey</span>
                <input
                  type="password"
                  value={form.encoding_aes_key}
                  onChange={(event) => updateField("encoding_aes_key", event.target.value)}
                  placeholder={
                    initialStatus.current.has_wecom_encoding_aes_key ? "已配置，可重新覆盖" : "企业微信后台 EncodingAESKey"
                  }
                />
              </label>
            </div>
            <div className="setup-guide-card">
              <div className="setup-guide-header">
                <strong>企业微信后台操作路径</strong>
                <a className="setup-link" href={WECOM_ADMIN_URL} target="_blank" rel="noreferrer">
                  打开企业微信管理后台
                </a>
              </div>
              <ul className="setup-guide-list">
                <li>先登录企业微信网页版后台，创建企业的“自建应用”。</li>
                <li>企业 ID 在首页的“认证主体信息”中获取。</li>
                <li>AgentID 和 Secret 在“应用管理”里的自建应用详情页中获取。</li>
                <li>在“接收消息”功能块里点“设置 API 接收”，填写上面的回调 URL。</li>
                <li>保存 API 接收配置后，把 Token 和 EncodingAESKey 回填到这里。</li>
              </ul>
            </div>
          </section>

          <section className="panel setup-panel">
            <div className="section-header">
              <div>
                <p className="section-kicker">Admin</p>
                <h3>后台密码</h3>
              </div>
              <button className="primary-button" onClick={() => void handleSaveAdmin()} disabled={savingSection === "admin"}>
                {savingSection === "admin" ? "保存中..." : "保存管理员密码"}
              </button>
            </div>
            <label className="field">
              <span>管理员密码</span>
              <input
                type="password"
                minLength={6}
                value={form.admin_password}
                onChange={(event) => updateField("admin_password", event.target.value)}
                placeholder={initialStatus.current.has_admin_password ? "已配置，可输入后重新覆盖" : "至少 6 位"}
              />
            </label>
            <div className="default-password-card">
              <strong>默认管理员密码</strong>
              <code>lovagent-admin</code>
              <span>如果你还没改过，角色调音台登录页默认就是这个密码。</span>
            </div>
            <p className="hero-copy">密码会保存到数据库运行时配置中；如果你已经保存过，留空不会展示旧值。</p>
          </section>
        </div>

        <section className="panel setup-validation-panel">
          <div className="section-header">
            <div>
              <p className="section-kicker">Validation</p>
              <h3>连通性校验</h3>
            </div>
            <button className="primary-button" onClick={() => void handleValidateAndEnter()} disabled={validating}>
              {validating ? "校验中..." : "校验并进入后台"}
            </button>
          </div>
          <p className="hero-copy">会依次检查本地服务、公网健康检查、当前模型 provider 调用、企业微信 access_token 和回调地址。</p>

          {validationResult ? (
            <div className="validation-grid">
              {Object.entries(validationResult.checks).map(([key, value]) => (
                <article key={key} className={`validation-card ${value.ok ? "ok" : "fail"}`}>
                  <strong>{key}</strong>
                  <span>{value.ok ? "通过" : "失败"}</span>
                  <p>{value.detail}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-state">还没开始校验。建议先保存四个区块，再执行一次完整验证。</p>
          )}
        </section>
      </section>
    </main>
  );
}
