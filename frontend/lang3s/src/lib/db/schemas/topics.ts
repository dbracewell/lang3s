import { SEMANTIC_EMBEDDING_DIMENSION } from "@/lib/db/schema";
import {
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
    embedding: halfvec("embedding", {
      dimensions: SEMANTIC_EMBEDDING_DIMENSION,
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
      table.embedding.op("halfvec_cosine_ops"),
    ),
  ],
);
