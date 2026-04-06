import type { FormEvent } from "react";

type LoginShellProps = {
  loginPassword: string;
  loginError: string;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LoginShell(props: LoginShellProps) {
  const { loginPassword, loginError, onPasswordChange, onSubmit } = props;

  return (
    <main className="shell login-shell">
      <section className="hero-panel">
        <p className="eyebrow">LovAgent Studio</p>
        <h1>给 Agent 一块可调音的控制台</h1>
        <p className="hero-copy">
          在这里调节她的温柔、俏皮、边界感和记忆密度，然后直接预览系统 Prompt 和回复风格。
        </p>
        <ul className="hero-points">
          <li>全局人设滑杆和规则编辑</li>
          <li>单用户记忆、偏好、里程碑维护</li>
          <li>实时 Prompt / Reply 预览</li>
        </ul>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={onSubmit}>
          <span className="panel-chip">Admin Gate</span>
          <h2>进入后台</h2>
          <div className="default-password-card prominent-default-password">
            <strong>默认管理员密码</strong>
            <code>lovagent-admin</code>
            <span>如果你还没有在 setup 或后台里修改过密码，先用这个登录。</span>
          </div>
          <label className="field">
            <span>管理员密码</span>
            <input
              type="password"
              value={loginPassword}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="输入 ADMIN_PASSWORD"
            />
          </label>
          {loginError ? <p className="form-error">{loginError}</p> : null}
          <button className="primary-button" type="submit">
            解锁 Studio
          </button>
        </form>
      </section>
    </main>
  );
}
