import { buildApiUrl } from "./config";
import { normalizePersonaConfig } from "./lib/persona";
import { normalizeProactiveChatConfig } from "./lib/proactiveChat";
import type {
  PersonaConfig,
  PreviewResponse,
  ProactiveChatConfig,
  ProactiveChatResponse,
  SetupModelMode,
  SetupModelProvider,
  SetupModelRouting,
  SetupStatus,
  SetupValidationResult,
  UserMemory,
  UserSummary,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(url), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(payload.detail ?? "请求失败");
  }

  return response.json() as Promise<T>;
}

export const api = {
  me(): Promise<{ authenticated: boolean }> {
    return request("/admin-api/me");
  },
  login(password: string): Promise<{ authenticated: boolean }> {
    return request("/admin-api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
  },
  logout(): Promise<{ authenticated: boolean }> {
    return request("/admin-api/auth/logout", { method: "POST" });
  },
  getPersona(): Promise<PersonaConfig> {
    return request<PersonaConfig>("/admin-api/persona").then(normalizePersonaConfig);
  },
  savePersona(persona: PersonaConfig): Promise<PersonaConfig> {
    return request<PersonaConfig>("/admin-api/persona", {
      method: "PUT",
      body: JSON.stringify(persona),
    }).then(normalizePersonaConfig);
  },
  previewPrompt(payload: {
    user_message: string;
    channel?: string | null;
    external_user_id?: string | null;
    draft_config?: PersonaConfig;
  }): Promise<PreviewResponse> {
    return request<PreviewResponse>("/admin-api/persona/preview-prompt", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((response) => ({
      ...response,
      persona_config: normalizePersonaConfig(response.persona_config),
    }));
  },
  previewReply(payload: {
    user_message: string;
    channel?: string | null;
    external_user_id?: string | null;
    draft_config?: PersonaConfig;
  }): Promise<PreviewResponse> {
    return request<PreviewResponse>("/admin-api/persona/preview-reply", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((response) => ({
      ...response,
      persona_config: normalizePersonaConfig(response.persona_config),
    }));
  },
  listUsers(query: string): Promise<{ items: UserSummary[] }> {
    const params = new URLSearchParams();
    if (query) {
      params.set("query", query);
    }
    params.set("limit", "30");
    return request(`/admin-api/users?${params.toString()}`);
  },
  getUserMemory(channel: string, externalUserId: string): Promise<UserMemory> {
    return request(`/admin-api/users/${encodeURIComponent(channel)}/${encodeURIComponent(externalUserId)}/memory`);
  },
  saveUserMemory(channel: string, externalUserId: string, payload: UserMemory): Promise<UserMemory> {
    return request(`/admin-api/users/${encodeURIComponent(channel)}/${encodeURIComponent(externalUserId)}/memory`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  getProactiveChat(): Promise<ProactiveChatConfig> {
    return request<ProactiveChatConfig>("/admin-api/proactive-chat").then(normalizeProactiveChatConfig);
  },
  saveProactiveChat(payload: ProactiveChatConfig): Promise<ProactiveChatConfig> {
    return request<ProactiveChatConfig>("/admin-api/proactive-chat", {
      method: "PUT",
      body: JSON.stringify(payload),
    }).then(normalizeProactiveChatConfig);
  },
  previewProactiveChat(channel?: string, externalUserId?: string): Promise<ProactiveChatResponse> {
    return request<ProactiveChatResponse>("/admin-api/proactive-chat/preview", {
      method: "POST",
      body: JSON.stringify({
        channel: channel || undefined,
        external_user_id: externalUserId || undefined,
      }),
    }).then((response) => ({
      ...response,
      config: normalizeProactiveChatConfig(response.config),
    }));
  },
  runProactiveChatOnce(channel?: string, externalUserId?: string): Promise<ProactiveChatResponse> {
    return request<ProactiveChatResponse>("/admin-api/proactive-chat/run-once", {
      method: "POST",
      body: JSON.stringify({
        channel: channel || undefined,
        external_user_id: externalUserId || undefined,
      }),
    }).then((response) => ({
      ...response,
      config: normalizeProactiveChatConfig(response.config),
    }));
  },
  getSetupStatus(): Promise<SetupStatus> {
    return request("/setup/status");
  },
  saveSetupModel(payload: {
    model_provider: SetupModelProvider;
    zhipu_api_key: string;
    zhipu_model: string;
    zhipu_thinking_type?: string;
    multimodal_api_key: string;
    multimodal_model: string;
    openai_api_key: string;
    openai_base_url: string;
    openai_model_mode: SetupModelMode;
    openai_model: string;
    openai_models: SetupModelRouting;
  }): Promise<SetupStatus> {
    return request("/setup/config/model", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  saveSetupWecom(payload: {
    corp_id: string;
    agent_id: string;
    secret: string;
    token: string;
    encoding_aes_key: string;
    public_base_url: string;
  }): Promise<SetupStatus> {
    return request("/setup/config/wecom", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  saveSetupAdmin(payload: { password: string }): Promise<SetupStatus> {
    return request("/setup/config/admin", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  validateSetup(): Promise<SetupValidationResult> {
    return request("/setup/validate", {
      method: "POST",
    });
  },
  restartTunnel(): Promise<SetupStatus["tunnel"]> {
    return request("/setup/tunnel/restart", {
      method: "POST",
    });
  },
};
