import { sql } from "drizzle-orm";
import { halfvec, index, integer, jsonb, pgTable, text, timestamp, uuid } from "drizzle-orm/pg-core";

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
    index("text_document_id_index").on(table.documentId),
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
    normalized: text("normalized_text").notNull(),
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
    a0Text: text("a0_text")
      .array()
      .generatedAlwaysAs(
        sql`ARRAY(SELECT jsonb_array_elements_text(metadata->'A0_TEXT'))`,
      ),
    a1Text: text("a1_text")
      .array()
      .generatedAlwaysAs(
        sql`ARRAY(SELECT jsonb_array_elements_text(metadata->'A0_TEXT'))`,
      ),
    timeText: text("time_text").generatedAlwaysAs(
      sql`(metadata->>'TIME_TEXT')`,
    ),
    locText: text("loc_text").generatedAlwaysAs(sql`(metadata->>'LOC_TEXT')`),
    a0Id: text("a0_id")
      .array()
      .generatedAlwaysAs(
        sql`ARRAY(SELECT jsonb_array_elements_text(metadata->'A0'))`,
      ),
    a1Id: text("a1_id")
      .array()
      .generatedAlwaysAs(
        sql`ARRAY(SELECT jsonb_array_elements_text(metadata->'A1'))`,
      ),
    timeId: text("time_id").generatedAlwaysAs(sql`(metadata->>'TIME')`),
    locId: text("loc_id").generatedAlwaysAs(sql`(metadata->>'LOC')`),
  },
  (table) => [
    index("text_annotation_sentence_aid_index").on(table.sentenceAid),
    index("text_annotation_document_id_index").on(table.documentId),
    index("text_annotation_mapping_index").on(table.mapping),
    index("text_annotation_normalized_index").on(table.normalized),
    index("ml_text_annotation_search_index").using("pgroonga", table.content),
    index("text_annotation_a0_text_index").using("GIN", table.a0Text),
    index("text_annotation_a1_text_index").using("GIN", table.a1Text),
    index("text_annotation_loc_text_index").on(table.locText),
    index("text_annotation_time_text_index").on(table.timeText),
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

////////////////////////////////////////////////////////////////////////////////
// Keywords Table
////////////////////////////////////////////////////////////////////////////////
export const KeywordsTable = pgTable(
  "keywords",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    category: text("category"),
    keyword: text("keyword").notNull(),
    documentId: text("document_id")
      .references(() => DocumentsTable.id, { onDelete: "cascade" })
      .notNull(),
    textId: text("text_id")
      .references(() => TextTable.id, { onDelete: "cascade" })
      .notNull(),
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
    }).notNull(),
  },
  (table) => [
    index("keywords_embedding_index").using(
      "hnsw",
      table.embedding.op("halfvec_cosine_ops"),
    ),
    index("keywords_category_idx").on(table.category),
    index("keywords_document_id").on(table.documentId),
    index("keywords_text_id").on(table.textId),
  ],
);

export const ClaimsTable = pgTable(
  "claims",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    documentId: text("doc_id")
      .notNull()
      .references(() => DocumentsTable.id, { onDelete: "cascade" }),
    claim: text("claim").notNull(),
    source: text("source"),
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
    }).notNull(),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("claims_content_fts_index").using("pgroonga", table.claim),
    index("claims_doc_id_idx").on(table.documentId),
    index("claims_embedding_index").using(
      "hnsw",
      table.embedding.op("halfvec_cosine_ops"),
    ),
  ],
);
