import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { db } from "@/lib/db";
import { TopicsTable } from "@/lib/db/schemas/topics";
import {
  and,
  count,
  countDistinct,
  desc,
  eq,
  gt,
  gte,
  not,
  sql,
} from "drizzle-orm";
import z from "zod";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { cosineSimilarity } from "@/lib/db/funcs";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { TRPCError } from "@trpc/server";
import { MIN_TOPIC_SIMILARITY } from "@/features/common/constants";

export const TopicsRouter = createTRPCRouter({
  getTopics: protectedProcedure.query(async () => {
    const s1 = db
      .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
      .from(TopicsTable)
      .as("t1");
    const s2 = db
      .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
      .from(TopicsTable)
      .as("t2");

    const similarity = sql<number>`1 - (${s1.embedding}::halfvec <=> ${s2.embedding}::halfvec)::float`;

    const [points, sims] = await Promise.all([
      db
        .select({
          id: TopicsTable.id,
          name: TopicsTable.name,
          support: TopicsTable.support,
        })
        .from(TopicsTable),
      db
        .select({
          id1: s1.id,
          id2: s2.id,
          similarity: similarity,
        })
        .from(s1)
        .innerJoin(s2, gt(s1.id, s2.id))
        .where((t) => gte(t.similarity, 0.7)),
    ]);
    return {
      points,
      similarities: sims,
    };
  }),

  getTopic: protectedProcedure
    .input(
      z.object({
        id: z.string(),
      }),
    )
    .query(async ({ input }) => {
      const { id } = input;

      const [topic] = await logAndRethrow(() =>
        db
          .select({ embedding: TopicsTable.embedding, name: TopicsTable.name })
          .from(TopicsTable)
          .where(eq(TopicsTable.id, id)),
      );

      if (topic == null) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      const sentences = db
        .select({
          documentId: TextAnnotationTable.documentId,
          content: TextAnnotationTable.content,
          sentenceId: TextAnnotationTable.sentenceId,
          similarity: cosineSimilarity(
            TextAnnotationTable.embedding,
            topic.embedding,
          ).as("similarity"),
        })
        .from(TextAnnotationTable)
        .where((t) =>
          and(
            gte(t.similarity, MIN_TOPIC_SIMILARITY),
            eq(TextAnnotationTable.type, "sentence"),
            not(
              sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
            ),
          ),
        )
        .as("sentence");

      const sentenceSearch = db
        .select({
          documentId: sentences.documentId,
          sentenceId: sentences.sentenceId,
          content: sentences.content,
          similarity: sentences.similarity,
        })
        .from(sentences)
        .orderBy((t) => desc(t.similarity))
        .limit(20);

      const entities = db
        .select({
          entity:
            sql<string>`upper(COALESCE(${TextAnnotationTable.metadata}->>'coref_text', ${TextAnnotationTable.content}))`.as(
              "entity",
            ),
          type: TextAnnotationTable.value,
          count: count(),
        })
        .from(sentences)
        .innerJoin(
          TextAnnotationTable,
          and(
            eq(sentences.documentId, TextAnnotationTable.documentId),
            eq(sentences.sentenceId, TextAnnotationTable.sentenceId),
          ),
        )
        .where(eq(TextAnnotationTable.type, "entity"))
        .groupBy((t) => [t.entity, t.type])
        .having((t) => gt(t.count, 9))
        .orderBy((t) => desc(t.count));

      const totalCount = db
        .select({ count: count(), docs: countDistinct(sentences.documentId) })
        .from(sentences);

      const [[totalData], sentencesData, entitiesData] = await logAndRethrow(
        () => Promise.all([totalCount, sentenceSearch, entities]),
      );

      return {
        name: topic.name,
        sentenceCount: totalData.count,
        documentCount: totalData.docs,
        sentences: sentencesData,
        entities: entitiesData,
      };
    }),
});
