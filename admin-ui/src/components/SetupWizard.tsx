import { useEffect, useState } from "react";

import { api } from "../api";
import type { SetupModelProvider, SetupProviderPreset, SetupStatus, SetupValidationResult } from "../types";

const WECOM_ADMIN_URL = "https://work.weixin.qq.com/";

type SetupWizardProps = {
  initialStatus: SetupStatus;
  authenticated: boolean;
  onStatusChange: (status: SetupStatus) => void;
  onEnterAdmin: () => void;
};

type SetupFormState = {
  provider_id: SetupModelProvider;
  provider_api_key: string;
  provider_base_url: string;
  tavily_api_key: string;
  exa_api_key: string;
  search_provider_mode: string;
  corp_id: string;
  agent_id: string;
  secret: string;
  token: string;
  encoding_aes_key: string;
  public_base_url: string;
  admin_password: string;
};

const DEFAULT_FORM_STATE: SetupFormState = {
  provider_id: "zhipu",
  provider_api_key: "",
  provider_base_url: "",
  tavily_api_key: "",
  exa_api_key: "",
  search_provider_mode: "tavily_primary_exa_fallback",
  corp_id: "",
  agent_id: "",
  secret: "",
  token: "",
  encoding_aes_key: "",
  public_base_url: "",
  admin_password: "",
};

function findProviderPreset(status: SetupStatus, providerId: SetupModelProvider): SetupProviderPreset | null {
  return status.provider_catalog.find((item) => item.provider_id === providerId) || null;
}

function buildFormState(status: SetupStatus): SetupFormState {
  const providerId = status.current.provider_id || "zhipu";
  const preset = findProviderPreset(status, providerId);
  return {
    ...DEFAULT_FORM_STATE,
    provider_id: providerId,
    provider_base_url: status.current.provider_base_url || status.raw.model.provider_base_url || preset?.default_base_url || "",
    search_provider_mode: status.current.search_provider_mode || status.raw.model.search_provider_mode || "tavily_primary_exa_fallback",
    corp_id: status.current.wecom_corp_id || status.raw.wecom.corp_id || "",
    agent_id: status.current.wecom_agent_id || status.raw.wecom.agent_id || "",
    public_base_url: status.current.public_base_url || status.tunnel.public_url || "",
  };
}

function buildModelSummary(status: SetupStatus): string {
  const multimodalSummary = status.current.multimodal_configured
    ? ` / 多模态: ${status.current.multimodal_model || status.current.default_multimodal_model || "已启用"}`
    : status.current.supports_multimodal
      ? " / 多模态待启用"
      : " / 当前供应商无多模态";
  return `${status.current.provider_label || "未设置供应商"} / 文本: ${status.current.text_model || "未设置"}${multimodalSummary}`;
}

function buildModelDraftSummary(preset: SetupProviderPreset | null): string[] {
  if (!preset) {
    return ["当前供应商未识别", "保存后即时生效，无需重启后端"];
  }
  const multimodalLine = preset.supports_multimodal
    ? `多模态识别：自动使用 ${preset.default_multimodal_model || "供应商默认视觉模型"}`
    : "多模态识别：当前供应商未启用";
  return [
    `当前将使用 ${preset.label}`,
    `文本模型：自动使用 ${preset.default_text_model}`,
    preset.supports_pdf
      ? `${multimodalLine} / PDF：${preset.default_document_model || "已启用文档模型"}`
      : multimodalLine,
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
  const selectedPreset = findProviderPreset(initialStatus, form.provider_id);
  const hasStoredProviderKey = initialStatus.current.provider_id === form.provider_id && initialStatus.current.has_provider_api_key;
  const hasStoredTavilyKey = initialStatus.current.has_tavily_api_key;
  const hasStoredExaKey = initialStatus.current.has_exa_api_key;

  useEffect(() => {
    setForm((current) => ({
      ...current,
      provider_id: initialStatus.current.provider_id || current.provider_id || "zhipu",
      provider_base_url:
        current.provider_base_url ||
        initialStatus.current.provider_base_url ||
        initialStatus.raw.model.provider_base_url ||
        findProviderPreset(initialStatus, initialStatus.current.provider_id || current.provider_id || "zhipu")?.default_base_url ||
        "",
      search_provider_mode:
        current.search_provider_mode ||
        initialStatus.current.search_provider_mode ||
        initialStatus.raw.model.search_provider_mode ||
        "tavily_primary_exa_fallback",
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
    if (!form.provider_api_key.trim() && !hasStoredProviderKey) {
      return "请先填写当前供应商的 API Key。";
    }
    if (!form.provider_base_url.trim() && !selectedPreset?.default_base_url) {
      return "当前供应商缺少 Base URL。";
    }
    return "";
  }

  function handleProviderChange(nextProviderId: SetupModelProvider) {
    const preset = findProviderPreset(initialStatus, nextProviderId);
    setForm((current) => ({
      ...current,
      provider_id: nextProviderId,
      provider_base_url: preset?.default_base_url || "",
    }));
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
        provider_id: form.provider_id,
        provider_api_key: form.provider_api_key,
        provider_base_url: form.provider_base_url,
        tavily_api_key: form.tavily_api_key,
        exa_api_key: form.exa_api_key,
        search_provider_mode: form.search_provider_mode,
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
                <span>供应商</span>
                <select
                  value={form.provider_id}
                  onChange={(event) => handleProviderChange(event.target.value as SetupModelProvider)}
                >
                  {initialStatus.provider_catalog.map((preset) => (
                    <option key={preset.provider_id} value={preset.provider_id}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field field-span">
                <span>API Key</span>
                <input
                  type="password"
                  value={form.provider_api_key}
                  onChange={(event) => updateField("provider_api_key", event.target.value)}
                  placeholder={
                    hasStoredProviderKey
                      ? "已配置，可重新覆盖"
                      : `输入 ${selectedPreset?.label || "当前供应商"} API Key`
                  }
                />
              </label>
              <label className="field field-span">
                <span>Base URL</span>
                <input
                  value={form.provider_base_url}
                  onChange={(event) => updateField("provider_base_url", event.target.value)}
                  placeholder={selectedPreset?.default_base_url || "https://api.example.com/v1"}
                />
              </label>
              <label className="field">
                <span>搜索后端</span>
                <select
                  value={form.search_provider_mode}
                  onChange={(event) => updateField("search_provider_mode", event.target.value)}
                >
                  <option value="tavily_primary_exa_fallback">Tavily 主，Exa 备</option>
                  <option value="tavily">仅 Tavily</option>
                  <option value="exa">仅 Exa</option>
                  <option value="disabled">关闭搜索</option>
                </select>
              </label>
              <label className="field">
                <span>Tavily API Key</span>
                <input
                  type="password"
                  value={form.tavily_api_key}
                  onChange={(event) => updateField("tavily_api_key", event.target.value)}
                  placeholder={hasStoredTavilyKey ? "已配置，可重新覆盖" : "可选，用于 AI Search 主通道"}
                />
              </label>
              <label className="field field-span">
                <span>Exa API Key</span>
                <input
                  type="password"
                  value={form.exa_api_key}
                  onChange={(event) => updateField("exa_api_key", event.target.value)}
                  placeholder={hasStoredExaKey ? "已配置，可重新覆盖" : "可选，用于搜索回退与高质量网页抽取"}
                />
              </label>
              <div className="setup-hint-card">
                <strong>自动模型选择</strong>
                <span>你只需要选择供应商。系统会自动选择默认文本模型、图片模型，以及该供应商支持时的 PDF 文档模型。</span>
              </div>
              <div className="setup-hint-card">
                <strong>联网检索</strong>
                <span>Web Search 现在优先走 Tavily，必要时回退 Exa，不再依赖单一模型厂商的私有搜索能力。</span>
              </div>
              <div className="setup-hint-card">
                <strong>多模态能力</strong>
                <span>
                  {selectedPreset?.supports_multimodal
                    ? `图片识别已启用；${selectedPreset.supports_pdf ? `PDF 会走 ${selectedPreset.pdf_execution_mode === "responses_file_url" ? "专用文档理解链路" : selectedPreset.pdf_execution_mode === "qwen_file_id" ? "文件上传文档理解链路" : "原生 file_url 多模态链路"}。` : "当前仅自动启用图片识别，PDF 会提示降级处理。"}`
                    : "当前供应商默认不启用多模态，图片和 PDF 会走受控降级提示。"}
                </span>
              </div>
            </div>
            <div className="setup-model-summary">
              {buildModelDraftSummary(selectedPreset).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            <div className="setup-guide-card">
              <div className="setup-guide-header">
                <strong>供应商接入说明</strong>
                {selectedPreset?.docs_url ? (
                  <a className="setup-link" href={selectedPreset.docs_url} target="_blank" rel="noreferrer">
                    打开官方文档
                  </a>
                ) : null}
              </div>
              <p>
                {selectedPreset
                  ? `选择 ${selectedPreset.label} 后，只需要填写 API Key。Base URL 默认会自动带出，普通用户不需要再手填模型名称。`
                  : "选择供应商后，系统会自动填充默认接入参数。"}
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
