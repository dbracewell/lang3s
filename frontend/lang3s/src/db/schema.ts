import { relations, sql } from "drizzle-orm";
import {
  index,
  json,
  pgTable,
  text,
  timestamp,
  boolean,
  uuid,
  integer,
  vector,
  serial,
  varchar,
  pgEnum,
} from "drizzle-orm/pg-core";
import { number } from "zod";

export const EMBEDDING_DIMENSIONS = 768;

////////////////////////////////////////////////////////////////////////////////
// Auth Tables
////////////////////////////////////////////////////////////////////////////////
export const user = pgTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: boolean("email_verified").default(false).notNull(),
  image: text("image"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => /* @__PURE__ */ new Date())
    .notNull(),
  role: text("role"),
  banned: boolean("banned").default(false),
  banReason: text("ban_reason"),
  banExpires: timestamp("ban_expires"),
  username: text("username").unique(),
  displayUsername: text("display_username"),
});

export const session = pgTable("session", {
  id: text("id").primaryKey(),
  expiresAt: timestamp("expires_at").notNull(),
  token: text("token").notNull().unique(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at")
    .$onUpdate(() => /* @__PURE__ */ new Date())
    .notNull(),
  ipAddress: text("ip_address"),
  userAgent: text("user_agent"),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  impersonatedBy: text("impersonated_by"),
});

export const account = pgTable("account", {
  id: text("id").primaryKey(),
  accountId: text("account_id").notNull(),
  providerId: text("provider_id").notNull(),
  userId: text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  accessToken: text("access_token"),
  refreshToken: text("refresh_token"),
  idToken: text("id_token"),
  accessTokenExpiresAt: timestamp("access_token_expires_at"),
  refreshTokenExpiresAt: timestamp("refresh_token_expires_at"),
  scope: text("scope"),
  password: text("password"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at")
    .$onUpdate(() => /* @__PURE__ */ new Date())
    .notNull(),
});

export const verification = pgTable("verification", {
  id: text("id").primaryKey(),
  identifier: text("identifier").notNull(),
  value: text("value").notNull(),
  expiresAt: timestamp("expires_at").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => /* @__PURE__ */ new Date())
    .notNull(),
});
////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////
// Documents Table
////////////////////////////////////////////////////////////////////////////////
export const DocumentsTable = pgTable("documents", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  metadata: json("metadata")
    .$type<Record<string, unknown>>()
    .notNull()
    .default({}),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => new Date()),
});

export const DocumentRelations = relations(DocumentsTable, ({ one, many }) => ({
  text: many(TextTable),
}));
////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////
// Text Table
////////////////////////////////////////////////////////////////////////////////
export const TextTable = pgTable(
  "text",
  {
    id: text("id").primaryKey(),
    text: text("text").notNull(),
    embedding: vector("embedding", {
      dimensions: EMBEDDING_DIMENSIONS,
    }).notNull(),
    documentId: text("doc_id")
      .notNull()
      .references(() => DocumentsTable.id, { onDelete: "cascade" }),
    metadata: json("metadata")
      .$type<Record<string, unknown>>()
      .notNull()
      .default({}),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    //CREATE INDEX pgroonga_content_index ON memos USING pgroonga (content);
    index("ml_text_search_index").using("pgroonga", table.text),
    // index("text_search_index").using(
    //   "gin",
    //   sql`to_tsvector('english', ${table.text})`,
    // ),
    index("text_embeddingIndex").using(
      "hnsw",
      table.embedding.op("vector_cosine_ops"),
    ),
  ],
);

export const TextRelations = relations(TextTable, ({ one }) => ({
  url: one(DocumentsTable, {
    fields: [TextTable.documentId],
    references: [DocumentsTable.id],
  }),
}));
////////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////////
// TextAnnotation Table
////////////////////////////////////////////////////////////////////////////////
export const TextAnnotationTable = pgTable(
  "text_annotations",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    text: text("text").notNull(),
    textId: text("text_id")
      .notNull()
      .references(() => TextTable.id, { onDelete: "cascade" }),
    documentId: text("doc_id")
      .notNull()
      .references(() => DocumentsTable.id, { onDelete: "cascade" }),
    start: integer("start").notNull(),
    end: integer("end").notNull(),
    type: text("type").notNull(),
    value: text("value").notNull(),
    embedding: vector("embedding", {
      dimensions: EMBEDDING_DIMENSIONS,
    }),
    metadata: json("metadata")
      .$type<Record<string, unknown>>()
      .notNull()
      .default({}),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("text_annotation_start_idx").on(table.start),
    index("text_annotation_end_idx").on(table.end),
    index("text_annotation_type_idx").on(table.type),
    index("text_annotation_value_idx").on(table.value),
    // index("text_annotation_text_search_index").using(
    //   "gin",
    //   sql`to_tsvector('english', ${table.text})`,
    // ),
    index("ml_text_annotation_search_index").using("pgroonga", table.text),
    index("embeddingIndex").using(
      "hnsw",
      table.embedding.op("vector_cosine_ops"),
    ),
  ],
);

export const TextAnnotationRelations = relations(
  TextAnnotationTable,
  ({ one }) => ({
    document: one(DocumentsTable, {
      fields: [TextAnnotationTable.documentId],
      references: [DocumentsTable.id],
    }),
    text: one(TextTable, {
      fields: [TextAnnotationTable.textId],
      references: [TextTable.id],
    }),
  }),
);
////////////////////////////////////////////////////////////////////////////////

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

export const JobsTable = pgTable("jobs", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  status: jobStatusEnum("status").notNull().default("waiting"),
  total: integer("total").notNull().default(0),
  completed: integer("completed").notNull().default(0),
  failed: integer("failed").notNull().default(0),
  metadata: json("metadata").notNull().default({}),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at")
    .defaultNow()
    .$onUpdate(() => new Date()),
});
