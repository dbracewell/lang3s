import { db } from "@/lib/db";
import {
  DocumentsTable,
  KeywordsTable,
  TopicSentences,
  TopicsTable,
} from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { and, count, desc, eq, gt, gte, isNotNull, sql } from "drizzle-orm";
import z from "zod";
import { TRPCError } from "@trpc/server";
import { Point } from "@/components/charts/ForceGraph";
import { getColorName } from "@/lib/utils/colors";
import {
  annotationAffinity,
  annotationCoOccurrence,
  annotationCounts,
  annotationEvents,
  annotationTopicScore,
  cohorts,
  cohortSupportInformation,
  topicInformation,
} from "@/features/analytics/server/analyticsApi";
import { inngest } from "@/lib/inngest/client";
import { randomAlphaUnderscore } from "@/lib/utils/random";

export const AnalyticsRouter = createTRPCRouter({
  getAnnotationEntropy: protectedProcedure
    .input(
      z.object({
        values: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(async () => {
        return annotationTopicScore(input.values);
      });
    }),

  getAnnotationLoners: protectedProcedure
    .input(z.object({ values: z.array(z.string()) }))
    .query(async ({ input }) => {
      return await logAndRethrow(async () => {
        return annotationAffinity(input.values);
      });
    }),

  getAnnotationCounts: protectedProcedure
    .input(
      z.object({
        values: z.array(z.string()),
        page: z.number().nullish(),
        sortBy: z
          .enum(["mention_count", "document_count", "mentions_per_document"])
          .nullish(),
        filter: z.string().nullish(),
      }),
    )
    .query(async ({ input }) => {
      const page = Math.max(1, input.page ?? 1);
      const filter = input.filter;
      const finalSortBy = input.sortBy ?? "mention_count";
      return await annotationCounts(page, finalSortBy, input.values, filter);
    }),

  getAnnotationCoOccurrence: protectedProcedure
    .input(
      z.object({
        leftValue: z.string(),
        leftText: z.string(),
        rightValues: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(() => {
        return annotationCoOccurrence(
          input.leftText,
          input.leftValue,
          input.rightValues,
        );
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
        return annotationEvents(input.entity, input.value);
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
          .select({
            name: TopicsTable.name,
            count: TopicsTable.support,
            docs: TopicsTable.documents,
            embedding: TopicsTable.embedding,
          })
          .from(TopicsTable)
          .where(eq(TopicsTable.id, id)),
      );

      if (topic == null) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      const [[totalData], sentencesData, entitiesData, keywordData] =
        await logAndRethrow(() => {
          const sentenceSearch = db
            .select({
              documentId: TopicSentences.documentId,
              content: TopicSentences.sentence,
              similarity: TopicSentences.similarity,
            })
            .from(TopicSentences)
            .where(eq(TopicSentences.topicId, id))
            .orderBy(desc(TopicSentences.similarity))
            .limit(200)
            .as(randomAlphaUnderscore());

          const topicDocuments = db
            .select({
              documentId: TopicSentences.documentId,
            })
            .from(TopicSentences)
            .where(eq(TopicSentences.topicId, id))
            .as(randomAlphaUnderscore());

          const keywords = db
            .select({
              category: KeywordsTable.category,
              count: count().as("count"),
            })
            .from(KeywordsTable)
            .innerJoin(
              topicDocuments,
              eq(KeywordsTable.documentId, topicDocuments.documentId),
            )
            .where(isNotNull(KeywordsTable.category))
            .groupBy(KeywordsTable.category)
            .orderBy((t) => desc(t.count))
            .having((t) => gt(t.count, 2))
            .limit(25);

          return Promise.all([
            [{ count: topic.count, docs: topic.docs }],
            db
              .selectDistinctOn([sentenceSearch.content])
              .from(sentenceSearch)
              .orderBy((t) => t.content)
              .limit(20),
            topicInformation(id),
            keywords,
          ]);
        });

      return {
        name: topic.name,
        sentenceCount: totalData.count,
        documentCount: totalData.docs,
        sentences: sentencesData.sort((a, b) => b.similarity - a.similarity),
        entities: entitiesData,
        keywords: keywordData,
      };
    }),

  getCohorts: protectedProcedure.query(async () => {
    const cohort_result = await logAndRethrow(() => {
      return cohorts();
    });
    const colored = cohort_result.nodes.map((p) => {
      return {
        ...p,
        color: `var(--color-${getColorName(cohort_result.id_cid[p.id]).toLowerCase()}-500)`,
      } as Point;
    });

    return {
      clusters: cohort_result.clusters,
      points: colored,
      similarities: cohort_result.edges,
    };
  }),

  getCohortInformation: protectedProcedure
    .input(
      z.object({
        cohort: z.array(z.string()),
      }),
    )
    .query(async ({ input }) => {
      return await logAndRethrow(() => cohortSupportInformation(input.cohort));
    }),

  updateAnalyticsTables: protectedProcedure.mutation(async ({ ctx }) => {
    const { user } = ctx;
    await inngest.send({
      name: "analytics/update",
      data: {
        userId: user.id,
      },
    });
    return { code: 200 };
  }),

  getConceptGraph: protectedProcedure.query(async () => {
    const minCount = 25;
    const [nodes, links] = await logAndRethrow(() => {
      const categoryInfo = db.$with("category_info").as(
        db
          .selectDistinctOn(
            [KeywordsTable.category, KeywordsTable.documentId],
            {
              category: KeywordsTable.category,
              documentId: KeywordsTable.documentId,
              cnt: sql<number>`count(*) over (partition by ${KeywordsTable.category})`.as(
                "cnt",
              ),
            },
          )
          .from(KeywordsTable)
          .where(isNotNull(KeywordsTable.category))
          .groupBy(KeywordsTable.category, KeywordsTable.documentId),
      );

      const totalDocs = db
        .$with("total_docs")
        .as(db.select({ d: count().as("d") }).from(DocumentsTable));

      const cooc = db.$with("cooc").as(
        db
          .select({
            source: sql<string>`a.category`.as("source"),
            sourceCount: sql<number>`a.cnt`.as("source_count"),
            target: sql<string>`b.category`.as("target"),
            targetCount: sql<number>`b.cnt`.as("target_count"),
            count: count().as("count"),
          })
          .from(sql`${categoryInfo} as a`) // Use raw SQL to alias the CTE
          .innerJoin(
            sql`${categoryInfo} as b`,
            sql`a.document_id = b.document_id AND a.category != b.category`,
          )
          .where(sql`a.category < b.category`)
          .groupBy(sql`a.category, b.category, a.cnt, b.cnt`)
          .having((t) => gt(t.count, 0)),
      );

      const nodes = db
        .select({
          id: sql<string>`${KeywordsTable.category}`.as("id"),
          group: sql<string>`${KeywordsTable.category}`.as("group"),
          count: count().as("count"),
        })
        .from(KeywordsTable)
        .where(isNotNull(KeywordsTable.category))
        .groupBy(KeywordsTable.category)
        .having((t) => gt(t.count, minCount));

      const links = db
        .with(categoryInfo, totalDocs, cooc)
        .select({
          source: cooc.source,
          target: cooc.target,
          value: sql<number>`ln((${cooc.count}::float * ${totalDocs.d}::float) / (${cooc.sourceCount}::float * ${cooc.targetCount}::float))`,
        })
        .from(cooc)
        .innerJoin(totalDocs, sql`1 = 1`)
        .where((t) =>
          and(
            gt(t.value, 1.5),
            gt(cooc.sourceCount, minCount),
            gt(cooc.targetCount, minCount),
          ),
        );
      return Promise.all([nodes, links]);
    });

    return {
      nodes,
      links,
    };
  }),
});
