import type { PersonaConfig, ResponsePreferenceKey } from "../types";
import { MetricSlider, TagEditor, TextListEditor } from "./Editors";
import { PreviewPanel } from "./PreviewPanel";

const RESPONSE_PREFERENCE_FIELDS: Array<{
  key: ResponsePreferenceKey;
  label: string;
  hint: string;
}> = [
  { key: "ultra_short_max_chars", label: "超短回复", hint: "适合“在吗 / 晚安 / 亲亲”这种一句接话。" },
  { key: "short_max_chars", label: "短回上限", hint: "常规微信往返，建议放宽到 80-120 字更自然。" },
  { key: "medium_max_chars", label: "中回上限", hint: "用户在倾诉或追问时，这一档会更常用。" },
  { key: "long_max_chars", label: "长回上限", hint: "只在复杂情绪或连续展开时允许更长回复。" },
];

type PersonaStudioProps = {
  config: PersonaConfig;
  previewMessage: string;
  previewPrompt: string;
  previewReply: string;
  previewBusy: boolean;
  selectedUserId: string;
  saving: boolean;
  onPreviewMessageChange: (value: string) => void;
  onDisplayNameChange: (value: string) => void;
  onPersonaCoreChange: (field: keyof PersonaConfig["persona_core"], value: string) => void;
  onMetricChange: (metric: string, value: number) => void;
  onPersonaListChange: (
    field: "interests" | "values" | "topics_to_avoid" | "recommended_topics" | "response_rules",
    items: string[],
  ) => void;
  onResponsePreferenceChange: (key: ResponsePreferenceKey, value: number) => void;
  onSave: () => void;
  onPreviewPrompt: () => void;
  onPreviewReply: () => void;
};

export function PersonaStudio(props: PersonaStudioProps) {
  const {
    config,
    previewMessage,
    previewPrompt,
    previewReply,
    previewBusy,
    selectedUserId,
    saving,
    onPreviewMessageChange,
    onDisplayNameChange,
    onPersonaCoreChange,
    onMetricChange,
    onPersonaListChange,
    onResponsePreferenceChange,
    onSave,
    onPreviewPrompt,
    onPreviewReply,
  } = props;

  return (
    <div className="studio-grid">
      <section className="panel aurora-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Global Persona</p>
            <h2>{config.display_name} 的气质矩阵</h2>
          </div>
          <button className="primary-button" onClick={onSave} disabled={saving}>
            {saving ? "保存中..." : "保存全局人设"}
          </button>
        </div>

        <div className="field-grid">
          <label className="field">
            <span>角色称呼</span>
            <input value={config.display_name} onChange={(event) => onDisplayNameChange(event.target.value)} />
          </label>
          <label className="field field-span">
            <span>核心角色设定</span>
            <textarea
              value={config.persona_core.role}
              onChange={(event) => onPersonaCoreChange("role", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>性格总览</span>
            <textarea
              value={config.persona_core.persona_summary}
              onChange={(event) => onPersonaCoreChange("persona_summary", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>审美与兴趣表达</span>
            <textarea
              value={config.persona_core.aesthetic}
              onChange={(event) => onPersonaCoreChange("aesthetic", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>生活方式</span>
            <textarea
              value={config.persona_core.lifestyle}
              onChange={(event) => onPersonaCoreChange("lifestyle", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>开场方式</span>
            <textarea
              value={config.persona_core.opening_style}
              onChange={(event) => onPersonaCoreChange("opening_style", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>整体风格</span>
            <textarea
              value={config.persona_core.signature_style}
              onChange={(event) => onPersonaCoreChange("signature_style", event.target.value)}
              rows={3}
            />
          </label>
          <label className="field">
            <span>表情策略</span>
            <textarea
              value={config.persona_core.emoji_style}
              onChange={(event) => onPersonaCoreChange("emoji_style", event.target.value)}
              rows={3}
            />
          </label>
        </div>

        <div className="metric-grid">
          {Object.entries(config.personality_metrics).map(([metric, value]) => (
            <MetricSlider key={metric} label={metric} value={value} onChange={(nextValue) => onMetricChange(metric, nextValue)} />
          ))}
        </div>

        <section className="response-preferences">
          <div className="tag-editor-header">
            <h3>回复长度偏好</h3>
            <span>这四档会同时影响 Prompt 提示和真实后端回复</span>
          </div>
          <div className="editor-grid">
            {RESPONSE_PREFERENCE_FIELDS.map((field) => (
              <label key={field.key} className="response-pref-card">
                <div className="response-pref-meta">
                  <strong>{field.label}</strong>
                  <span>{field.hint}</span>
                </div>
                <input
                  type="number"
                  min={12}
                  max={240}
                  step={1}
                  value={config.response_preferences[field.key]}
                  onChange={(event) => onResponsePreferenceChange(field.key, Number(event.target.value))}
                />
                <small>单位：汉字上限</small>
              </label>
            ))}
          </div>
        </section>

        <div className="editor-grid">
          <TagEditor
            label="兴趣关键词"
            items={config.interests}
            accent="coral"
            onChange={(items) => onPersonaListChange("interests", items)}
          />
          <TagEditor
            label="价值观"
            items={config.values}
            accent="mint"
            onChange={(items) => onPersonaListChange("values", items)}
          />
          <TagEditor
            label="推荐话题"
            items={config.recommended_topics}
            accent="sky"
            onChange={(items) => onPersonaListChange("recommended_topics", items)}
          />
          <TagEditor
            label="避免话题"
            items={config.topics_to_avoid}
            accent="amber"
            onChange={(items) => onPersonaListChange("topics_to_avoid", items)}
          />
        </div>

        <TextListEditor
          label="回复规则"
          items={config.response_rules}
          placeholder="新增一条规则，比如：短消息优先短回"
          onChange={(items) => onPersonaListChange("response_rules", items)}
        />
      </section>

      <PreviewPanel
        previewMessage={previewMessage}
        previewPrompt={previewPrompt}
        previewReply={previewReply}
        previewBusy={previewBusy}
        selectedUserId={selectedUserId}
        onPreviewMessageChange={onPreviewMessageChange}
        onPreviewPrompt={onPreviewPrompt}
        onPreviewReply={onPreviewReply}
      />
    </div>
  );
}
