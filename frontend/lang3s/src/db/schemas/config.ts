import { jsonb, pgTable, text } from "drizzle-orm/pg-core";

export const ConfigTable = pgTable("configuration", {
  name: text("name").primaryKey(),
  value: jsonb("value").notNull(),
});
