export type PersonaCore = {
  role: string;
  persona_summary: string;
  aesthetic: string;
  lifestyle: string;
  opening_style: string;
  signature_style: string;
  emoji_style: string;
};

export type ResponsePreferenceKey =
  | "ultra_short_max_chars"
  | "short_max_chars"
  | "medium_max_chars"
  | "long_max_chars";

export type ResponsePreferences = Record<ResponsePreferenceKey, number>;

export type PersonaConfig = {
  display_name: string;
  persona_core: PersonaCore;
  personality_metrics: Record<string, number>;
  interests: string[];
  values: string[];
  topics_to_avoid: string[];
  recommended_topics: string[];
  response_rules: string[];
  response_preferences: ResponsePreferences;
  base_persona_text?: string;
  updated_at?: string | null;
};

export type UserSummary = {
  wecom_user_id: string;
  nickname: string;
  avatar_url: string;
  total_conversations: number;
  last_interaction: string | null;
  first_interaction: string | null;
};

export type ConversationItem = {
  id: number;
  user_message: string;
  agent_message: string;
  message_source?: string;
  user_emotion: string | null;
  agent_emotion: string | null;
  created_at: string | null;
};

export type UserMemory = {
  wecom_user_id: string;
  nickname: string;
  avatar_url: string;
  basic_info: Record<string, string>;
  emotional_patterns: Record<string, string>;
  relationship_milestones: string[];
  preferences: Record<string, string>;
  recent_conversations?: ConversationItem[];
};

export type PreviewResponse = {
  prompt: string;
  persona_config: PersonaConfig;
  user_memory: UserMemory | null;
  context_messages?: Array<{ role: string; content: string }>;
  reply?: string;
};

export type ScheduledWindow = {
  key: string;
  label: string;
  enabled: boolean;
  time: string;
};

export type QuietHours = {
  enabled: boolean;
  start: string;
  end: string;
};

export type ProactiveChatConfig = {
  enabled: boolean;
  target_wecom_user_id: string;
  scheduled_windows: ScheduledWindow[];
  inactivity_trigger_hours: number;
  quiet_hours: QuietHours;
  max_messages_per_day: number;
  min_interval_minutes: number;
  tone_hint: string;
  updated_at?: string | null;
};

export type ProactiveChatResponse = {
  prompt: string;
  reply: string;
  target_wecom_user_id: string;
  user_memory: UserMemory | null;
  config: ProactiveChatConfig;
  delivery?: {
    attempted: boolean;
    status: string;
    sent_at?: string;
    error_message?: string | null;
  };
};

export type SetupModelProvider = "glm" | "openai_compatible";

export type SetupModelMode = "manual" | "auto";

export type SetupModelRouting = {
  chat_model: string;
  memory_model: string;
  proactive_model: string;
};

export type SetupStatus = {
  setup_completed: boolean;
  sections: {
    model_configured: boolean;
    wecom_configured: boolean;
    admin_configured: boolean;
    deployment_configured: boolean;
  };
  current: {
    model_provider: SetupModelProvider;
    zhipu_model: string;
    openai_model_mode: SetupModelMode;
    openai_base_url: string;
    openai_model: string;
    openai_models: SetupModelRouting;
    public_base_url: string;
    callback_url: string;
    wecom_corp_id: string;
    wecom_agent_id: string;
    has_zhipu_api_key: boolean;
    has_openai_api_key: boolean;
    has_wecom_secret: boolean;
    has_wecom_token: boolean;
    has_wecom_encoding_aes_key: boolean;
    has_admin_password: boolean;
  };
  raw: {
    model: {
      model_provider: SetupModelProvider;
      zhipu_model: string;
      openai_model_mode: SetupModelMode;
      openai_base_url: string;
      openai_model: string;
      openai_models: SetupModelRouting;
      has_zhipu_api_key: boolean;
      has_openai_api_key: boolean;
    };
    wecom: {
      corp_id: string;
      agent_id: string;
      has_secret: boolean;
      has_token: boolean;
      has_encoding_aes_key: boolean;
    };
    deployment: {
      public_base_url: string;
    };
    admin: {
      has_password: boolean;
    };
  };
  tunnel: {
    available: boolean;
    running: boolean;
    public_url: string;
    binary_path: string;
  };
};

export type SetupValidationResult = {
  all_passed: boolean;
  checks: Record<string, { ok: boolean; detail: string }>;
  status: SetupStatus;
};
