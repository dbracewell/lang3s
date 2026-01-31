import { jsonb, pgTable, serial, text, unique } from "drizzle-orm/pg-core";

export const PrecomputedStatsTable = pgTable(
  "precomputed_stats",
  {
    id: serial("id").primaryKey(),
    name: text("name").notNull(),
    value: jsonb("value").notNull(),
  },
  (t) => [unique("precomputed_stats_name_unique").on(t.name)],
);
