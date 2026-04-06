type StudioTopbarProps = {
  statusMessage: string;
  onLogout: () => void;
};

export function StudioTopbar({ statusMessage, onLogout }: StudioTopbarProps) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">LovAgent Studio</p>
        <h1>角色调音台</h1>
      </div>
      <div className="topbar-actions">
        <p className="status-banner">
          {statusMessage || "数据库配置实时生效，预览不会发送企业微信消息。"}
        </p>
        <button className="ghost-button" onClick={onLogout}>
          退出
        </button>
      </div>
    </header>
  );
}
