import { Activity, Database, FileText, LockKeyhole, LogIn, UserPlus } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../components/AuthContext";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

export function LoginPage() {
  const auth = useAuth();
  const toast = useToast();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!username.trim() || !password) {
      toast.error("请填写用户名和密码");
      return;
    }
    if (mode === "register" && password.length < 6) {
      toast.error("密码至少 6 位");
      return;
    }
    setBusy(true);
    try {
      const result = mode === "login" ? await api.login(username.trim(), password) : await api.register(username.trim(), password);
      auth.login(result.token, result.username);
      toast.success(mode === "login" ? "登录成功" : "注册成功");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-layout">
        <section className="auth-identity" aria-label="应用信息">
          <div className="auth-brand-mark">
            <Activity size={26} />
          </div>
          <div>
            <span className="eyebrow">本地 MVP</span>
            <h1>医疗岗位情报</h1>
            <p>Resume Lab</p>
          </div>
          <div className="auth-signal-grid">
            <div>
              <Database size={18} />
              <span>公开官网样本</span>
            </div>
            <div>
              <FileText size={18} />
              <span>结构化履历</span>
            </div>
            <div>
              <LockKeyhole size={18} />
              <span>账号数据隔离</span>
            </div>
          </div>
        </section>

        <section className="auth-card" aria-label="登录注册">
          <div className="auth-head">
            <h2>{mode === "login" ? "登录工作台" : "创建账号"}</h2>
            <p className="subtle">{mode === "login" ? "继续管理岗位样本与履历草稿" : "用于隔离你的履历和简历草稿"}</p>
          </div>
          <div className="auth-mode-switch" role="tablist" aria-label="账号操作">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
              <LogIn size={15} />
              登录
            </button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")} type="button">
              <UserPlus size={15} />
              注册
            </button>
          </div>
          <div className="form-grid">
            <label>
              <span>用户名</span>
              <input
                value={username}
                autoComplete="username"
                onChange={(event) => setUsername(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && submit()}
                placeholder="2-32 个字符"
              />
            </label>
            <label>
              <span>密码</span>
              <input
                type="password"
                value={password}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                onChange={(event) => setPassword(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && submit()}
                placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
              />
            </label>
          </div>
          <button className="primary-button auth-submit" onClick={submit} disabled={busy}>
            {mode === "login" ? <LogIn size={17} /> : <UserPlus size={17} />}
            {busy ? "处理中…" : mode === "login" ? "登录" : "注册"}
          </button>
          <p className="auth-note">提示：当前为演示环境（HTTP），请勿填写真实身份证、银行卡等敏感信息。</p>
        </section>
      </div>
    </div>
  );
}
