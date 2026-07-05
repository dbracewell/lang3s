import { EventMessageSchema, EventPayloadSchemas } from "@/lib/events/schemas";
import { EventType, EventTypeValues } from "@/lib/events/types";
import { eventBus } from "@/lib/events/eventBus";

export const eventRouter = (msg: string) => {
  let raw: unknown;
  try {
    raw = JSON.parse(msg);
  } catch {
    console.error("Unable to parse JSON", msg);
    return;
  }

  const env = EventMessageSchema.safeParse(raw);
  if (!env.success) {
    console.error("Unable to parse event", msg);
    return;
  }

  const { type, payload } = env.data;
  if (!EventTypeValues.includes(type as EventType)) {
    console.error("Unknown EventType", type);
    return;
  }

  const parsed = EventPayloadSchemas[type as EventType].safeParse(payload);
  if (!parsed.success) {
    console.error("Could not parse payload", type, payload, parsed.error);
    return;
  }

  eventBus.emit(type as EventType, parsed.data);
};
