import { z } from "zod";

export const EventSchemas = {
  "job:update": z.object({
    jobId: z.string(),
    progress: z.number().min(0).max(100),
    status: z.enum(["queued", "running", "done", "failed"]),
  }),

  analytics_update: z.object({
    completed: z.boolean(),
  }),

  "job:log": z.object({
    jobId: z.string(),
    message: z.string(),
    level: z.enum(["info", "warn", "error"]),
  }),

  "system:heartbeat": z.object({
    ts: z.number(),
  }),
} as const;

export type EventType = keyof typeof EventSchemas;

export type SSEEventMap = {
  [K in EventType]: z.infer<(typeof EventSchemas)[K]>;
};

export const EventMessageSchema = z.object({
  type: z.string(),
  userid: z.string(),
  payload: z.unknown(),
});

export function isKnownType(type: string): type is EventType {
  return type in EventSchemas;
}

export const parseEventMessage = (msg: string) => {
  let raw: unknown;

  try {
    raw = JSON.parse(msg);
  } catch {
    return undefined;
  }

  const env = EventMessageSchema.safeParse(raw);
  if (!env.success) return undefined;

  const { type, payload } = env.data;
  if (!isKnownType(type)) return undefined;

  const parsed = EventSchemas[type].safeParse(payload);
  if (!parsed.success) return undefined;

  return { type, data: parsed.data };
};
