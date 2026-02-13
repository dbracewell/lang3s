import { halfvec, index, pgTable, text, timestamp, uuid } from "drizzle-orm/pg-core";
import { SEMANTIC_EMBEDDING_DIMENSION } from "@/lib/db/schemas/text";

export const ClaimsTable = pgTable(
  "claims",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    sentenceAid: text("sentence_aid").notNull(),
    documentId: text("doc_id").notNull(),
    content: text("text").notNull(),
    source: text("source"),
    entities: text("entities").array().default([]).notNull(),
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
    }).notNull(),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("claims_content_fts_index").using("pgroonga", table.content),
    index("claims_sentence_aid_idx").on(table.sentenceAid),
    index("claims_embedding_index").using(
      "hnsw",
      table.embedding.op("halfvec_cosine_ops"),
    ),
  ],
);
