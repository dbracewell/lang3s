import { SEMANTIC_EMBEDDING_DIMENSION } from "@/lib/db/schema";
import {
  boolean,
  halfvec,
  index,
  integer,
  pgTable,
  serial,
  text,
  timestamp,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

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
    documents: integer("doc_support").notNull().default(0),
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

export const TopicTree = pgTable(
  "topics_tree",
  {
    id: text("id").primaryKey(),
    name: text("name").notNull(),
    parent: text("parent_id"),
    isLeaf: boolean("is_leaf").default(false),
    level: integer("level"),
    splitK: integer("split_k"),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at")
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (table) => [index("topic_tree_parent_id").on(table.parent)],
);

export const TopicTree2Topic = pgTable("topic_tree_topic_map", {
  id: serial("id").primaryKey(),
  nodeId: text("node_id").references(() => TopicTree.id, {
    onDelete: "cascade",
  }),
  topicId: text("topic_id").references(() => TopicsTable.id, {
    onDelete: "cascade",
  }),
});

export const TopicRelations = relations(TopicsTable, ({ one }) => ({
  topicTreeNode: one(TopicTree2Topic, {
    fields: [TopicsTable.id],
    references: [TopicTree2Topic.topicId],
  }),
}));

export const TopicTreeRelations = relations(TopicTree, ({ one }) => ({
  topicTreeNode: one(TopicTree2Topic, {
    fields: [TopicTree.id],
    references: [TopicTree2Topic.nodeId],
  }),
}));
