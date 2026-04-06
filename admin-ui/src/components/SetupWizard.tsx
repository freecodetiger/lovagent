import { useEffect, useState } from "react";

import { api } from "../api";
import type { SetupStatus, SetupValidationResult } from "../types";

type SetupWizardProps = {
  initialStatus: SetupStatus;
  onStatusChange: (status: SetupStatus) => void;
  onEnterAdmin: () => void;
};

type SetupFormState = {
  zhipu_api_key: string;
  zhipu_model: string;
  corp_id: string;
  agent_id: string;
  secret: string;
  token: string;
  encoding_aes_key: string;
  public_base_url: string;
  admin_password: string;
};

const DEFAULT_FORM_STATE: SetupFormState = {
  zhipu_api_key: "",
  zhipu_model: "glm-5",
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
    zhipu_model: status.current.zhipu_model || "glm-5",
    corp_id: status.current.wecom_corp_id || status.raw.wecom.corp_id || "",
    agent_id: status.current.wecom_agent_id || status.raw.wecom.agent_id || "",
    public_base_url: status.current.public_base_url || status.tunnel.public_url || "",
  };
}

export function SetupWizard({ initialStatus, onStatusChange, onEnterAdmin }: SetupWizardProps) {
  const [form, setForm] = useState<SetupFormState>(() => buildFormState(initialStatus));
  const [statusMessage, setStatusMessage] = useState("");
  const [savingSection, setSavingSection] = useState<"" | "model" | "wecom" | "admin">("");
  const [validationResult, setValidationResult] = useState<SetupValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [tunnelBusy, setTunnelBusy] = useState(false);

  useEffect(() => {
    setForm((current) => ({
      ...current,
      zhipu_model: initialStatus.current.zhipu_model || current.zhipu_model || "glm-5",
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

  async function refreshStatus() {
    const nextStatus = await api.getSetupStatus();
    onStatusChange(nextStatus);
    return nextStatus;
  }

  async function handleSaveModel() {
    setSavingSection("model");
    setStatusMessage("");
    try {
      const nextStatus = await api.saveSetupModel({
        zhipu_api_key: form.zhipu_api_key,
        zhipu_model: form.zhipu_model,
        zhipu_thinking_type: "disabled",
      });
      onStatusChange(nextStatus);
      setStatusMessage("GLM 配置已保存。");
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

  if (setupCompleted) {
    return (
      <main className="shell setup-shell">
        <section className="hero-panel setup-hero">
          <p className="eyebrow">LovAgent Setup</p>
          <h1>当前实例已经初始化完成</h1>
          <p className="hero-copy">
            如果你需要继续调整人格、记忆、主动聊天和回复长度，请进入管理后台。运行时参数已经保存在数据库里。
          </p>
          <div className="setup-progress single-column">
            <article className="setup-step-card done">
              <strong>回调地址</strong>
              <span>{initialStatus.current.callback_url}</span>
            </article>
            <article className="setup-step-card done">
              <strong>GLM 模型</strong>
              <span>{initialStatus.current.zhipu_model}</span>
            </article>
          </div>
          <div className="setup-inline-actions">
            <button className="primary-button" onClick={onEnterAdmin}>
              进入后台
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
          只填 GLM、企业微信和管理员密码。公网地址默认优先走 Cloudflare Tunnel，保存后立即写入数据库，不需要手改
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
                进入后台
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
                <h3>GLM 接入</h3>
              </div>
              <button className="primary-button" onClick={() => void handleSaveModel()} disabled={savingSection === "model"}>
                {savingSection === "model" ? "保存中..." : "保存模型配置"}
              </button>
            </div>
            <div className="field-grid">
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
                <span>后端已接入 Web Search 触发逻辑，提到概念、新闻、价格等问题时会自动走检索。</span>
              </div>
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
          <p className="hero-copy">会依次检查本地服务、公网健康检查、GLM 调用、企业微信 access_token 和回调地址。</p>

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
