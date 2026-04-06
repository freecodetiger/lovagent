import { FormEvent, startTransition, useDeferredValue, useEffect, useState } from "react";

import { api } from "./api";
import { LoginShell } from "./components/LoginShell";
import { MemoryDesk } from "./components/MemoryDesk";
import { PersonaStudio } from "./components/PersonaStudio";
import { ProactiveStudio } from "./components/ProactiveStudio";
import { ReplyLab } from "./components/ReplyLab";
import { SetupWizard } from "./components/SetupWizard";
import { StudioTabs, type StudioTab } from "./components/StudioTabs";
import { StudioTopbar } from "./components/StudioTopbar";
import { UserSidebar } from "./components/UserSidebar";
import { DEFAULT_PROACTIVE_CHAT_CONFIG, normalizeProactiveChatConfig } from "./lib/proactiveChat";
import { EMPTY_MEMORY, normalizeUserMemory } from "./lib/userMemory";
import type { PersonaConfig, ProactiveChatConfig, ResponsePreferenceKey, SetupStatus, UserMemory, UserSummary } from "./types";

const DEFAULT_PREVIEW_MESSAGE = "今天工作好累，但还是想和你说说话。";
const SETUP_PATH = "/setup";
const ADMIN_PATH = "/admin";

function App() {
  const [bootstrapped, setBootstrapped] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const [activeTab, setActiveTab] = useState<StudioTab>("persona");
  const [statusMessage, setStatusMessage] = useState("");

  const [personaConfig, setPersonaConfig] = useState<PersonaConfig | null>(null);
  const [personaSaving, setPersonaSaving] = useState(false);
  const [proactiveConfig, setProactiveConfig] = useState<ProactiveChatConfig>(DEFAULT_PROACTIVE_CHAT_CONFIG);
  const [proactiveSaving, setProactiveSaving] = useState(false);
  const [proactiveBusy, setProactiveBusy] = useState(false);
  const [proactivePrompt, setProactivePrompt] = useState("");
  const [proactiveReply, setProactiveReply] = useState("");
  const [proactiveDeliveryStatus, setProactiveDeliveryStatus] = useState("");

  const [previewMessage, setPreviewMessage] = useState(DEFAULT_PREVIEW_MESSAGE);
  const [previewPrompt, setPreviewPrompt] = useState("");
  const [previewReply, setPreviewReply] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);

  const [userQuery, setUserQuery] = useState("");
  const deferredUserQuery = useDeferredValue(userQuery);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [memoryDraft, setMemoryDraft] = useState<UserMemory>(EMPTY_MEMORY);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memorySaving, setMemorySaving] = useState(false);

  useEffect(() => {
    let mounted = true;

    void Promise.allSettled([api.getSetupStatus(), api.me()])
      .then((results) => {
        if (!mounted) {
          return;
        }

        const [setupResult, authResult] = results;
        if (setupResult.status === "fulfilled") {
          setSetupStatus(setupResult.value);
          if (!setupResult.value.setup_completed && window.location.pathname !== SETUP_PATH) {
            window.history.replaceState({}, "", SETUP_PATH);
          }
        }

        if (authResult.status === "fulfilled") {
          setAuthenticated(authResult.value.authenticated);
        } else {
          setAuthenticated(false);
        }
      })
      .catch(() => {
        setAuthenticated(false);
      })
      .finally(() => {
        if (mounted) {
          setBootstrapped(true);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!authenticated || !setupStatus?.setup_completed) {
      return;
    }

    void Promise.all([api.getPersona(), api.getProactiveChat(), api.listUsers("")])
      .then(([persona, proactive, userPayload]) => {
        setPersonaConfig(persona);
        setProactiveConfig(proactive);
        setUsers(userPayload.items);
        if (userPayload.items[0] && !selectedUserId) {
          setSelectedUserId(userPayload.items[0].wecom_user_id);
        }
      })
      .catch((error: Error) => {
        setStatusMessage(error.message);
      });
  }, [authenticated, selectedUserId, setupStatus?.setup_completed]);

  useEffect(() => {
    if (!authenticated || !setupStatus?.setup_completed) {
      return;
    }

    setUsersLoading(true);
    void api
      .listUsers(deferredUserQuery)
      .then((payload) => {
        setUsers(payload.items);
        if (payload.items.length === 0) {
          setSelectedUserId("");
          setMemoryDraft(EMPTY_MEMORY);
          return;
        }

        const stillExists = payload.items.some((item) => item.wecom_user_id === selectedUserId);
        if (!stillExists) {
          setSelectedUserId(payload.items[0].wecom_user_id);
        }
      })
      .catch((error: Error) => {
        setStatusMessage(error.message);
      })
      .finally(() => {
        setUsersLoading(false);
      });
  }, [authenticated, deferredUserQuery, selectedUserId, setupStatus?.setup_completed]);

  useEffect(() => {
    if (!authenticated || !setupStatus?.setup_completed || !selectedUserId) {
      return;
    }

    setMemoryLoading(true);
    void api
      .getUserMemory(selectedUserId)
      .then((payload) => {
        setMemoryDraft(normalizeUserMemory(payload));
      })
      .catch((error: Error) => {
        setStatusMessage(error.message);
      })
      .finally(() => {
        setMemoryLoading(false);
      });
  }, [authenticated, selectedUserId, setupStatus?.setup_completed]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError("");

    try {
      const result = await api.login(loginPassword);
      setAuthenticated(result.authenticated);
      setStatusMessage("管理后台已解锁。");
    } catch (error) {
      setLoginError((error as Error).message);
    }
  }

  async function handleLogout() {
    await api.logout();
    setAuthenticated(false);
    setPersonaConfig(null);
    setProactiveConfig(DEFAULT_PROACTIVE_CHAT_CONFIG);
    setPreviewPrompt("");
    setPreviewReply("");
    setStatusMessage("已退出管理后台。");
  }

  async function handleSavePersona() {
    if (!personaConfig) {
      return;
    }

    setPersonaSaving(true);
    try {
      const saved = await api.savePersona(personaConfig);
      setPersonaConfig(saved);
      setStatusMessage("全局人设已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setPersonaSaving(false);
    }
  }

  async function handlePreview(mode: "prompt" | "reply") {
    if (!personaConfig || !previewMessage.trim()) {
      return;
    }

    setPreviewBusy(true);
    try {
      const payload = {
        user_message: previewMessage,
        wecom_user_id: selectedUserId || undefined,
        draft_config: personaConfig,
      };
      const response = mode === "prompt" ? await api.previewPrompt(payload) : await api.previewReply(payload);

      setPreviewPrompt(response.prompt);
      if (response.reply) {
        setPreviewReply(response.reply);
      }
      setStatusMessage(mode === "prompt" ? "Prompt 预览已刷新。" : "回复预览已刷新。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setPreviewBusy(false);
    }
  }

  async function handleSaveMemory() {
    if (!selectedUserId) {
      return;
    }

    setMemorySaving(true);
    try {
      const saved = await api.saveUserMemory(selectedUserId, memoryDraft);
      setMemoryDraft(normalizeUserMemory(saved));
      setStatusMessage("用户记忆已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setMemorySaving(false);
    }
  }

  async function handleSaveProactiveChat() {
    setProactiveSaving(true);
    try {
      const saved = await api.saveProactiveChat(proactiveConfig);
      setProactiveConfig(saved);
      setStatusMessage("主动聊天策略已保存。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setProactiveSaving(false);
    }
  }

  async function handleProactiveAction(mode: "preview" | "run") {
    setProactiveBusy(true);
    try {
      const saved = await api.saveProactiveChat(proactiveConfig);
      setProactiveConfig(saved);

      const response =
        mode === "preview"
          ? await api.previewProactiveChat(saved.target_wecom_user_id)
          : await api.runProactiveChatOnce(saved.target_wecom_user_id);

      setProactivePrompt(response.prompt);
      setProactiveReply(response.reply);
      setProactiveDeliveryStatus(response.delivery?.status ?? (mode === "preview" ? "preview" : ""));
      setStatusMessage(mode === "preview" ? "主动开场预览已生成。" : "已触发一次主动发送。");
    } catch (error) {
      setStatusMessage((error as Error).message);
    } finally {
      setProactiveBusy(false);
    }
  }

  function updatePersonaCore(field: keyof PersonaConfig["persona_core"], value: string) {
    setPersonaConfig((current) =>
      current
        ? {
            ...current,
            persona_core: {
              ...current.persona_core,
              [field]: value,
            },
          }
        : current,
    );
  }

  function updateDisplayName(value: string) {
    setPersonaConfig((current) =>
      current
        ? {
            ...current,
            display_name: value,
          }
        : current,
    );
  }

  function updateMetric(metric: string, value: number) {
    setPersonaConfig((current) =>
      current
        ? {
            ...current,
            personality_metrics: {
              ...current.personality_metrics,
              [metric]: value,
            },
          }
        : current,
    );
  }

  function updatePersonaList(
    field: "interests" | "values" | "topics_to_avoid" | "recommended_topics" | "response_rules",
    items: string[],
  ) {
    setPersonaConfig((current) =>
      current
        ? {
            ...current,
            [field]: items,
          }
        : current,
    );
  }

  function updateResponsePreference(key: ResponsePreferenceKey, value: number) {
    const nextValue = Number.isFinite(value) ? Math.max(12, Math.min(240, Math.round(value))) : 12;
    setPersonaConfig((current) =>
      current
        ? {
            ...current,
            response_preferences: {
              ...current.response_preferences,
              [key]: nextValue,
            },
          }
        : current,
    );
  }

  function updateMemoryKeyValue(
    field: "basic_info" | "emotional_patterns" | "preferences",
    nextValue: Record<string, string>,
  ) {
    setMemoryDraft((current) => ({
      ...current,
      [field]: nextValue,
    }));
  }

  function updateMemoryField(field: "nickname" | "avatar_url", value: string) {
    setMemoryDraft((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateMilestones(items: string[]) {
    setMemoryDraft((current) => ({
      ...current,
      relationship_milestones: items,
    }));
  }

  function updateProactiveField(
    field: "enabled" | "target_wecom_user_id" | "tone_hint",
    value: boolean | string,
  ) {
    setProactiveConfig((current) =>
      normalizeProactiveChatConfig({
        ...current,
        [field]: value,
      }),
    );
  }

  function updateProactiveNumberField(
    field: "inactivity_trigger_hours" | "max_messages_per_day" | "min_interval_minutes",
    value: number,
  ) {
    setProactiveConfig((current) =>
      normalizeProactiveChatConfig({
        ...current,
        [field]: value,
      }),
    );
  }

  function updateProactiveWindow(key: string, patch: { enabled?: boolean; time?: string }) {
    setProactiveConfig((current) =>
      normalizeProactiveChatConfig({
        ...current,
        scheduled_windows: current.scheduled_windows.map((item) =>
          item.key === key
            ? {
                ...item,
                ...patch,
              }
            : item,
        ),
      }),
    );
  }

  function updateQuietHours(field: "enabled" | "start" | "end", value: boolean | string) {
    setProactiveConfig((current) =>
      normalizeProactiveChatConfig({
        ...current,
        quiet_hours: {
          ...current.quiet_hours,
          [field]: value,
        },
      }),
    );
  }

  function handleSetupStatusChange(nextStatus: SetupStatus) {
    setSetupStatus(nextStatus);
  }

  function handleEnterAdmin() {
    window.history.replaceState({}, "", ADMIN_PATH);
    setAuthenticated(true);
    setStatusMessage("环境校验完成，已进入管理后台。");
  }

  if (!bootstrapped) {
    return <div className="loading-screen">正在唤醒 LovAgent Studio...</div>;
  }

  if (!setupStatus) {
    return <div className="loading-screen">后端暂时不可用，请检查 `http://127.0.0.1:8000/health`。</div>;
  }

  if (!setupStatus.setup_completed) {
    return <SetupWizard initialStatus={setupStatus} onStatusChange={handleSetupStatusChange} onEnterAdmin={handleEnterAdmin} />;
  }

  if (window.location.pathname === SETUP_PATH) {
    return (
      <SetupWizard initialStatus={setupStatus} onStatusChange={handleSetupStatusChange} onEnterAdmin={handleEnterAdmin} />
    );
  }

  if (!authenticated) {
    return (
      <LoginShell
        loginPassword={loginPassword}
        loginError={loginError}
        onPasswordChange={setLoginPassword}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <main className="shell">
      <StudioTopbar statusMessage={statusMessage} onLogout={() => void handleLogout()} />
      <StudioTabs
        activeTab={activeTab}
        onChange={(tab) => {
          startTransition(() => {
            setActiveTab(tab);
          });
        }}
      />

      <div className="workspace">
        <UserSidebar
          userQuery={userQuery}
          users={users}
          usersLoading={usersLoading}
          selectedUserId={selectedUserId}
          onQueryChange={(value) => {
            startTransition(() => {
              setUserQuery(value);
            });
          }}
          onSelectUser={setSelectedUserId}
        />

        <section className="main-panel">
          {activeTab === "persona" && personaConfig ? (
            <PersonaStudio
              config={personaConfig}
              previewMessage={previewMessage}
              previewPrompt={previewPrompt}
              previewReply={previewReply}
              previewBusy={previewBusy}
              selectedUserId={selectedUserId}
              saving={personaSaving}
              onPreviewMessageChange={setPreviewMessage}
              onDisplayNameChange={updateDisplayName}
              onPersonaCoreChange={updatePersonaCore}
              onMetricChange={updateMetric}
              onPersonaListChange={updatePersonaList}
              onResponsePreferenceChange={updateResponsePreference}
              onSave={() => void handleSavePersona()}
              onPreviewPrompt={() => void handlePreview("prompt")}
              onPreviewReply={() => void handlePreview("reply")}
            />
          ) : null}

          {activeTab === "memory" ? (
            <MemoryDesk
              draft={memoryDraft}
              loading={memoryLoading}
              saving={memorySaving}
              onMemoryFieldChange={updateMemoryField}
              onKeyValueChange={updateMemoryKeyValue}
              onMilestonesChange={updateMilestones}
              onSave={() => void handleSaveMemory()}
            />
          ) : null}

          {activeTab === "lab" && personaConfig ? (
            <ReplyLab
              previewMessage={previewMessage}
              previewPrompt={previewPrompt}
              previewReply={previewReply}
              previewBusy={previewBusy}
              selectedUserId={selectedUserId}
              onPreviewMessageChange={setPreviewMessage}
              onPreviewPrompt={() => void handlePreview("prompt")}
              onPreviewReply={() => void handlePreview("reply")}
            />
          ) : null}

          {activeTab === "proactive" ? (
            <ProactiveStudio
              config={proactiveConfig}
              users={users}
              saving={proactiveSaving}
              busy={proactiveBusy}
              previewPrompt={proactivePrompt}
              previewReply={proactiveReply}
              deliveryStatus={proactiveDeliveryStatus}
              onToggleEnabled={(value) => updateProactiveField("enabled", value)}
              onTargetUserChange={(value) => updateProactiveField("target_wecom_user_id", value)}
              onWindowToggle={(key, enabled) => updateProactiveWindow(key, { enabled })}
              onWindowTimeChange={(key, value) => updateProactiveWindow(key, { time: value })}
              onQuietHoursToggle={(value) => updateQuietHours("enabled", value)}
              onQuietHoursChange={(field, value) => updateQuietHours(field, value)}
              onNumberChange={updateProactiveNumberField}
              onToneHintChange={(value) => updateProactiveField("tone_hint", value)}
              onSave={() => void handleSaveProactiveChat()}
              onPreview={() => void handleProactiveAction("preview")}
              onRunOnce={() => void handleProactiveAction("run")}
            />
          ) : null}
        </section>
      </div>
    </main>
  );
}

export default App;
