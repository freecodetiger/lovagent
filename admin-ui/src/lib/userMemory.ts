import type { UserMemory } from "../types";

export const EMPTY_MEMORY: UserMemory = {
  wecom_user_id: "",
  nickname: "",
  avatar_url: "",
  basic_info: {},
  emotional_patterns: {},
  relationship_milestones: [],
  preferences: {},
  recent_conversations: [],
};

export function normalizeUserMemory(payload: UserMemory): UserMemory {
  return {
    ...EMPTY_MEMORY,
    ...payload,
    basic_info: normalizeRecord(payload.basic_info),
    emotional_patterns: normalizeRecord(payload.emotional_patterns),
    preferences: normalizeRecord(payload.preferences),
    relationship_milestones: (payload.relationship_milestones ?? []).map((item) =>
      typeof item === "string" ? item : JSON.stringify(item, null, 2),
    ),
    recent_conversations: payload.recent_conversations ?? [],
  };
}

function normalizeRecord(source: Record<string, unknown> | undefined): Record<string, string> {
  if (!source) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(source).map(([key, value]) => [key, stringifyValue(value)]),
  );
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join("、");
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}
