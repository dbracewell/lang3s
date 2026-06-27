import z from "zod";

export const EventSchemas = {
  "job:update": z.object({
    jobId: z.number(),
    progress: z.number().min(0).max(100),
    status: z.enum(["waiting", "running", "completed", "failed", "canceled"]),
    started_at: z.string().optional(),
    completed_at: z.string().optional(),
  }),

  analytics_update: z.object({
    completed: z.boolean(),
  }),

  "agent:update": z.object({
    progress: z.number().min(0).max(100),
    prompt: z.string(),
    id: z.string(),
    response: z.string().optional(),
  }),

  "system:heartbeat": z.object({
    ts: z.number(),
  }),
} as const;

export type EventType = keyof typeof EventSchemas;
export type EventPayloadMap = {
  [K in EventType]: z.infer<(typeof EventSchemas)[K]>;
};

export type JobStatusUpdateType = z.infer<(typeof EventSchemas)["job:update"]>;
