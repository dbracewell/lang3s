import {
  doublePrecision,
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
