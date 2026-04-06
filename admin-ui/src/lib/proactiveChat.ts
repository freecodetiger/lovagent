import type { ProactiveChatConfig, QuietHours, ScheduledWindow } from "../types";

const DEFAULT_WINDOWS: ScheduledWindow[] = [
  { key: "morning", label: "上午", enabled: true, time: "09:30" },
  { key: "afternoon", label: "下午", enabled: true, time: "15:00" },
  { key: "night", label: "夜晚", enabled: true, time: "21:00" },
];

const DEFAULT_QUIET_HOURS: QuietHours = {
  enabled: true,
  start: "23:00",
  end: "09:00",
};

export const DEFAULT_PROACTIVE_CHAT_CONFIG: ProactiveChatConfig = {
  enabled: false,
  target_wecom_user_id: "",
  scheduled_windows: DEFAULT_WINDOWS,
  inactivity_trigger_hours: 6,
  quiet_hours: DEFAULT_QUIET_HOURS,
  max_messages_per_day: 4,
  min_interval_minutes: 180,
  tone_hint: "像突然想起我一样，自然一点，别像打卡问候。",
};

export function normalizeProactiveChatConfig(payload: Partial<ProactiveChatConfig> | null | undefined): ProactiveChatConfig {
  if (!payload) {
    return {
      ...DEFAULT_PROACTIVE_CHAT_CONFIG,
      scheduled_windows: DEFAULT_WINDOWS.map((item) => ({ ...item })),
      quiet_hours: { ...DEFAULT_QUIET_HOURS },
    };
  }

  return {
    ...DEFAULT_PROACTIVE_CHAT_CONFIG,
    ...payload,
    scheduled_windows: normalizeWindows(payload.scheduled_windows),
    quiet_hours: normalizeQuietHours(payload.quiet_hours),
    inactivity_trigger_hours: toBoundedNumber(payload.inactivity_trigger_hours, 6, 1, 168),
    max_messages_per_day: toBoundedNumber(payload.max_messages_per_day, 4, 1, 12),
    min_interval_minutes: toBoundedNumber(payload.min_interval_minutes, 180, 10, 1440),
    tone_hint: String(payload.tone_hint ?? DEFAULT_PROACTIVE_CHAT_CONFIG.tone_hint),
  };
}

function normalizeWindows(value: ScheduledWindow[] | undefined): ScheduledWindow[] {
  const source = Array.isArray(value) && value.length > 0 ? value : DEFAULT_WINDOWS;
  return source.map((item, index) => ({
    key: String(item?.key ?? DEFAULT_WINDOWS[index]?.key ?? `window-${index}`),
    label: String(item?.label ?? DEFAULT_WINDOWS[index]?.label ?? `时段 ${index + 1}`),
    enabled: Boolean(item?.enabled ?? DEFAULT_WINDOWS[index]?.enabled ?? true),
    time: normalizeTime(item?.time ?? DEFAULT_WINDOWS[index]?.time ?? "09:30"),
  }));
}

function normalizeQuietHours(value: QuietHours | undefined): QuietHours {
  return {
    enabled: Boolean(value?.enabled ?? DEFAULT_QUIET_HOURS.enabled),
    start: normalizeTime(value?.start ?? DEFAULT_QUIET_HOURS.start),
    end: normalizeTime(value?.end ?? DEFAULT_QUIET_HOURS.end),
  };
}

function normalizeTime(value: string): string {
  return /^\d{2}:\d{2}$/.test(value) ? value : "09:30";
}

function toBoundedNumber(value: number | undefined, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.round(parsed)));
}
