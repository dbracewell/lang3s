import { pgMaterializedView } from "drizzle-orm/pg-core";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { TopicsTable } from "@/lib/db/schemas/topics";
import { countDistinct, eq, gt, gte, sql } from "drizzle-orm";
import { cosineSimilarity } from "@/lib/db/helpers/vector";
import { MIN_TOPIC_SIMILARITY } from "@/features/common/constants";

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
