import { z } from "zod";
import { EventType } from "@/lib/events/types";
import { zJob } from "@/clients/core/zod.gen";

export const EventMessageSchema = z.object({
  type: z.string(),
  userId: z.string(),
  payload: z.unknown(),
});

export const EventPayloadSchemas = {
  "job:update": zJob,
  "analytics:update": z.object({
    completed: z.boolean(),
  }),
  "agent:update": z.object({
    progress: z.number().min(0).max(100),
    prompt: z.string(),
    id: z.string(),
    response: z.string().optional(),
  }),
} as const;

export type EventPayloadMap = {
  [K in EventType]: z.infer<(typeof EventPayloadSchemas)[K]>;
};
