import { sql } from "drizzle-orm";
import {
  index,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  uuid,
  vector,
} from "drizzle-orm/pg-core";
export const EMBEDDING_DIMENSIONS = 768;

////////////////////////////////////////////////////////////////////////////////
// Documents Table
////////////////////////////////////////////////////////////////////////////////
export const DocumentsTable = pgTable(
  "documents",
  {
    id: text("id").primaryKey(),
    title: text("title").notNull(),
    metadata: jsonb("metadata")
      .$type<Record<string, unknown>>()
      .notNull()
      .default({}),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("document_metadata_gin_idx").using(
      "gin",
      sql`${table.metadata} jsonb_path_ops`,
    ),
  ],
);

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
    metadata: jsonb("metadata")
      .$type<Record<string, unknown>>()
      .notNull()
      .default({}),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("ml_text_search_index").using("pgroonga", table.text),
    index("text_embeddingIndex").using(
      "hnsw",
      table.embedding.op("vector_cosine_ops"),
    ),
    index("text_metadata_gin_idx").using(
      "gin",
      sql`${table.metadata} jsonb_path_ops`,
    ),
  ],
);

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
    sentenceId: integer("sentence_id").notNull(),
    type: text("type").notNull(),
    value: text("value").notNull(),
    mapping: text("mapping")
      .generatedAlwaysAs(sql`type || ':' || value`)
      .notNull(),
    embedding: vector("embedding", {
      dimensions: EMBEDDING_DIMENSIONS,
    }),
    metadata: jsonb("metadata")
      .$type<Record<string, unknown>>()
      .notNull()
      .default({}),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("text_annotation_type_idx").on(table.type),
    index("text_annotation_value_idx").on(table.value),
    index("text_annotation_sentence_id_idx").on(table.sentenceId),
    index("text_annotation_mapping_index").on(table.mapping),
    index("ml_text_annotation_search_index").using("pgroonga", table.text),
    index("embeddingIndex").using(
      "hnsw",
      table.embedding.op("vector_cosine_ops"),
    ),
    index("text_annotation_metadata_gin_idx").using(
      "gin",
      sql`${table.metadata} jsonb_path_ops`,
    ),
  ],
);

////////////////////////////////////////////////////////////////////////////////
