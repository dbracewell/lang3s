import { db } from "@/lib/db";
import {
  AnnotationCoOccurrence,
  AnnotationCounts,
  TextAnnotationTable,
  TopicSentences,
  TopicsTable,
} from "@/lib/db/schema";
import { logAndRethrow, tryCatch } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import {
  and,
  asc,
  count,
  countDistinct,
  desc,
  eq,
  gt,
  gte,
  ilike,
  lt,
  ne,
  or,
  sql,
} from "drizzle-orm";
import z from "zod";
import {
  generateNextPage,
  jsonAgg,
  jsonBuildObject,
  withPagination,
} from "@/lib/db/funcs";
import { PAGE_LIMIT } from "@/features/common/constants";
import { Annotations } from "@/lib/db/annotations";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { TRPCError } from "@trpc/server";
import { alias } from "drizzle-orm/pg-core";
import { Point } from "@/components/charts/ForceGraph";
import { getColorName } from "@/lib/utils/colors";
import { roleHasPermissions } from "@/features/auth/permissions";
import { createRedisClient } from "@/lib/redis";

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

  getAnnotationCounts: protectedProcedure
    .input(
      z.object({
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

      const [total, results] = await logAndRethrow(() => {
        const q3 = Annotations.getAnnotationsWithOntology({
          options: { normalize: true },
          limitTo: input.values,
          ontologyFields: ["path", "color"],
          annotationFields: ["value"],
          computedColumns: (o) => ({
            value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
            count: count().as("count"),
            docCount: countDistinct(TextAnnotationTable.documentId).as(
              "doc_count",
            ),
            mentionsPerDocument:
              sql<number>`count(0)::float/count(distinct ${TextAnnotationTable.documentId})`.as(
                "mentions_per_doc",
              ),
          }),
        })
          .where((t) =>
            !!filter ? ilike(t.content, `${filter.toUpperCase()}%`) : undefined,
          )
          .groupBy((t) => [t.content, t.value, t.path, t.color])
          .orderBy((t) =>
            finalSortBy === "mentions"
              ? desc(t.count)
              : finalSortBy === "docs"
                ? desc(t.docCount)
                : desc(t.mentionsPerDocument),
          )
          .having((t) => gt(t.docCount, 5))
          .as("annotation_search");
        return Promise.all([
          db.select({ count: count() }).from(q3),
          withPagination(db.select().from(q3), {
            page,
          }),
        ]);
      });

      const { hasNextPage, finalResults } = generateNextPage(results);
      return {
        total: total[0].count,
        results: finalResults,
        totalPages: Math.ceil(total[0].count / PAGE_LIMIT),
        nextPage: hasNextPage ? page + 1 : undefined,
        prevPage: page > 1 ? page - 1 : undefined,
      };
    }),

  getAnnotationCoOccurrence: protectedProcedure
    .input(
      z.object({
        leftValue: z.string(),
        leftText: z.string().optional(),
        rightValues: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return logAndRethrow(async () => {
        const q1 = Annotations.getAnnotationsWithOntology({
          options: { normalize: true },
          limitTo: [input.leftValue],
          computedColumns: (o) => ({
            value: sql<string>`${o.path}`.as(randomAlphaUnderscore()),
          }),
          annotationFields: ["id", "start", "end", "sentenceAid"],
        })
          .where((t) =>
            input.leftText
              ? eq(t.content, input.leftText.toUpperCase())
              : undefined,
          )
          .as("q1");

        const q2 = Annotations.getAnnotationsWithOntology({
          options: { normalize: true },
          limitTo: input.rightValues,
          annotationFields: ["id", "start", "end", "sentenceAid"],
          computedColumns: (o) => ({
            value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
          }),
        }).as("q2");

        return db
          .select({
            e1: q1.content,
            e1Type: q1.value,
            e2: q2.content,
            e2Type: q2.value,
            count: count(),
          })
          .from(q1)
          .innerJoin(
            q2,
            and(
              eq(q2.sentenceAid, q1.sentenceAid),
              ne(q1.id, q2.id),
              ne(q1.content, q2.content),
              or(gt(q1.start, q2.end), lt(q1.end, q2.start)),
            ),
          )
          .groupBy((t) => [t.e1, t.e2, t.e1Type, t.e2Type])
          .orderBy((t) => [desc(t.count)])
          .limit(40);
      });
    }),

  getEventsForEntity: protectedProcedure
    .input(
      z.object({
        entity: z.string(),
        value: z.string(),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(() => {
        const { entity, value } = input;

        const entityQuery = Annotations.getAnnotationsWithOntology({
          options: { normalize: true },
          annotationFields: ["sentenceAid"],
          limitTo: [value],
        })
          .where((t) => eq(t.content, entity.toUpperCase()))
          .as(randomAlphaUnderscore());

        const sentenceQuery = Annotations.getSentences().as("sentence_query");
        const entitiesWithSentences = db
          .selectDistinct({
            sentenceAid: sentenceQuery.sentenceAid,
            sentence: sentenceQuery.content,
          })
          .from(entityQuery)
          .innerJoin(
            sentenceQuery,
            eq(entityQuery.sentenceAid, sentenceQuery.sentenceAid),
          )
          .as("entities_with_sentences");

        const eventsBaseQuery = Annotations.getAnnotationsWithOntology({
          limitTo: ["ALL.Event", "ALL.State", "ALL.Process"],
          options: { normalize: true, includeEventArgs: true },
          annotationFields: ["sentenceAid"],
          computedColumns: (o) => ({
            value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
            isA0: sql<boolean>`exists (
          select 1
          from jsonb_array_elements_text(metadata->'A0_TEXT') as elem
          where lower(elem) = ${entity.toLowerCase()})`.as("isA0"),
            isA1: sql<boolean>`exists (
          select 1
          from jsonb_array_elements_text(metadata->'A1_TEXT') as elem
          where lower(elem) = ${entity.toLowerCase()})`.as("isA1"),
            isLoc:
              sql<boolean>`UPPER((metadata->>'LOC_TEXT')::text) = ${entity.toUpperCase()}`.as(
                "isLoc",
              ),
          }),
        })
          .where((t) =>
            and(
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
          .as("events_base_query");

        const events = db
          .select({
            text: eventsBaseQuery.content,
            A0: eventsBaseQuery.a0,
            A1: eventsBaseQuery.a1,
            LOC: eventsBaseQuery.location,
            TIME: eventsBaseQuery.time,
            value: eventsBaseQuery.value,
            sentence: entitiesWithSentences.sentence,
            isA0: eventsBaseQuery.isA0,
            isA1: eventsBaseQuery.isA1,
            isLoc: eventsBaseQuery.isLoc,
          })
          .from(entitiesWithSentences)
          .innerJoin(
            eventsBaseQuery,
            eq(entitiesWithSentences.sentenceAid, eventsBaseQuery.sentenceAid),
          )
          .as("events");

        return db
          .select({
            value: events.value,
            count: count(),
            events: jsonAgg(
              jsonBuildObject(
                {
                  text: events.text,
                  sentence: events.sentence,
                  A0: events.A0,
                  A1: events.A1,
                  TIME: events.TIME,
                  LOC: events.LOC,
                  isA0: events.isA0,
                  isA1: events.isA1,
                  isLoc: events.isLoc,
                },
                true,
              ),
              undefined,
              true,
            ),
          })
          .from(events)
          .groupBy((t) => [t.value])
          .orderBy(events.value);
      });
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
          .select({ name: TopicsTable.name })
          .from(TopicsTable)
          .where(eq(TopicsTable.id, id)),
      );

      if (topic == null) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      const [[totalData], sentencesData, entitiesData] = await logAndRethrow(
        () => {
          const topicSentences = db
            .select({
              documentId: TopicSentences.documentId,
              sentenceAid: TopicSentences.sentenceAid,
              content: TextAnnotationTable.content,
              similarity: TopicSentences.similarity,
            })
            .from(TopicSentences)
            .innerJoin(
              TextAnnotationTable,
              eq(TextAnnotationTable.id, TopicSentences.sentenceAid),
            )
            .where(eq(TopicSentences.topicId, id))
            .orderBy(desc(TopicSentences.similarity))
            .as(randomAlphaUnderscore());

          const sentenceSearch = db
            .selectDistinct({
              content: topicSentences.content,
            })
            .from(topicSentences)
            .limit(20);

          const baseEntityQuery = Annotations.getAnnotationsWithOntology({
            options: { normalize: true },
            limitTo: [
              "ALL.Entity.Physical",
              "ALL.Entity.Abstract.Social_And_Collective",
            ],
            annotationFields: ["sentenceAid"],
            computedColumns: (o) => ({
              value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
            }),
          }).as("base_entities");

          const entities = db
            .select({
              entity: baseEntityQuery.content,
              type: baseEntityQuery.value,
              count: count().as(randomAlphaUnderscore()),
            })
            .from(topicSentences)
            .innerJoin(
              baseEntityQuery,
              eq(topicSentences.sentenceAid, baseEntityQuery.sentenceAid),
            )
            .groupBy((t) => [t.entity, t.type])
            .orderBy((t) => [desc(t.count), asc(t.entity)])
            .having((t) => gte(t.count, 2));

          const totalCount = db
            .select({
              count: count(),
              docs: countDistinct(topicSentences.documentId),
            })
            .from(topicSentences);

          return Promise.all([totalCount, sentenceSearch, entities]);
        },
      );

      return {
        name: topic.name,
        sentenceCount: totalData.count,
        documentCount: totalData.docs,
        sentences: sentencesData,
        entities: entitiesData,
      };
    }),

  getCohorts: protectedProcedure.query(async () => {
    const [similarities, pointsRaw] = await logAndRethrow(() => {
      const s1 = alias(AnnotationCounts, "s1");
      const s2 = alias(AnnotationCounts, "s2");
      const similarityQuery = db
        .select({
          id1: sql<string>`CONCAT(${s1.content},'-',${s1.type})`.as("id1"),
          id2: sql<string>`CONCAT(${s2.content},'-',${s2.type})`.as("id2"),
          similarity: sql<number>`
       ${AnnotationCoOccurrence.documentCount}::float /
       NULLIF( (${s1.documentCount} + ${s2.documentCount}  -${AnnotationCoOccurrence.documentCount}),0)
      `.as("similarity"),
        })
        .from(AnnotationCoOccurrence)
        .innerJoin(
          s1,
          and(
            eq(AnnotationCoOccurrence.source, sql`${s1.content}`),
            eq(AnnotationCoOccurrence.sourceType, s1.type),
          ),
        )
        .innerJoin(
          s2,
          and(
            eq(AnnotationCoOccurrence.target, sql`${s2.content}`),
            eq(AnnotationCoOccurrence.targetType, s2.type),
          ),
        )
        .where((t) =>
          and(
            gte(t.similarity, 0.25),
            sql`${s1.type} <@ 'ALL.Entity'`,
            sql`${s2.type} <@ 'ALL.Entity'`,
            gt(s1.documentCount, 5),
            gt(s2.documentCount, 5),
          ),
        );

      return Promise.all([
        similarityQuery,
        db
          .select({
            id: sql<string>`CONCAT(${AnnotationCounts.content},'-',${AnnotationCounts.type})`.as(
              "id",
            ),
            name: AnnotationCounts.content,
            support: AnnotationCounts.documentCount,
            r: sql<number>`20`,
          })
          .from(AnnotationCounts)
          .where(
            and(
              gt(AnnotationCounts.documentCount, 5),
              sql`${AnnotationCounts.type} <@ 'ALL.Entity'`,
            ),
          ),
      ]);
    });

    const points = pointsRaw.filter((p) =>
      similarities.find((s) => s.id1 === p.id || s.id2 === p.id),
    );

    const clusters: Record<string, string> = {};
    points.forEach((p) => {
      clusters[p.id] = p.id;
    });

    for (let i = 0; i < 50; i++) {
      Object.keys(clusters).forEach((p) => {
        clusters[p] =
          similarities
            .map((s) => {
              if (s.id2 === p && clusters[s.id1] < clusters[p]) {
                return clusters[s.id1];
              }
              if (s.id1 === p && clusters[s.id2] < clusters[p]) {
                return clusters[s.id2];
              }
              return null;
            })
            .filter(Boolean)[0] ?? clusters[p];
      });
    }

    const groups: Record<string, string[]> = {};
    Object.entries(clusters).forEach(([id, name]) => {
      if (groups[name] == null) {
        groups[name] = [];
      }
      groups[name].push(id);
    });

    const finalClusters = Object.entries(groups)
      .sort((a, b) => b[1].length - a[1].length)
      .map(([id, points]) =>
        points.map((p) => {
          const parts = p.split("-");
          return {
            id: p,
            name: parts.slice(0, -1).join("-"),
            type: parts[parts.length - 1],
          };
        }),
      );

    const colored = points.map(
      (p) =>
        ({
          ...p,
          color: `var(--color-${getColorName(clusters[p.id]).toLowerCase()}-500)`,
        }) as Point,
    );

    return {
      clusters: finalClusters,
      points: colored,
      similarities,
    };
  }),

  getCohortInformation: protectedProcedure
    .input(
      z.object({
        cohort: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      const array = sql.join(
        input.cohort.map((c) => sql`${c}`),
        sql`, `,
      );

      const edges = await logAndRethrow(() =>
        db
          .select({
            source: AnnotationCoOccurrence.source,
            sourceId:
              sql<string>`CONCAT(${AnnotationCoOccurrence.source},'-',${AnnotationCoOccurrence.sourceType})`.as(
                "source_id",
              ),
            target: AnnotationCoOccurrence.target,
            targetId:
              sql<string>`CONCAT(${AnnotationCoOccurrence.target},'-',${AnnotationCoOccurrence.targetType})`.as(
                "target_id",
              ),
            documentCount: AnnotationCoOccurrence.documentCount,
            sentenceCount: AnnotationCoOccurrence.sentenceCount,
          })
          .from(AnnotationCoOccurrence)
          .where(
            and(
              or(
                sql`CONCAT(${AnnotationCoOccurrence.source},'-',${AnnotationCoOccurrence.sourceType}) in (${array})`,
                sql`CONCAT(${AnnotationCoOccurrence.target},'-',${AnnotationCoOccurrence.targetType}) in (${array})`,
              ),
              gt(AnnotationCoOccurrence.documentCount, 5),
            ),
          )
          .orderBy((t) => [t.sourceId, t.targetId]),
      );

      const grouped: Record<string, string[]> = {};
      edges.forEach((e) => {
        const s1Id = e.sourceId;
        const s2Id = e.targetId;
        if (grouped[s2Id] == null) {
          grouped[s2Id] = [];
        }
        grouped[s2Id].push(s1Id);
        if (grouped[s1Id] == null) {
          grouped[s1Id] = [];
        }
        grouped[s1Id].push(s2Id);
      });
      const ranked = Object.entries(grouped)
        .sort((a, b) => b[1].length - a[1].length)
        .map(([a, b]) => ({
          id: a,
          support: b.length,
        }));

      return { edges, ranked };
    }),

  updateAnalyticsTables: protectedProcedure.mutation(async ({ ctx }) => {
    const { user } = ctx;

    if (
      !roleHasPermissions(user.role, [
        "ontology:edit",
        "data:load",
        "data:update",
        "model:create",
      ])
    ) {
      throw new TRPCError({ code: "UNAUTHORIZED" });
    }

    const { isError } = await tryCatch(
      (async () => {
        await db.refreshMaterializedView(AnnotationCounts).concurrently();
        await db.refreshMaterializedView(AnnotationCoOccurrence).concurrently();
        return true;
      })(),
    );

    const client = await createRedisClient();
    try {
      await client.publish(
        "events",
        JSON.stringify({
          type: "analytics_update",
          userid: user.id,
          payload: { completed: !isError },
        }),
      );
    } catch (e) {
      console.error(e);
    } finally {
      await client.close();
    }

    return { code: 200 };
  }),
});
