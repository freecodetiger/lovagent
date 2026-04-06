type PreviewPanelProps = {
  previewMessage: string;
  previewPrompt: string;
  previewReply: string;
  previewBusy: boolean;
  selectedUserId: string;
  onPreviewMessageChange: (value: string) => void;
  onPreviewPrompt: () => void;
  onPreviewReply: () => void;
};

export function PreviewPanel(props: PreviewPanelProps) {
  const {
    previewMessage,
    previewPrompt,
    previewReply,
    previewBusy,
    selectedUserId,
    onPreviewMessageChange,
    onPreviewPrompt,
    onPreviewReply,
  } = props;

  return (
    <section className="panel preview-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Instant Preview</p>
          <h2>Reply Lab</h2>
        </div>
        <span className="tiny-tag">
          {selectedUserId ? `当前用户: ${selectedUserId}` : "未选择用户，按全局默认预览"}
        </span>
      </div>

      <label className="field">
        <span>测试消息</span>
        <textarea
          value={previewMessage}
          onChange={(event) => onPreviewMessageChange(event.target.value)}
          rows={4}
        />
      </label>

      <div className="preview-actions">
        <button className="secondary-button" onClick={onPreviewPrompt} disabled={previewBusy}>
          {previewBusy ? "生成中..." : "预览 Prompt"}
        </button>
        <button className="primary-button" onClick={onPreviewReply} disabled={previewBusy}>
          {previewBusy ? "生成中..." : "预览回复"}
        </button>
      </div>

      <label className="field">
        <span>系统 Prompt</span>
        <textarea value={previewPrompt} readOnly rows={14} />
      </label>

      <label className="field">
        <span>模型回复</span>
        <textarea value={previewReply} readOnly rows={5} />
      </label>
    </section>
  );
}
