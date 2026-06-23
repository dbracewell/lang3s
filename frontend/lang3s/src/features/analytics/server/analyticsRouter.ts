import { db } from "@/lib/db";
import {
  ConceptCoOccurrence,
  DocumentsTable,
  DocumentTopicConcepts,
  KeywordsTable,
  TopicSentences,
  TopicsTable,
  TopicTree,
  TopicTree2Topic
} from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { aliasedTable, and, count, desc, eq, gt, gte, isNotNull, sql } from "drizzle-orm";
import z from "zod";
import { TRPCError } from "@trpc/server";
import { getColorName } from "@/lib/utils/colors";
import {
  annotationAffinity,
  annotationCoOccurrence,
  annotationCounts,
  annotationEvents,
  annotationTopicScore,
  cohorts,
  cohortSupportInformation,
  topicInformation
} from "@/features/analytics/server/analyticsApi";
import { inngest } from "@/lib/inngest/client";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { ForceGraphPoint } from "@/components/d3/ForceGraph/types";
import { truncateText } from "@/lib/utils/formatters";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";
import { TopicNode } from "@/features/analytics/types";
import { coalesce } from "@/lib/db/funcs";

const walkTree = (
  node: Omit<TopicNode, "children">,
  parentToChild: Record<string, Omit<TopicNode, "children">[]>,
): TopicNode => {
  return {
    ...node,
    children: parentToChild[node.id]
      ? parentToChild[node.id].map((child) => walkTree(child, parentToChild))
      : ([] as TopicNode[]),
  };
};

export const AnalyticsRouter = createTRPCRouter({
  getTopicTree: protectedProcedure.query(async () => {
    const nodes = await logAndRethrow(async () => {
      return db
        .select({
          id: TopicTree.id,
          name: TopicTree.name,
          parent: TopicTree.parent,
          isLeaf: coalesce(TopicTree.isLeaf, false),
          topics: jsonAgg(
            jsonBuildObject({
              id: TopicsTable.id,
              name: TopicsTable.name,
              support: TopicsTable.support,
              docSupport: TopicsTable.documents,
            }),
          ),
        })
        .from(TopicTree)
        .leftJoin(TopicTree2Topic, eq(TopicTree2Topic.nodeId, TopicTree.id))
        .leftJoin(TopicsTable, eq(TopicTree2Topic.topicId, TopicsTable.id))
        .groupBy((t) => [t.id, t.parent, t.name, t.isLeaf]);
    });

    const parentToChild: Record<string, Omit<TopicNode, "children">[]> = {};
    let rootNode: Omit<TopicNode, "children"> | null = null;

    nodes.forEach((node) => {
      if (node.parent != null) {
        if (parentToChild[node.parent] == null) {
          parentToChild[node.parent] = [];
        }
        parentToChild[node.parent].push(node);
      } else {
        rootNode = node;
      }
    });

    if (rootNode == null) {
      return null;
    }

    return walkTree(rootNode, parentToChild);
  }),

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
      try {
        return await annotationCounts(page, finalSortBy, input.values, filter);
      } catch (error) {
        console.error(error);
        throw error;
      }
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
            .selectDistinct({
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
      } as ForceGraphPoint;
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

  getCorpusMap: protectedProcedure.query(async () => {
    const [rawNodes, similarities] = await logAndRethrow(() => {
      const nodes = db.select().from(DocumentTopicConcepts);

      const s1 = aliasedTable(TopicsTable, "s1");
      const s2 = aliasedTable(TopicsTable, "s2");
      const similarity = sql<number>`1 - (${s1.embedding}::halfvec <=> ${s2.embedding}::halfvec)::float`;
      const topicSimilarities = db
        .select({
          id1: s1.id,
          id2: s2.id,
          type: sql<string>`${"topic"}`.as("type"),
          similarity: similarity,
        })
        .from(s1)
        .innerJoin(s2, gt(s1.id, s2.id))
        .where((t) => gte(t.similarity, 0.7));

      const totalDocuments = db
        .select({ count: count().as("count") })
        .from(DocumentsTable)
        .as(randomAlphaUnderscore());

      const conceptSimilarities = db
        .select({
          id1: ConceptCoOccurrence.source,
          id2: ConceptCoOccurrence.target,
          type: sql<string>`${"concept"}`.as("type"),
          similarity: sql<number>`
              CASE
               WHEN ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float)) > 0.5
               THEN 1 + ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float))
               ELSE 0.25
              END
              `,
        })
        .from(ConceptCoOccurrence)
        .innerJoin(totalDocuments, sql`1=1`)
        .groupBy((t) => [
          t.id1,
          t.id2,
          ConceptCoOccurrence.sourceCount,
          ConceptCoOccurrence.targetCount,
          totalDocuments.count,
        ]);

      const allSims = topicSimilarities.unionAll(conceptSimilarities);

      return Promise.all([nodes, allSims]);
    });

    interface CustomPoint extends ForceGraphPoint {
      type: "topic" | "concept" | "entity";
      subvalues: Record<string, number>;
    }

    const nodes: Record<string, CustomPoint> = {};
    for (let row of rawNodes) {
      if (!(row.topicId in nodes)) {
        nodes[row.topicId] = {
          id: row.topicId,
          type: "topic",
          text: row.topic,
          display: truncateText(row.topic),
          value: row.topicCount,
          subvalues: {},
        };
      }
      if ((row.overlap as number) <= 5) {
        continue;
      }

      nodes[row.topicId].subvalues[row.concept] = row.overlap;

      if (!(row.concept in nodes)) {
        nodes[row.concept] = {
          id: row.concept,
          type: "concept",
          text: row.concept,
          display: truncateText(row.concept),
          value: row.conceptCount,
          subvalues: row.instances,
        };
      }
    }

    const maxConceptSim = Math.max(
      ...similarities
        .filter((s) => s.type === "concept")
        .map((s) => s.similarity),
    );
    const minConceptSim = Math.min(
      ...similarities
        .filter((s) => s.type === "concept")
        .map((s) => s.similarity),
    );

    return {
      nodes: Object.values(nodes),
      similarities: similarities.map((s) => {
        if (s.type === "topic") {
          return s;
        }
        return {
          ...s,
          similarity:
            (s.similarity - minConceptSim) *
            (1 / (maxConceptSim - minConceptSim)),
        };
      }),
    };

    // const [topicNodes, topicSimilarities] = await logAndRethrow(() => {
    //   const concepts = db
    //     .select({
    //       documentId: KeywordsTable.documentId,
    //       text: KeywordsTable.category,
    //     })
    //     .from(KeywordsTable)
    //     .where(isNotNull(KeywordsTable.category))
    //     .as(randomAlphaUnderscore());
    //
    //   const nodes = db
    //     .select({
    //       id: TopicSentences.topicId,
    //       type: sql<string>`${"topic"}`.as("type"),
    //       text: TopicsTable.name,
    //       value: countDistinct(TopicSentences.documentId).as("count"),
    //       subvalues: jsonAgg(
    //         jsonBuildObject({
    //           kw: concepts.text,
    //         }),
    //       ).as("subvalues"),
    //     })
    //     .from(TopicSentences)
    //     .innerJoin(TopicsTable, eq(TopicsTable.id, TopicSentences.topicId))
    //     .leftJoin(
    //       concepts,
    //       eq(concepts.documentId, TopicSentences.documentId),
    //     )
    //     .groupBy((t) => [t.id, t.text])
    //     .orderBy((t) => desc(t.value));
    //
    //   const s1 = db
    //     .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
    //     .from(TopicsTable)
    //     .as("t1");
    //   const s2 = db
    //     .select({ id: TopicsTable.id, embedding: TopicsTable.embedding })
    //     .from(TopicsTable)
    //     .as("t2");
    //
    //   const similarity = sql<number>`1 - (${s1.embedding}::halfvec <=> ${s2.embedding}::halfvec)::float`;
    //
    //   const similarities = db
    //     .select({
    //       id1: s1.id,
    //       id2: s2.id,
    //       similarity: similarity,
    //     })
    //     .from(s1)
    //     .innerJoin(s2, gt(s1.id, s2.id))
    //     .where((t) => gte(t.similarity, 0.7));
    //
    //   return Promise.all([nodes, similarities]);
    // });
    //
    // const finalTopicNodes = topicNodes.map((n) => {
    //   const subValueCounts = n.subvalues.reduce(
    //     (agg, v) => {
    //       if (!(v.kw in agg)) {
    //         agg[v.kw] = 0;
    //       }
    //       agg[v.kw] += 1;
    //       return agg;
    //     },
    //     {} as Record<string, number>,
    //   );
    //   return {
    //     ...n,
    //     subvalues: Object.entries(subValueCounts)
    //       .filter(([k, v]) => v > 5)
    //       .map(([k, v]) => ({
    //         kw: k,
    //       }))
    //       .sort((a, b) => a.kw.localeCompare(b.kw)),
    //   };
    // });
    //
    // if (!topicId) {
    //   return {
    //     nodes: finalTopicNodes,
    //     similarities: topicSimilarities,
    //   };
    // }
    //
    // const [[topic], conceptNodes, conceptSimilarities] = await logAndRethrow(
    //   () => {
    //     const topicDocuments = db
    //       .selectDistinct({
    //         documentId: TopicSentences.documentId,
    //       })
    //       .from(TopicSentences)
    //       .where(eq(TopicSentences.topicId, topicId))
    //       .as(randomAlphaUnderscore());
    //
    //     const topic = db
    //       .select({ name: TopicsTable.name })
    //       .from(TopicsTable)
    //       .where(eq(TopicsTable.id, topicId));
    //
    //     const totalDocuments = db
    //       .select({ count: count().as("total_documents") })
    //       .from(topicDocuments)
    //       .as(randomAlphaUnderscore());
    //
    //     const nodes = db
    //       .select({
    //         id: sql<string>`${KeywordsTable.category}`.as("id"),
    //         type: sql<string>`${"concept"}`.as("type"),
    //         text: sql<string>`${KeywordsTable.category}`.as("text"),
    //         value: count().as("count"),
    //         subvalues: jsonAgg(
    //           jsonBuildObject({
    //             kw: KeywordsTable.keyword,
    //           }),
    //         ).as("subvalues"),
    //       })
    //       .from(KeywordsTable)
    //       .innerJoin(
    //         topicDocuments,
    //         eq(KeywordsTable.documentId, topicDocuments.documentId),
    //       )
    //       .where(isNotNull(KeywordsTable.category))
    //       .groupBy(KeywordsTable.category)
    //       .orderBy((t) => desc(t.value))
    //       .having((t) => gte(t.value, 5))
    //       .limit(50);
    //
    //     const subselect = nodes.as("subselect");
    //     const similarities = db
    //       .select({
    //         id1: ConceptCoOccurrence.source,
    //         id2: ConceptCoOccurrence.target,
    //         similarity: sql<number>`
    //         CASE
    //          WHEN ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float)) > 0.5
    //          THEN 1 + ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float))
    //          ELSE 0.25
    //         END
    //         `,
    //       })
    //       .from(ConceptCoOccurrence)
    //       .innerJoin(
    //         subselect,
    //         or(
    //           eq(ConceptCoOccurrence.source, subselect.id),
    //           eq(ConceptCoOccurrence.target, subselect.id),
    //         ),
    //       )
    //       .innerJoin(
    //         topicDocuments,
    //         eq(topicDocuments.documentId, ConceptCoOccurrence.documentId),
    //       )
    //       .innerJoin(totalDocuments, sql`1=1`)
    //       .groupBy((t) => [
    //         t.id1,
    //         t.id2,
    //         ConceptCoOccurrence.sourceCount,
    //         ConceptCoOccurrence.targetCount,
    //         totalDocuments.count,
    //       ]);
    //     return Promise.all([topic, nodes, similarities]);
    //   },
    // );
    //
    // if (topic == null) {
    //   throw new TRPCError({ code: "NOT_FOUND" });
    // }
    //
    // const filteredTopicSims = topicSimilarities.filter(
    //   (sim) => sim.id1 === topicId || sim.id2 === topicId,
    // );
    // const addedConceptSims = conceptNodes.flatMap((node) =>
    //   filteredTopicSims.map((sim) => {
    //     if (sim.id1 === topicId) {
    //       return { ...sim, id1: node.id };
    //     }
    //     return { ...sim, id2: node.id };
    //   }),
    // );
    //
    // const maxConceptSim = Math.max(
    //   ...conceptSimilarities.map((s) => s.similarity),
    // );
    // const minConceptSim = Math.min(
    //   ...conceptSimilarities.map((s) => s.similarity),
    // );
    // const adjustedConceptSims = conceptSimilarities.map((s) => ({
    //   ...s,
    //   similarity:
    //     (s.similarity - minConceptSim) *
    //     (1 / (maxConceptSim - minConceptSim)),
    // }));
    //
    // if (!conceptId) {
    //   return {
    //     selectedTopic: topic.name,
    //     selectedTopicCount: topicNodes.filter((p) => p.id === topicId)[0]
    //       .value,
    //     nodes: [
    //       ...finalTopicNodes.filter((p) => p.id !== topicId),
    //       ...conceptNodes,
    //     ],
    //     similarities: [
    //       ...adjustedConceptSims,
    //       ...topicSimilarities,
    //       ...addedConceptSims,
    //     ],
    //   };
    // }
    //
    // return {
    //   selectedTopic: topic.name,
    //   nodes: [
    //     ...finalTopicNodes.filter((p) => p.id !== topicId),
    //     ...conceptNodes.filter((p) => p.id !== conceptId),
    //   ],
    //   similarities: [
    //     ...conceptSimilarities,
    //     ...topicSimilarities,
    //     ...addedConceptSims,
    //   ],
    // };
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
        .having((t) => gt(t.count, minCount))
        .limit(150);

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
            gt(t.value, 2.0),
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
