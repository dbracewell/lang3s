import { user } from "@/lib/db/schema";
import {
  integer,
  json,
  pgEnum,
  pgTable,
  serial,
  text,
  timestamp,
  varchar,
} from "drizzle-orm/pg-core";

////////////////////////////////////////////////////////////////////////////////
// Jobs Table
////////////////////////////////////////////////////////////////////////////////
export const jobStatuses = [
  "waiting",
  "processing",
  "complete",
  "failed",
] as const;

export type JobStatusType = (typeof jobStatuses)[number];
export const jobStatusEnum = pgEnum("job_status", jobStatuses);

export const jobTypes = ["annotation", "update", "other"] as const;
export type JobType = (typeof jobTypes)[number];
export const jobTypEnum = pgEnum("job_type", jobTypes);

export const JobsTable = pgTable("jobs", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  apiKey: text("apiKey"),
  userId: text("user_id")
    .references(() => user.id, { onDelete: "cascade" })
    .notNull(),
  status: jobStatusEnum("status").notNull().default("waiting"),
  total: integer("total").notNull().default(0),
  completed: integer("completed").notNull().default(0),
  failed: integer("failed").notNull().default(0),
  jobType: jobTypEnum("job_type").notNull().default("other"),
  metadata: json("metadata").notNull().default({}),
  createdAt: timestamp("created_at").defaultNow(),
  startedAt: timestamp("started_at"),
  completedAt: timestamp("completed_at"),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => new Date()),
});
