import {
  doublePrecision,
  integer,
  json,
  pgMaterializedView,
  pgView,
  text,
} from "drizzle-orm/pg-core";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { eq, getTableColumns, sql } from "drizzle-orm";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { randomAlphaUnderscore } from "@/lib/utils/random";

export const TopicSentences = pgMaterializedView("topic_sentences", {
  topicId: text("topic_id").notNull(),
  documentId: text("doc_id").notNull(),
  textId: text("text_id").notNull(),
  sentenceAid: text("sentence_aid").notNull(),
  sentence: text("sentence").notNull(),
  similarity: doublePrecision("similarity").notNull(),
}).existing();

export const DocumentTopicConcepts = pgView("document_topic_concepts", {
  topicId: text("topic_id").notNull(),
  topic: text("topic").notNull(),
  topicCount: integer("topic_count").notNull(),
  concept: text("concept").notNull(),
  conceptCount: integer("concept_count").notNull(),
  overlap: integer("overlap_count").notNull(),
  instances: json().$type<Record<string, number>>().notNull(),
}).existing();

export const ConceptCoOccurrence = pgMaterializedView("concept_co_occurrence", {
  source: text("source").notNull(),
  target: text("target").notNull(),
  sourceCount: integer("source_count").notNull(),
  targetCount: integer("target_count").notNull(),
  documentId: text("document_id").notNull(),
}).existing();

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
