import { z } from "zod";
import { EventSchemas, EventType } from "@/lib/events/eventSchemas";

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
