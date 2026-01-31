import { db } from "@/lib/db";
import { TopicSentences, TopicsTable } from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { desc, eq, gt, gte, sql } from "drizzle-orm";
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
          })
          .from(TopicsTable)
          .where(eq(TopicsTable.id, id)),
      );

      if (topic == null) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      const [[totalData], sentencesData, entitiesData] = await logAndRethrow(
        () => {
          const sentenceSearch = db
            .select({
              documentId: TopicSentences.documentId,
              content: TopicSentences.sentence,
              similarity: TopicSentences.similarity,
            })
            .from(TopicSentences)
            .where(eq(TopicSentences.topicId, id))
            .orderBy(desc(TopicSentences.similarity))
            .limit(20);

          return Promise.all([
            [{ count: topic.count, docs: topic.docs }],
            sentenceSearch,
            topicInformation(id),
          ]);
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
    const result = await inngest.send({
      name: "analytics/update",
      data: {
        userId: user.id,
      },
    });
    // return result;
    // await requirePermissions(user, undefined, [
    //   "ontology:edit",
    //   "data:load",
    //   "data:update",
    //   "model:create",
    // ]);
    //
    // const { isError } = await tryCatch(
    //   (async () => {
    //     await updateAnalytics();
    //     // await db.refreshMaterializedView(AnnotationCounts).concurrently();
    //     // await db.refreshMaterializedView(AnnotationCoOccurrence).concurrently();
    //     return true;
    //   })(),
    // );

    // const client = await createRedisClient();
    // try {
    //   await client.publish(
    //     "events",
    //     JSON.stringify({
    //       type: "analytics_update",
    //       userid: user.id,
    //       payload: { completed: !isError },
    //     }),
    //   );
    // } catch (e) {
    //   console.error(e);
    // } finally {
    //   await client.close();
    // }

    return { code: 200 };
  }),
});
