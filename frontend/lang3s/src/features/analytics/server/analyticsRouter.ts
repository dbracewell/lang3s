import { db } from "@/lib/db";
import { TextAnnotationTable } from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import {
  getAnnotationsInSentence,
  notOverlaps,
} from "@/features/documents/server/subqueries";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import {
  and,
  asc,
  count,
  countDistinct,
  desc,
  eq,
  gt,
  ilike,
  inArray,
  ne,
  or,
  sql,
} from "drizzle-orm";
import z from "zod";
import {
  coalesce,
  generateNextPage,
  jsonbAgg,
  jsonbBuildObject,
  jsonValue,
  lower,
  upper,
  withPagination,
} from "@/lib/db/funcs";
import { PAGE_LIMIT } from "@/features/common/constants";

export const AnalyticsRouter = createTRPCRouter({
  getAnnotationTypes: protectedProcedure.query(async () => {
    return (
      await logAndRethrow(() =>
        db
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
          .orderBy((t) => [asc(t.type)]),
      )
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
        await logAndRethrow(() =>
          db
            .selectDistinct({ value: TextAnnotationTable.value })
            .from(TextAnnotationTable)
            .where(eq(TextAnnotationTable.type, input.annotationType))
            .orderBy((t) => asc(t.value)),
        )
      ).map((v) => v.value.toUpperCase());
    }),

  getAnnotationCounts: protectedProcedure
    .input(
      z.object({
        annotationType: z.string(),
        values: z.array(z.string()),
        page: z.number().nullish(),
        sortBy: z.string().nullish(),
        filter: z.string().nullish(),
      }),
    )
    .query(async ({ input }) => {
      const page = Math.max(1, input.page ?? 1);
      const filter = input.filter;
      const rawSortBy = input.sortBy ?? "mentions";
      let finalSortBy = rawSortBy.toLowerCase();
      if (!["mentions", "docs", "mentionsperdoc"].includes(finalSortBy)) {
        finalSortBy = "mentions";
      }

      const annotations = db
        .select({
          text: sql<string>`upper(COALESCE(${TextAnnotationTable.metadata}->>'coref_text', ${TextAnnotationTable.content}))`.as(
            "text",
          ),
          documentId: TextAnnotationTable.documentId,
          value: TextAnnotationTable.value,
        })
        .from(TextAnnotationTable)
        .where(
          and(
            eq(TextAnnotationTable.type, input.annotationType),
            inArray(TextAnnotationTable.value, input.values),
          ),
        )
        .as("annotations");

      const subQuery = db
        .select({
          text: annotations.text,
          value: annotations.value,
          count: count().as("count"),
          docCount: countDistinct(annotations.documentId).as("doc_count"),
          mentionsPerDocument:
            sql<number>`count(0)::float/count(distinct ${annotations.documentId})`.as(
              "mentions_per_doc",
            ),
        })
        .from(annotations)
        .where(
          !!filter
            ? ilike(sql`upper(${annotations.text})`, `${filter.toUpperCase()}%`)
            : undefined,
        )
        .groupBy((t) => [t.text, t.value])
        .orderBy((t) =>
          finalSortBy === "mentions"
            ? desc(t.count)
            : finalSortBy === "docs"
              ? desc(t.docCount)
              : desc(t.mentionsPerDocument),
        )
        .having((t) => gt(t.docCount, 5))
        .as("annotation_search");

      const [total, results] = await logAndRethrow(() =>
        Promise.all([
          db.select({ count: count() }).from(subQuery),
          withPagination(db.select().from(subQuery), {
            page,
          }),
        ]),
      );

      const { hasNextPage, finalResults } = generateNextPage(results);

      return {
        total: total[0].count,
        results: finalResults,
        totalPages: Math.ceil(total[0].count / PAGE_LIMIT),
        nextPage: hasNextPage ? page + 1 : undefined,
        prevPage: page > 1 ? page - 1 : undefined,
      };
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

      return await db
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
            eq(q2.sentenceAId, q1.sentenceAId),
            ne(q1.annotationId, q2.annotationId),
            ne(q1.text, q2.text),
            input.leftType !== input.rightType
              ? notOverlaps(q1, q2)
              : undefined,
          ),
        )
        .groupBy((t) => [t.e1, t.e2, t.e1Type, t.e2Type])
        .orderBy((t) => [desc(t.count)])
        .limit(100);
    }),

  getEventsForEntity: protectedProcedure
    .input(
      z.object({
        entity: z.string(),
        value: z.string(),
      }),
    )
    .query(async ({ input }) => {
      const { entity, value } = input;

      const sentences = db
        .select()
        .from(TextAnnotationTable)
        .where(eq(TextAnnotationTable.type, "sentence"))
        .as("sentences");

      const entities = db
        .selectDistinct({
          sentenceAid: TextAnnotationTable.sentenceAid,
          sentence: sentences.content,
        })
        .from(TextAnnotationTable)
        .innerJoin(sentences, eq(sentences.id, TextAnnotationTable.sentenceAid))
        .where(
          and(
            eq(TextAnnotationTable.type, "entity"),
            eq(TextAnnotationTable.value, value),
            eq(
              lower(
                coalesce(
                  jsonValue<string>(
                    TextAnnotationTable.metadata,
                    "coref_text",
                    "text",
                  ),
                  TextAnnotationTable.content,
                ),
              ),
              entity.toLowerCase(),
            ),
          ),
        )
        .as("entities");

      const events = db
        .select({
          text: upper(
            coalesce(
              jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
              TextAnnotationTable.content,
            ),
          ).as("trigger"),
          sentence: entities.sentence,
          value: TextAnnotationTable.value,
          A0: jsonValue(TextAnnotationTable.metadata, "A0_TEXT", "json").as(
            "A0",
          ),
          A1: jsonValue(TextAnnotationTable.metadata, "A1_TEXT", "json").as(
            "A1",
          ),
          TIME: jsonValue<string>(TextAnnotationTable.metadata, "TIME_TEXT").as(
            "TIME",
          ),
          LOC: jsonValue<string>(TextAnnotationTable.metadata, "LOC_TEXT").as(
            "LOC",
          ),
          isA0: sql<boolean>`exists (
      select 1
      from jsonb_array_elements_text(metadata->'A0_TEXT') as elem
      where lower(elem) = ${entity.toLowerCase()}
  )`.as("isA0"),
          isA1: sql<boolean>`exists (
      select 1
      from jsonb_array_elements_text(metadata->'A1_TEXT') as elem
      where lower(elem) = ${entity.toLowerCase()}
  )`.as("isA1"),
          isLoc:
            sql<boolean>`UPPER((metadata->>'LOC_TEXT')::text) = ${entity.toUpperCase()}`.as(
              "isLoc",
            ),
        })
        .from(TextAnnotationTable)
        .innerJoin(
          entities,
          eq(entities.sentenceAid, TextAnnotationTable.sentenceAid),
        )
        .where(
          and(
            eq(TextAnnotationTable.type, "event"),
            or(
              sql`exists (
      select 1
      from jsonb_array_elements_text(metadata->'A0_TEXT') as elem
      where lower(elem) = ${entity.toLowerCase()}
  )`,
              sql`exists (
      select 1
      from jsonb_array_elements_text(metadata->'A1_TEXT') as elem
      where lower(elem) = ${entity.toLowerCase()}
  )`,
              sql`UPPER((metadata->>'LOC_TEXT')::text) = ${entity.toUpperCase()}`,
            ),
          ),
        )
        .as("events");

      return await logAndRethrow(() =>
        db
          .select({
            value: events.value,
            count: count(),
            events: jsonbAgg(
              jsonbBuildObject({
                text: events.text,
                sentence: events.sentence,
                A0: events.A0,
                A1: events.A1,
                TIME: events.TIME,
                LOC: events.LOC,
                isA0: events.isA0,
                isA1: events.isA1,
                isLoc: events.isLoc,
              }),
            ),
          })
          .from(events)
          .groupBy((t) => [t.value])
          .orderBy(events.value),
      );
    }),
});
