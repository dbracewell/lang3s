export const EventTypeValues = [
  "job:update",
  "analytics:update",
  "agent:update",
] as const;

export type EventType = (typeof EventTypeValues)[number];
