import type { UserMemory } from "../types";
import { KeyValueEditor, TextListEditor } from "./Editors";

type MemoryDeskProps = {
  draft: UserMemory;
  loading: boolean;
  saving: boolean;
  onMemoryFieldChange: (field: "nickname" | "avatar_url", value: string) => void;
  onKeyValueChange: (
    field: "basic_info" | "emotional_patterns" | "preferences",
    nextValue: Record<string, string>,
  ) => void;
  onMilestonesChange: (items: string[]) => void;
  onSave: () => void;
};

export function MemoryDesk(props: MemoryDeskProps) {
  const { draft, loading, saving, onMemoryFieldChange, onKeyValueChange, onMilestonesChange, onSave } = props;

  const userLabel = draft.external_user_id ? `${draft.channel}:${draft.external_user_id}` : "未选择用户";

  return (
    <div className="memory-grid">
      <section className="panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Selected User</p>
            <h2>{userLabel}</h2>
          </div>
          <button className="primary-button" onClick={onSave} disabled={saving || !draft.external_user_id}>
            {saving ? "保存中..." : "保存记忆"}
          </button>
        </div>

        {loading ? <p className="empty-state">正在加载用户记忆...</p> : null}

        <div className="field-grid">
          <label className="field">
            <span>昵称</span>
            <input value={draft.nickname} onChange={(event) => onMemoryFieldChange("nickname", event.target.value)} placeholder="比如：阿杰" />
          </label>
          <label className="field">
            <span>头像链接</span>
            <input value={draft.avatar_url} onChange={(event) => onMemoryFieldChange("avatar_url", event.target.value)} placeholder="可选" />
          </label>
        </div>

        <div className="editor-grid memory-editors">
          <KeyValueEditor label="基础信息" items={draft.basic_info} keyPlaceholder="字段名" valuePlaceholder="字段值" onChange={(nextValue) => onKeyValueChange("basic_info", nextValue)} />
          <KeyValueEditor label="情感模式" items={draft.emotional_patterns} keyPlaceholder="情绪场景" valuePlaceholder="描述" onChange={(nextValue) => onKeyValueChange("emotional_patterns", nextValue)} />
          <KeyValueEditor label="偏好" items={draft.preferences} keyPlaceholder="偏好类型" valuePlaceholder="偏好内容" onChange={(nextValue) => onKeyValueChange("preferences", nextValue)} />
        </div>

        <TextListEditor label="关系里程碑" items={draft.relationship_milestones} placeholder="新增一个里程碑，比如：第一次说想你" onChange={onMilestonesChange} />
      </section>

      <section className="panel contrast-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Recent Context</p>
            <h2>最近对话</h2>
          </div>
        </div>
        <div className="conversation-list">
          {draft.recent_conversations?.map((conversation) => (
            <article key={conversation.id} className="conversation-card">
              <p className="conversation-role">User</p>
              <p>{conversation.user_message || (conversation.message_source === "proactive" ? "（Agent 主动发起）" : "")}</p>
              <p className="conversation-role assistant-role">Agent</p>
              <p>{conversation.agent_message}</p>
            </article>
          ))}
          {!draft.recent_conversations?.length ? <p className="empty-state">这个用户还没有历史对话。</p> : null}
        </div>
      </section>
    </div>
  );
}
