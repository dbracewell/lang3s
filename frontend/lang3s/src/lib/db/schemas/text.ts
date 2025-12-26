import { sql } from "drizzle-orm";
import { halfvec, index, integer, jsonb, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const TOKEN_EMBEDDING_DIMENSION = 768;
export const SEMANTIC_EMBEDDING_DIMENSION = 384;
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
    content: text("text").notNull(),
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
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
    index("ml_text_search_index").using("pgroonga", table.content),
    index("text_embedding_index").using(
      "hnsw",
      table.embedding.op("halfvec_cosine_ops"),
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
    id: text("id").primaryKey(),
    content: text("text").notNull(),
    cleaned: text("clean_text").notNull(),
    textId: text("text_id")
      .notNull()
      .references(() => TextTable.id, { onDelete: "cascade" }),
    documentId: text("doc_id")
      .notNull()
      .references(() => DocumentsTable.id, { onDelete: "cascade" }),
    start: integer("start").notNull(),
    end: integer("end").notNull(),
    sentenceId: integer("sentence_id").notNull(),
    sentenceAid: text("sentence_aid").notNull(),
    type: text("type").notNull(),
    value: text("value").notNull(),
    source: text("source").notNull(),
    mapping: text("mapping"),
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
    }).notNull(),
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
    index("text_annotation_sentence_aid").on(table.sentenceAid),
    index("text_annotation_sentence_id_idx").on(table.sentenceId),
    index("text_annotation_mapping_index").on(table.mapping),
    index("ml_text_annotation_search_index").using("pgroonga", table.content),
    index("text_annotation_embedding_index").using(
      "hnsw",
      table.embedding.op("halfvec_cosine_ops"),
    ),
    index("text_annotation_metadata_gin_idx").using(
      "gin",
      sql`${table.metadata} jsonb_path_ops`,
    ),
  ],
);

////////////////////////////////////////////////////////////////////////////////
