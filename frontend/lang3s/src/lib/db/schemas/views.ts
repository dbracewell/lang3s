import {
  doublePrecision,
  integer,
  pgMaterializedView,
  pgView,
  text,
} from "drizzle-orm/pg-core";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { countDistinct, eq, getTableColumns, gt, sql } from "drizzle-orm";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { ltree } from "@/lib/db/custom_types";

export const TopicSentences = pgMaterializedView("topic_sentences", {
  topicId: text("topic_id").notNull(),
  documentId: text("doc_id").notNull(),
  textId: text("text_id").notNull(),
  sentenceAid: text("sentence_aid").notNull(),
  sentence: text("sentence").notNull(),
  similarity: doublePrecision("similarity").notNull(),
}).existing();

export const TopicDocuments = pgMaterializedView("topic_documents").as((qb) =>
  qb
    .select({
      topicId: TopicSentences.topicId,
      documentId: TopicSentences.documentId,
      textId: TopicSentences.textId,
      similarity: sql<number>`AVG(${TopicSentences.similarity})`.as(
        "similarity",
      ),
      score: countDistinct(TopicSentences.sentenceAid).as("score"),
    })
    .from(TopicSentences)
    .groupBy((t) => [t.documentId, t.textId, t.topicId])
    .having((t) => gt(t.score, 2)),
);

export const AnnotationWithOntologyView = pgView("annotation_with_ontology").as(
  (qb) => {
    const sub = qb
      .select({
        path: OntologyTable.path,
        name: OntologyTable.name,
        color: OntologyTable.color,
        properties: OntologyTable.properties,
        mapping: AnnotationToOntology.annotation,
      })
      .from(OntologyTable)
      .innerJoin(
        AnnotationToOntology,
        eq(OntologyTable.id, AnnotationToOntology.ontologyId),
      )
      .as(randomAlphaUnderscore());

    return qb
      .select({
        ...getTableColumns(TextAnnotationTable),
        path: sub.path,
        name: sub.name,
        color: sub.color,
        properties: sub.properties,
        normalizedAndPath:
          sql<string>`CONCAT(${TextAnnotationTable.normalized},'-',${sub.path})`.as(
            "normalized_path",
          ),
      })
      .from(TextAnnotationTable)
      .innerJoin(sub, eq(TextAnnotationTable.mapping, sub.mapping));
  },
);

export const AnnotationCounts = pgMaterializedView("annotation_counts", {
  content: text("normalized_text").notNull(),
  type: ltree("path").notNull(),
  documentCount: integer("document_count").notNull(),
  sentenceCount: integer("sentence_count").notNull(),
  mentionCount: integer("mention_count").notNull(),
}).existing();

export const AnnotationCoOccurrence = pgMaterializedView(
  "annotation_co_occurrence",
  {
    sourceId: text("source_id").notNull(),
    source: text("source").notNull(),
    sourceType: text("source_type").notNull(),
    sourceNorm: text("source_norm").notNull(),
    sourceSentenceCount: integer("source_sentence_count").notNull(),
    sourceDocumentCount: integer("source_document_count").notNull(),
    sourceMentionCount: integer("source_mention_count").notNull(),
    sentenceAid: text("sentence_aid").notNull(),
    documentId: text("doc_id").notNull(),
    targetId: text("target_id"),
    target: text("target"),
    targetType: text("target_type"),
    targetNorm: text("target_norm"),
    targetSentenceCount: integer("target_sentence_count"),
    targetDocumentCount: integer("target_document_count"),
    targetMentionCount: integer("target_mention_count"),
  },
).existing();
