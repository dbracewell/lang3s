import { db } from "@/db";
import {
  EMBEDDING_DIMENSIONS,
  TextAnnotationTable,
  TopicsTable,
} from "@/db/schema";
import { logAndRethrow } from "@/lib/try-catch";
import {
  getAnnotationsInSentence,
  notOverlaps,
} from "@/features/documents/server/subqueries";
import { createTRPCRouter, protectedProcedure } from "@/trpc/init";
import {
  and,
  asc,
  count,
  countDistinct,
  desc,
  eq,
  gt,
  gte,
  hammingDistance,
  inArray,
  ne,
  sql,
} from "drizzle-orm";
import z from "zod";

export const AnalyticsRouter = createTRPCRouter({
  getAnnotationTypes: protectedProcedure.query(async () => {
    return (
      await db
        .selectDistinct({
          type: TextAnnotationTable.type,
        })
        .from(TextAnnotationTable)
        .where(
          and(
            ne(TextAnnotationTable.type, "sentence"),
            ne(TextAnnotationTable.type, "token"),
          ),
        )
        .orderBy((t) => [asc(t.type)])
    ).map((t) => t.type);
  }),
  getUniqueTags: protectedProcedure
    .input(
      z.object({
        annotationType: z.string(),
      }),
    )
    .query(async ({ input }) => {
      return (
        await logAndRethrow(
          db
            .selectDistinct({ value: TextAnnotationTable.value })
            .from(TextAnnotationTable)
            .where(eq(TextAnnotationTable.type, input.annotationType))
            .orderBy((t) => asc(t.value)),
        )
      ).map((v) => v.value);
    }),

  getAnnotationCounts: protectedProcedure
    .input(
      z.object({
        annotationType: z.string(),
        values: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(
        db
          .select({
            text: sql<string>`upper(${TextAnnotationTable.text})`.as("text"),
            value: TextAnnotationTable.value,
            count: count().as("count"),
            docCount: countDistinct(TextAnnotationTable.documentId).as(
              "doc_count",
            ),
            mentionsPerDocument:
              sql<number>`count(0)::float/count(distinct ${TextAnnotationTable.documentId})`.as(
                "mentions_per_doc",
              ),
          })
          .from(TextAnnotationTable)
          .where(
            and(
              eq(TextAnnotationTable.type, input.annotationType),
              inArray(TextAnnotationTable.value, input.values),
            ),
          )
          .groupBy((t) => [t.text, t.value])
          .orderBy((t) => desc(t.count))
          .having((t) => gt(t.count, 10)),
      );
    }),

  getCoocurrence: protectedProcedure
    .input(
      z.object({
        leftType: z.string(),
        leftValue: z.string(),
        leftText: z.string().optional(),
        rightType: z.string(),
        rightValues: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      const leftNormedText = input.leftText
        ? input.leftText.toUpperCase()
        : undefined;

      const q1 = getAnnotationsInSentence({
        annotationType: input.leftType,
        textConversion: "upper",
        tags: [input.leftValue],
        text: leftNormedText,
      }).as("q1");
      const q2 = getAnnotationsInSentence({
        annotationType: input.rightType,
        textConversion: "upper",
        tags: input.rightValues,
      }).as("q2");

      return await logAndRethrow(
        db
          .select({
            e1: q1.text,
            e1Type: q1.value,
            e2: q2.text,
            e2Type: q2.value,
            count: count(),
          })
          .from(q1)
          .innerJoin(
            q2,
            and(
              eq(q2.sentenceId, q1.sentenceId),
              ne(q1.annotationId, q2.annotationId),
              ne(q1.text, q2.text),
              input.leftType !== input.rightType
                ? notOverlaps(q1, q2)
                : undefined,
            ),
          )
          .groupBy((t) => [t.e1, t.e2, t.e1Type, t.e2Type])
          .orderBy((t) => [desc(t.count)])
          .limit(100),
      );
    }),

  getTopics: protectedProcedure.query(async () => {
    const s1 = db
      .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
      .from(TopicsTable)
      .as("t1");
    const s2 = db
      .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
      .from(TopicsTable)
      .as("t2");

    const similarity = sql<number>`1 - (${hammingDistance(
      s1.embedding,
      s2.embedding as any,
    )}) / ${EMBEDDING_DIMENSIONS}`;

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
        .where((t) => gte(t.similarity, 0.75)),
    ]);
    return {
      points,
      similarities: sims,
    };
  }),
});
