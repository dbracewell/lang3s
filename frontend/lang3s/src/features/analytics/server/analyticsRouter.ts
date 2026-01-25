import { db } from "@/lib/db";
import {
  AnnotationCoOccurrence,
  AnnotationCounts,
  AnnotationWithOntologyView,
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
  isNotNull,
  isNull,
  lt,
  ne,
  not,
  notInArray,
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
import {
  Annotations,
  createPathWildcards,
  matchPath,
} from "@/lib/db/annotations";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { TRPCError } from "@trpc/server";
import { Point } from "@/components/charts/ForceGraph";
import { getColorName } from "@/lib/utils/colors";
import { createRedisClient } from "@/lib/redis";
import { requirePermissions } from "@/features/auth/server/actions";
import { remap } from "@/lib/utils/math";

export const AnalyticsRouter = createTRPCRouter({
  getAnnotationEntropy: protectedProcedure
    .input(
      z.object({
        values: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(async () => {
        const entityTopics = db
          .select({
            entity: AnnotationWithOntologyView.normalized,
            type: AnnotationWithOntologyView.path,
            topicId: TopicSentences.topicId,
            count: count().as("count"),
          })
          .from(AnnotationWithOntologyView)
          .innerJoin(
            TopicSentences,
            eq(
              TopicSentences.sentenceAid,
              AnnotationWithOntologyView.sentenceAid,
            ),
          )
          .where(matchPath(AnnotationWithOntologyView.path, input.values))
          .groupBy(
            AnnotationWithOntologyView.normalized,
            AnnotationWithOntologyView.path,
            TopicSentences.topicId,
          )
          .having((t) =>
            and(
              sql`count(distinct ${AnnotationWithOntologyView.documentId}) > 5`,
            ),
          )
          .as("entityTopics");

        const probabilities = db
          .select({
            entityId: entityTopics.entity,
            type: entityTopics.type,
            p: sql<number>`
        ${entityTopics.count}::float /
        SUM(${entityTopics.count}) OVER (PARTITION BY CONCAT(${entityTopics.entity},'-',${entityTopics.type}))
      `.as("p"),
          })
          .from(entityTopics)
          .as("probabilities");

        const base = db
          .select({
            entityId: probabilities.entityId,
            entityType: probabilities.type,
            rawScore: sql<number>`
        -SUM(
          ${probabilities.p} * (LN(${probabilities.p}) / LN(2))
        )
      `.as("entropy_score"),
          })
          .from(probabilities)
          .groupBy(probabilities.entityId, probabilities.type);

        const lowQuery = db
          .select()
          .from(base.as("query"))
          .orderBy((t) => asc(t.rawScore))
          .limit(25);
        const highQuery = db
          .select()
          .from(base.as("query"))
          .orderBy((t) => desc(t.rawScore))
          .limit(25);
        const [low, high] = await Promise.all([lowQuery, highQuery]);
        const maxLowV = low.length > 0 ? 1 / (low[0].rawScore + 0.0001) : 0;
        const minLowV =
          low.length > 0 ? 1 / (low.slice(-1)[0].rawScore + 0.0001) : 0;

        const maxHighV = high.length > 0 ? high[0].rawScore : 0;
        const lowHighV = high.length > 0 ? high.slice(-1)[0].rawScore : 0;

        return [
          ...low.map((m) => ({
            ...m,
            category: "low",
            normScore:
              1 / (m.rawScore + 0.0001) === maxLowV
                ? 1
                : remap(m.rawScore, minLowV, maxLowV, 0, 1),
          })),
          ...high.reverse().map((m) => ({
            ...m,
            category: "high",
            normScore: remap(m.rawScore, lowHighV, maxHighV, 0, 1),
          })),
        ];
      });
    }),
  getAnnotationLoners: protectedProcedure
    .input(z.object({ values: z.array(z.string()) }))
    .query(async ({ input }) => {
      return await logAndRethrow(async () => {
        const base = db
          .select({
            entityId: AnnotationCoOccurrence.source,
            entityType: AnnotationCoOccurrence.sourceType,
            rawScore:
              sql<number>`( count(${AnnotationCoOccurrence.sentenceAid})::float /  ${AnnotationCoOccurrence.sourceSentenceCount})`.as(
                "score",
              ),
          })
          .from(AnnotationCoOccurrence)
          .where(
            and(
              sql`${AnnotationCoOccurrence.sourceType} ~ any(array[${createPathWildcards(input.values)}]::lquery[])`,
              gt(AnnotationCoOccurrence.sourceDocumentCount, 5),
              gt(AnnotationCoOccurrence.sourceSentenceCount, 10),
              or(
                isNull(AnnotationCoOccurrence.targetType),
                sql`${AnnotationCoOccurrence.targetType} <@ 'ALL.Entity'`,
              ),
              or(
                isNull(AnnotationCoOccurrence.targetDocumentCount),
                gt(AnnotationCoOccurrence.targetDocumentCount, 5),
              ),
            ),
          )
          .groupBy(
            AnnotationCoOccurrence.source,
            AnnotationCoOccurrence.sourceType,
            AnnotationCoOccurrence.sourceSentenceCount,
          );
        const lowQuery = db
          .select()
          .from(base.as("query"))
          .orderBy((t) => t.rawScore)
          .limit(25);
        const highQuery = db
          .select()
          .from(base.as("query"))
          .orderBy((t) => desc(t.rawScore))
          .limit(25);
        const [low, high] = await Promise.all([lowQuery, highQuery]);
        const maxLowV = low.length > 0 ? low[0].rawScore : 0;
        const minLowV = low.length > 0 ? low.slice(-1)[0].rawScore : 0;

        const maxHighV = high.length > 0 ? high[0].rawScore : 0;
        const lowHighV = high.length > 0 ? high.slice(-1)[0].rawScore : 0;

        return [
          ...low.map((m) => ({
            ...m,
            category: "low",
            normScore:
              1 / (m.rawScore + 0.0001) === maxLowV
                ? 1
                : remap(m.rawScore, minLowV, maxLowV, 0, 1),
          })),
          ...high.reverse().map((m) => ({
            ...m,
            category: "high",
            normScore: remap(m.rawScore, lowHighV, maxHighV, 0, 1),
          })),
        ];
      });
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
        const base = db
          .selectDistinct({
            content: AnnotationCounts.content,
            path: AnnotationCounts.type,
            value: sql<string>`${AnnotationCounts.type}`.as("value"),
            count: AnnotationCounts.mentionCount,
            docCount: AnnotationCounts.documentCount,
            sentenceCount: AnnotationCounts.sentenceCount,
            mentionsPerDocument:
              sql<number>`${AnnotationCounts.mentionCount}::float/${AnnotationCounts.documentCount}`.as(
                "mentions_per_doc",
              ),
          })
          .from(AnnotationCounts)
          .where(
            and(
              notInArray(AnnotationCounts.content, [
                "WHO",
                "I",
                "THEY",
                "WE",
                "YOU",
                "HIS",
                "HER",
                "HE",
                "SHE",
                "FIRST",
                "ITS",
                "TWO",
                "ONE",
                "YOUR",
                "IT",
              ]),
              matchPath(AnnotationCounts.type, input.values),
              !!filter
                ? ilike(AnnotationCounts.content, `${filter.toUpperCase()}%`)
                : undefined,
              gt(AnnotationCounts.documentCount, 5),
            ),
          )
          .orderBy((t) =>
            finalSortBy === "mentions"
              ? desc(t.count)
              : finalSortBy === "docs"
                ? desc(t.docCount)
                : desc(t.mentionsPerDocument),
          )
          .as(randomAlphaUnderscore());

        return Promise.all([
          db.select({ count: count() }).from(base),
          withPagination(db.select().from(base), {
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
        const q1 = db
          .select({
            content: AnnotationWithOntologyView.normalized,
            id: AnnotationWithOntologyView.id,
            start: AnnotationWithOntologyView.start,
            end: AnnotationWithOntologyView.end,
            sentenceAid: AnnotationWithOntologyView.sentenceAid,
            value: AnnotationWithOntologyView.path,
          })
          .from(AnnotationWithOntologyView)
          .where(
            and(
              matchPath(AnnotationWithOntologyView.path, [input.leftValue]),
              input.leftText
                ? eq(
                    AnnotationWithOntologyView.normalized,
                    input.leftText.toUpperCase(),
                  )
                : undefined,
            ),
          )
          .as("q1");

        const q2 = db
          .select({
            content: AnnotationWithOntologyView.normalized,
            id: AnnotationWithOntologyView.id,
            start: AnnotationWithOntologyView.start,
            end: AnnotationWithOntologyView.end,
            sentenceAid: AnnotationWithOntologyView.sentenceAid,
            value: AnnotationWithOntologyView.name,
          })
          .from(AnnotationWithOntologyView)
          .where(matchPath(AnnotationWithOntologyView.path, input.rightValues))
          .as("q2");

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
      return await logAndRethrow(async () => {
        const { entity, value } = input;

        const entitiesWithSentences = db
          .selectDistinct({
            sentenceAid: AnnotationWithOntologyView.sentenceAid,
            sentence: TextAnnotationTable.content,
          })
          .from(AnnotationWithOntologyView)
          .innerJoin(
            TextAnnotationTable,
            and(
              eq(
                AnnotationWithOntologyView.sentenceAid,
                TextAnnotationTable.sentenceAid,
              ),
              eq(TextAnnotationTable.type, "sentence"),
            ),
          )
          .where(
            and(
              eq(AnnotationWithOntologyView.normalized, entity.toUpperCase()),
              eq(AnnotationWithOntologyView.path, value),
            ),
          )
          .as(randomAlphaUnderscore());

        const entityLower = entity.toLowerCase();
        const entityLowerArr = sql`ARRAY[${entityLower}]::text[]`;
        const events = db
          .select({
            text: sql<string>`${AnnotationWithOntologyView.content}`.as(
              randomAlphaUnderscore(),
            ),
            value: AnnotationWithOntologyView.name,
            A0: AnnotationWithOntologyView.a0Text,
            A1: AnnotationWithOntologyView.a1Text,
            TIME: AnnotationWithOntologyView.timeText,
            LOC: AnnotationWithOntologyView.locText,
            sentence: entitiesWithSentences.sentence,
          })
          .from(AnnotationWithOntologyView)
          .innerJoin(
            entitiesWithSentences,
            eq(
              entitiesWithSentences.sentenceAid,
              AnnotationWithOntologyView.sentenceAid,
            ),
          )
          .where(
            or(
              sql`lower_array(${AnnotationWithOntologyView.a0Text}) && ${entityLowerArr}`,
              sql`lower_array(${AnnotationWithOntologyView.a1Text}) && ${entityLowerArr}`,
              sql`lower(${AnnotationWithOntologyView.locText}) = ${entityLower}`,
              sql`lower(${AnnotationWithOntologyView.timeText}) = ${entityLower}`,
            ),
          )
          .as(randomAlphaUnderscore());

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
      const similarityQuery = db
        .select({
          id1: AnnotationCoOccurrence.sourceNorm,
          id2: sql<string>`${AnnotationCoOccurrence.targetNorm}`.as(
            "target_norm",
          ),
          similarity: sql<number>`
       ${countDistinct(AnnotationCoOccurrence.documentId)}::float /
       NULLIF( (${AnnotationCoOccurrence.sourceDocumentCount} + ${AnnotationCoOccurrence.targetDocumentCount}  -${countDistinct(AnnotationCoOccurrence.documentId)}),0)
      `.as("similarity"),
        })
        .from(AnnotationCoOccurrence)
        .where((t) =>
          and(
            isNotNull(AnnotationCoOccurrence.targetNorm),
            sql`${AnnotationCoOccurrence.sourceType} <@ 'ALL.Entity'`,
            not(
              sql`${AnnotationCoOccurrence.sourceType} <@ 'ALL.Entity.Abstract.Temporal_And_Occurrence'`,
            ),
            not(
              sql`${AnnotationCoOccurrence.sourceType} <@ 'ALL.Entity.Abstract.Value_And_Quantification'`,
            ),
            sql`${AnnotationCoOccurrence.targetType} <@ 'ALL.Entity'`,
            not(
              sql`${AnnotationCoOccurrence.targetType} <@ 'ALL.Entity.Abstract.Temporal_And_Occurrence'`,
            ),
            not(
              sql`${AnnotationCoOccurrence.targetType} <@ 'ALL.Entity.Abstract.Value_And_Quantification'`,
            ),
            gt(AnnotationCoOccurrence.sourceDocumentCount, 5),
            gt(AnnotationCoOccurrence.targetDocumentCount, 5),
          ),
        )
        .groupBy((t) => [
          t.id1,
          t.id2,
          AnnotationCoOccurrence.targetDocumentCount,
          AnnotationCoOccurrence.sourceDocumentCount,
        ])
        .having((t) => gte(t.similarity, 0.25));

      return Promise.all([
        similarityQuery,
        db
          .selectDistinct({
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
              not(
                sql`${AnnotationCounts.type} <@ 'ALL.Entity.Abstract.Temporal_And_Occurrence'`,
              ),
              not(
                sql`${AnnotationCounts.type} <@ 'ALL.Entity.Abstract.Value_And_Quantification'`,
              ),
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
      .map(([_, points]) =>
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

      console.log(input.cohort);

      const edges = await logAndRethrow(() =>
        db
          .select({
            source: AnnotationCoOccurrence.source,
            sourceId: AnnotationCoOccurrence.sourceNorm,
            target: sql<string>`${AnnotationCoOccurrence.target}`.as("target"),
            targetId: sql<string>`${AnnotationCoOccurrence.targetNorm}`.as(
              "target_id",
            ),
            documentCount: countDistinct(AnnotationCoOccurrence.documentId).as(
              "document_count",
            ),
            sentenceCount: countDistinct(AnnotationCoOccurrence.sentenceAid).as(
              "document_count",
            ),
          })
          .from(AnnotationCoOccurrence)
          .where(
            and(
              isNotNull(AnnotationCoOccurrence.targetNorm),
              sql`${AnnotationCoOccurrence.sourceNorm} in (${array})`,
              sql`${AnnotationCoOccurrence.targetNorm} in (${array})`,
            ),
          )
          .groupBy((t) => [
            t.source,
            t.sourceId,
            AnnotationCoOccurrence.targetNorm,
            AnnotationCoOccurrence.target,
          ])
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

    await requirePermissions(user, undefined, [
      "ontology:edit",
      "data:load",
      "data:update",
      "model:create",
    ]);

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
