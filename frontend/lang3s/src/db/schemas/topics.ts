import { EMBEDDING_DIMENSIONS } from "@/db/schema";
import {
  bit,
  boolean,
  halfvec,
  index,
  integer,
  pgTable,
  text,
  timestamp,
} from "drizzle-orm/pg-core";

export const TopicsTable = pgTable(
  "topics",
  {
    id: text("id").primaryKey(),
    name: text("name").notNull(),
    fixed: boolean("is_fixed").notNull().default(false),
    fullEmbedding: halfvec("full_embedding", {
      dimensions: EMBEDDING_DIMENSIONS,
    }).notNull(),
    embedding: bit("embedding", {
      dimensions: EMBEDDING_DIMENSIONS,
    }).notNull(),
    support: integer("support").notNull().default(0),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [
    index("topics_embeddingIndex").using(
      "hnsw",
      table.embedding.op("bit_hamming_ops"),
    ),
  ],
);
