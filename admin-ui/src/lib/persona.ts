import type { PersonaConfig, ResponsePreferences } from "../types";

const DEFAULT_RESPONSE_PREFERENCES: ResponsePreferences = {
  ultra_short_max_chars: 30,
  short_max_chars: 55,
  medium_max_chars: 90,
  long_max_chars: 140,
};

export function normalizePersonaConfig(payload: PersonaConfig): PersonaConfig {
  return {
    ...payload,
    response_preferences: normalizeResponsePreferences(payload.response_preferences),
  };
}

function normalizeResponsePreferences(source: Partial<ResponsePreferences> | undefined): ResponsePreferences {
  return {
    ultra_short_max_chars: toBoundedNumber(source?.ultra_short_max_chars, DEFAULT_RESPONSE_PREFERENCES.ultra_short_max_chars),
    short_max_chars: toBoundedNumber(source?.short_max_chars, DEFAULT_RESPONSE_PREFERENCES.short_max_chars),
    medium_max_chars: toBoundedNumber(source?.medium_max_chars, DEFAULT_RESPONSE_PREFERENCES.medium_max_chars),
    long_max_chars: toBoundedNumber(source?.long_max_chars, DEFAULT_RESPONSE_PREFERENCES.long_max_chars),
  };
}

function toBoundedNumber(value: unknown, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  return Math.max(12, Math.min(240, Math.round(parsed)));
}
