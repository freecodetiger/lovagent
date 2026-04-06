import type { ProactiveChatConfig, UserSummary } from "../types";

type ProactiveStudioProps = {
  config: ProactiveChatConfig;
  users: UserSummary[];
  saving: boolean;
  busy: boolean;
  previewPrompt: string;
  previewReply: string;
  deliveryStatus: string;
  onToggleEnabled: (value: boolean) => void;
  onTargetUserChange: (value: string) => void;
  onWindowToggle: (key: string, enabled: boolean) => void;
  onWindowTimeChange: (key: string, value: string) => void;
  onQuietHoursToggle: (value: boolean) => void;
  onQuietHoursChange: (field: "start" | "end", value: string) => void;
  onNumberChange: (field: "inactivity_trigger_hours" | "max_messages_per_day" | "min_interval_minutes", value: number) => void;
  onToneHintChange: (value: string) => void;
  onSave: () => void;
  onPreview: () => void;
  onRunOnce: () => void;
};

export function ProactiveStudio(props: ProactiveStudioProps) {
  const {
    config,
    users,
    saving,
    busy,
    previewPrompt,
    previewReply,
    deliveryStatus,
    onToggleEnabled,
    onTargetUserChange,
    onWindowToggle,
    onWindowTimeChange,
    onQuietHoursToggle,
    onQuietHoursChange,
    onNumberChange,
    onToneHintChange,
    onSave,
    onPreview,
    onRunOnce,
  } = props;

  return (
    <div className="studio-grid">
      <section className="panel aurora-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Proactive Chat</p>
            <h2>主动聊天调度台</h2>
          </div>
          <button className="primary-button" onClick={onSave} disabled={saving}>
            {saving ? "保存中..." : "保存主动策略"}
          </button>
        </div>

        <div className="field-grid">
          <label className="toggle-field">
            <span>启用主动聊天</span>
            <input type="checkbox" checked={config.enabled} onChange={(event) => onToggleEnabled(event.target.checked)} />
          </label>

          <label className="field">
            <span>目标用户</span>
            <select value={config.target_wecom_user_id} onChange={(event) => onTargetUserChange(event.target.value)}>
              <option value="">请选择用户</option>
              {users.map((user) => (
                <option key={user.wecom_user_id} value={user.wecom_user_id}>
                  {user.nickname || user.wecom_user_id}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>久未互动阈值（小时）</span>
            <input
              type="number"
              min={1}
              max={168}
              value={config.inactivity_trigger_hours}
              onChange={(event) => onNumberChange("inactivity_trigger_hours", Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span>每天最多主动消息数</span>
            <input
              type="number"
              min={1}
              max={12}
              value={config.max_messages_per_day}
              onChange={(event) => onNumberChange("max_messages_per_day", Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span>最小发送间隔（分钟）</span>
            <input
              type="number"
              min={10}
              max={1440}
              value={config.min_interval_minutes}
              onChange={(event) => onNumberChange("min_interval_minutes", Number(event.target.value))}
            />
          </label>

          <label className="toggle-field">
            <span>启用免打扰</span>
            <input
              type="checkbox"
              checked={config.quiet_hours.enabled}
              onChange={(event) => onQuietHoursToggle(event.target.checked)}
            />
          </label>

          <label className="field">
            <span>免打扰开始</span>
            <input type="time" value={config.quiet_hours.start} onChange={(event) => onQuietHoursChange("start", event.target.value)} />
          </label>

          <label className="field">
            <span>免打扰结束</span>
            <input type="time" value={config.quiet_hours.end} onChange={(event) => onQuietHoursChange("end", event.target.value)} />
          </label>

          <label className="field field-span">
            <span>主动语气提示</span>
            <textarea value={config.tone_hint} rows={3} onChange={(event) => onToneHintChange(event.target.value)} />
          </label>
        </div>

        <section className="response-preferences">
          <div className="tag-editor-header">
            <h3>固定时段窗口</h3>
            <span>每个窗口当天最多主动发起一次，仍受免打扰与间隔约束</span>
          </div>
          <div className="editor-grid">
            {config.scheduled_windows.map((window) => (
              <label key={window.key} className="response-pref-card">
                <div className="response-pref-meta">
                  <strong>{window.label}</strong>
                  <span>{window.key}</span>
                </div>
                <div className="inline-editor">
                  <input type="checkbox" checked={window.enabled} onChange={(event) => onWindowToggle(window.key, event.target.checked)} />
                  <input type="time" value={window.time} onChange={(event) => onWindowTimeChange(window.key, event.target.value)} />
                </div>
              </label>
            ))}
          </div>
        </section>
      </section>

      <section className="panel contrast-panel preview-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Preview & Trigger</p>
            <h2>主动开场预览</h2>
          </div>
        </div>

        <p className="panel-chip">当前发送状态：{deliveryStatus || "尚未触发"}</p>

        <div className="preview-actions">
          <button className="secondary-button" onClick={onPreview} disabled={busy || !config.target_wecom_user_id}>
            {busy ? "处理中..." : "预览主动开场"}
          </button>
          <button className="primary-button" onClick={onRunOnce} disabled={busy || !config.target_wecom_user_id}>
            {busy ? "处理中..." : "立即发一条"}
          </button>
        </div>

        <article className="conversation-card">
          <p className="conversation-role">Prompt</p>
          <p>{previewPrompt || "保存配置后可以预览主动开场 prompt。"}</p>
        </article>

        <article className="conversation-card">
          <p className="conversation-role assistant-role">Reply</p>
          <p>{previewReply || "这里会显示主动发起时生成的消息。"}</p>
        </article>
      </section>
    </div>
  );
}
