import type { UserSummary } from "../types";

type UserSidebarProps = {
  userQuery: string;
  users: UserSummary[];
  usersLoading: boolean;
  selectedUserId: string;
  onQueryChange: (value: string) => void;
  onSelectUser: (channel: string, externalUserId: string) => void;
};

export function UserSidebar(props: UserSidebarProps) {
  const { userQuery, users, usersLoading, selectedUserId, onQueryChange, onSelectUser } = props;

  return (
    <aside className="sidebar-panel">
      <section className="sidebar-section">
        <div className="section-header">
          <div>
            <p className="section-kicker">User Lens</p>
            <h2>单用户记忆</h2>
          </div>
          {usersLoading ? <span className="tiny-tag">刷新中</span> : null}
        </div>

        <input
          className="search-input"
          value={userQuery}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索用户 ID 或昵称"
        />

        <div className="user-list">
          {users.map((user) => (
            <button
              key={`${user.channel}:${user.external_user_id}`}
              className={user.external_user_id === selectedUserId ? "user-card active" : "user-card"}
              onClick={() => onSelectUser(user.channel, user.external_user_id)}
            >
              <strong>{user.nickname || user.external_user_id}</strong>
              <span>{user.channel}:{user.external_user_id}</span>
              <em>{user.total_conversations} 次对话</em>
            </button>
          ))}

          {!users.length ? <p className="empty-state">还没有可编辑用户，先收一条消息。</p> : null}
        </div>
      </section>
    </aside>
  );
}
