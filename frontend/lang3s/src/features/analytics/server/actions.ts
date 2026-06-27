"use server";
import { inngest } from "@/lib/inngest/client";
import { BasicUserInfo } from "@/features/common/types";

export const updateAnalytics = async (user: BasicUserInfo) => {
  await inngest.send({
    name: "analytics/update",
    data: {
      userId: user.id,
    },
  });
  return { code: 200 };
};

// getCorpusMap: protectedProcedure.query(async () => {
//     const [rawNodes, similarities] = await logAndRethrow(() => {
//       const nodes = db.select().from(DocumentTopicConcepts);
//
//       const s1 = aliasedTable(TopicsTable, "s1");
//       const s2 = aliasedTable(TopicsTable, "s2");
//       const similarity = sql<number>`1 - (${s1.embedding}::halfvec <=> ${s2.embedding}::halfvec)::float`;
//       const topicSimilarities = db
//         .select({
//           id1: s1.id,
//           id2: s2.id,
//           type: sql<string>`${"topic"}`.as("type"),
//           similarity: similarity,
//         })
//         .from(s1)
//         .innerJoin(s2, gt(s1.id, s2.id))
//         .where((t) => gte(t.similarity, 0.7));
//
//       const totalDocuments = db
//         .select({ count: count().as("count") })
//         .from(DocumentsTable)
//         .as(randomAlphaUnderscore());
//
//       const conceptSimilarities = db
//         .select({
//           id1: ConceptCoOccurrence.source,
//           id2: ConceptCoOccurrence.target,
//           type: sql<string>`${"concept"}`.as("type"),
//           similarity: sql<number>`
//               CASE
//                WHEN ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float)) > 0.5
//                THEN 1 + ln((${count()}::float * ${totalDocuments.count}::float) / (${ConceptCoOccurrence.sourceCount}::float * ${ConceptCoOccurrence.targetCount}::float))
//                ELSE 0.25
//               END
//               `,
//         })
//         .from(ConceptCoOccurrence)
//         .innerJoin(totalDocuments, sql`1=1`)
//         .groupBy((t) => [
//           t.id1,
//           t.id2,
//           ConceptCoOccurrence.sourceCount,
//           ConceptCoOccurrence.targetCount,
//           totalDocuments.count,
//         ]);
//
//       const allSims = topicSimilarities.unionAll(conceptSimilarities);
//
//       return Promise.all([nodes, allSims]);
//     });
//
//     interface CustomPoint extends ForceGraphPoint {
//       type: "topic" | "concept" | "entity";
//       subvalues: Record<string, number>;
//     }
//
//     const nodes: Record<string, CustomPoint> = {};
//     for (let row of rawNodes) {
//       if (!(row.topicId in nodes)) {
//         nodes[row.topicId] = {
//           id: row.topicId,
//           type: "topic",
//           text: row.topic,
//           display: truncateText(row.topic),
//           value: row.topicCount,
//           subvalues: {},
//         };
//       }
//       if ((row.overlap as number) <= 5) {
//         continue;
//       }
//
//       nodes[row.topicId].subvalues[row.concept] = row.overlap;
//
//       if (!(row.concept in nodes)) {
//         nodes[row.concept] = {
//           id: row.concept,
//           type: "concept",
//           text: row.concept,
//           display: truncateText(row.concept),
//           value: row.conceptCount,
//           subvalues: row.instances,
//         };
//       }
//     }
//
//     const maxConceptSim = Math.max(
//       ...similarities
//         .filter((s) => s.type === "concept")
//         .map((s) => s.similarity),
//     );
//     const minConceptSim = Math.min(
//       ...similarities
//         .filter((s) => s.type === "concept")
//         .map((s) => s.similarity),
//     );
//
//     return {
//       nodes: Object.values(nodes),
//       similarities: similarities.map((s) => {
//         if (s.type === "topic") {
//           return s;
//         }
//         return {
//           ...s,
//           similarity:
//             (s.similarity - minConceptSim) *
//             (1 / (maxConceptSim - minConceptSim)),
//         };
//       }),
//     };

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
// }
