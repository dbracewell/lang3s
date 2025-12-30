import {
  customType,
  integer,
  pgMaterializedView,
  pgView,
  text,
} from "drizzle-orm/pg-core";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { TopicsTable } from "@/lib/db/schemas/topics";
import { countDistinct, eq, gt, gte, sql } from "drizzle-orm";
import { cosineSimilarity } from "@/lib/db/helpers/vector";
import { MIN_TOPIC_SIMILARITY } from "@/features/common/constants";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { upper } from "@/lib/db/helpers/string";
import { coalesce, jsonValue } from "@/lib/db/funcs";
import { randomAlphaUnderscore } from "@/lib/utils/random";

export const TopicSentences = pgMaterializedView("topic_sentences").as((qb) =>
  qb
    .select({
      topicId: sql<string>`${TopicsTable.id}`.as("topic_id"),
      documentId: TextAnnotationTable.documentId,
      textId: TextAnnotationTable.textId,
      sentenceAid: TextAnnotationTable.sentenceAid,
      similarity: cosineSimilarity(
        TopicsTable.embedding,
        TextAnnotationTable.embedding,
      ).as("similarity"),
    })
    .from(TopicsTable)
    .innerJoin(TextAnnotationTable, eq(TextAnnotationTable.type, "sentence"))
    .where(
      gte(
        cosineSimilarity(TopicsTable.embedding, TextAnnotationTable.embedding),
        MIN_TOPIC_SIMILARITY,
      ),
    ),
);

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
        content: TextAnnotationTable.content,
        start: TextAnnotationTable.start,
        end: TextAnnotationTable.end,
        sentenceAid: TextAnnotationTable.sentenceAid,
        documentId: TextAnnotationTable.documentId,
        metadata: TextAnnotationTable.metadata,
        type: TextAnnotationTable.type,
        value: TextAnnotationTable.value,
        a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
        a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
        time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
          "TIME",
        ),
        location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
          "LOCATION",
        ),
        textId: TextAnnotationTable.textId,
        normalized: upper(
          coalesce(
            jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
            jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
            TextAnnotationTable.content,
          ),
        ).as("normalized"),
        path: sub.path,
        name: sub.name,
      })
      .from(TextAnnotationTable)
      .innerJoin(sub, eq(TextAnnotationTable.mapping, sub.mapping));
  },
);

// export const AnnotationCounts = pgMaterializedView("annotation_counts").as(
//   (qb) =>
//     qb
//       .select({
//         content: sql<string>`${AnnotationWithOntologyView.normalized}`.as(
//           "content",
//         ),
//         type: AnnotationWithOntologyView.path,
//         documentCount: countDistinct(AnnotationWithOntologyView.documentId).as(
//           "document_count",
//         ),
//         sentenceCount: countDistinct(AnnotationWithOntologyView.sentenceAid).as(
//           "sentence_count",
//         ),
//         mentionCount: count().as("mention_count"),
//       })
//       .from(AnnotationWithOntologyView)
//       .groupBy((t) => [t.content, t.type]),
// );

const ltree = customType<{ data: string }>({
  dataType() {
    return "ltree";
  },
});

export const AnnotationCounts = pgMaterializedView("annotation_counts", {
  content: text("content").notNull(),
  type: ltree("path").notNull(),
  documentCount: integer("document_count").notNull(),
  sentenceCount: integer("sentence_count").notNull(),
  mentionCount: integer("mention_count").notNull(),
}).existing();

export const AnnotationCoOccurrence = pgMaterializedView(
  "annotation_co_occurrence",
  {
    source: text("source").notNull(),
    sourceType: ltree("source_type").notNull(),
    target: text("target").notNull(),
    targetType: ltree("target_type").notNull(),
    documentCount: integer("document_count").notNull(),
    sentenceCount: integer("sentence_count").notNull(),
  },
).existing();
