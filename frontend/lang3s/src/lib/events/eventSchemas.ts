import z from "zod";

export const EventSchemas = {
  "job:update": z.object({
    jobId: z.number(),
    progress: z.number().min(0).max(100),
    status: z.enum(["waiting", "processing", "complete", "failed"]),
  }),

  analytics_update: z.object({
    completed: z.boolean(),
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
