import "server-only";
import { db } from "@/lib/db";
import {
  DocumentsTable,
  TextAnnotationTable,
  TopicSentences,
  TopicsTable,
} from "@/lib/db/schema";
import {
  and,
  asc,
  count,
  countDistinct,
  desc,
  eq,
  gte,
  sql,
} from "drizzle-orm";

import {
  cosineSimilarity,
  generateNextPage,
  orderAsc,
  upper,
  withPagination,
} from "@/lib/db/funcs";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";
import { Annotations, OntologyMappings } from "@/lib/db/annotations";
import {
  AnnotationSearchResult,
  DocumentSearchResult,
  SearchResults,
  TopicSearchResult,
} from "@/features/search/types";

export type SearchParams = {
  embedding?: number[];
  threshold: number;
  page: number;
  query?: string;
  isStrict: boolean;
};

export const docSearch = async ({
  embedding,
  threshold,
  page,
  query,
  isStrict,
}: SearchParams) => {
  const fullTextSearch = db
    .select({
      documentId: TextAnnotationTable.documentId,
      sentenceAid: TextAnnotationTable.sentenceAid,
      text: sql<string>`${TextAnnotationTable.content}`.as("text"),
      itemRank: Annotations.fullTextRank.as("item_rank"),
      scoreRank: Annotations.fullTextRank.as("score_rank"),
      priority: sql<number>`2`.as("priority"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isSentence,
        Annotations.getFullTextMatch(query ?? "", TextAnnotationTable.content),
      ),
    );

  const semanticSearch = db
    .select({
      documentId: TextAnnotationTable.documentId,
      sentenceAid: TextAnnotationTable.sentenceAid,
      text: sql<string>`${TextAnnotationTable.content}`.as("text"),
      itemRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("item_rank"),
      scoreRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("score_rank"),
      priority: sql<number>`1`.as("priority"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isSentence,
        gte(
          cosineSimilarity(TextAnnotationTable.embedding, embedding!),
          threshold,
        ),
      ),
    );

  let fromTable;
  if (embedding == null) {
    fromTable = fullTextSearch.as(randomAlphaUnderscore());
  } else if (!!query) {
    fromTable = fullTextSearch
      .unionAll(semanticSearch)
      .as(randomAlphaUnderscore());
  } else {
    fromTable = semanticSearch.as(randomAlphaUnderscore());
  }

  const uniqueRows = db
    .select({
      documentId: fromTable.documentId,
      sentenceAid: fromTable.sentenceAid,
      text: fromTable.text,
      itemRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.itemRank}))`.as(
        randomAlphaUnderscore(),
      ),
      scoreRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.scoreRank}))`.as(
        randomAlphaUnderscore(),
      ),
    })
    .from(fromTable)
    .groupBy((t) => [t.documentId, t.sentenceAid, t.text])
    .as("unique_rows");

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: jsonAgg(
        jsonBuildObject({
          text: !!query
            ? sql<string>`
              CASE
                 WHEN LENGTH(${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.text,
                 )}) > 0  THEN ${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.text,
                 )}
                ELSE ${uniqueRows.text}
             END`
            : sql<string>`${uniqueRows.text}`,
          rank: uniqueRows.itemRank,
        }),
        orderAsc(sql`${uniqueRows.itemRank}`),
      ).as(randomAlphaUnderscore()),
      rank: sql<number>`SUM(${uniqueRows.scoreRank})`.as("rank"),
    })
    .from(uniqueRows)
    .innerJoin(DocumentsTable, eq(DocumentsTable.id, uniqueRows.documentId))
    .where((t) =>
      isStrict && !!query
        ? sql`LENGTH(${Annotations.getFullTextSnippet(query, uniqueRows.text)}) > 0`
        : undefined,
    )
    .groupBy((t) => [t.documentId, t.documentTitle])
    .orderBy((t) => [desc(t.rank), asc(t.documentId)]);

  let results;
  let total;
  if (page <= 1) {
    const c = sub.as(randomAlphaUnderscore());
    [results, total] = await Promise.all([
      withPagination(sub, { page }),
      db.select({ count: countDistinct(c.documentId) }).from(c),
    ]);
  } else {
    results = await withPagination(sub, { page });
  }
  const { finalResults, hasNextPage } = generateNextPage(results);

  return {
    nextCursor: hasNextPage ? page + 1 : undefined,
    results: finalResults,
    total: total ? total[0].count : 0,
  } as SearchResults<DocumentSearchResult>;
};

export const topicSearch = async ({
  isStrict,
  query,
  embedding,
  threshold,
  page,
}: SearchParams) => {
  const fullTextSearchNoTopics = db
    .select({
      documentId: TextAnnotationTable.documentId,
      sentenceAid: TextAnnotationTable.sentenceAid,
      text: sql<string>`${TextAnnotationTable.content}`.as("text"),
      itemRank: Annotations.fullTextRank.as("item_rank"),
      scoreRank: Annotations.fullTextRank.as("score_rank"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isSentence,
        Annotations.getFullTextMatch(query ?? "", TextAnnotationTable.content),
      ),
    )
    .as(randomAlphaUnderscore());

  const topicSentences = db
    .select({
      id: TopicsTable.id,
      name: TopicsTable.name,
      sentenceAid: TopicSentences.sentenceAid,
    })
    .from(TopicSentences)
    .innerJoin(TopicsTable, eq(TopicsTable.id, TopicSentences.topicId));

  const ftTopics = topicSentences.as(randomAlphaUnderscore());

  const fullTextSearch = db
    .select({
      id: sql<string>`${ftTopics.id}`.as("id"),
      name: sql<string>`${ftTopics.name}`.as("name"),
      documentId: fullTextSearchNoTopics.documentId,
      sentenceAid: fullTextSearchNoTopics.sentenceAid,
      text: sql<string>`${fullTextSearchNoTopics.text}`.as("text"),
      itemRank: sql<number>`${fullTextSearchNoTopics.itemRank}`.as("item_rank"),
      scoreRank: sql<number>`${fullTextSearchNoTopics.scoreRank}`.as(
        "score_rank",
      ),
      priority: sql<number>`2`.as("priority"),
    })
    .from(fullTextSearchNoTopics)
    .innerJoin(
      ftTopics,
      eq(ftTopics.sentenceAid, fullTextSearchNoTopics.sentenceAid),
    );

  const semanticSearchNoTopics = db
    .select({
      documentId: TextAnnotationTable.documentId,
      sentenceAid: TextAnnotationTable.sentenceAid,
      text: sql<string>`${TextAnnotationTable.content}`.as("text"),
      itemRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("item_rank"),
      scoreRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("score_rank"),
      priority: sql<number>`1`.as("priority"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isSentence,
        gte(
          cosineSimilarity(TextAnnotationTable.embedding, embedding!),
          threshold,
        ),
      ),
    )
    .as(randomAlphaUnderscore());

  const semanticTopics = topicSentences.as(randomAlphaUnderscore());

  const semanticSearch = db
    .select({
      id: sql<string>`${semanticTopics.id}`.as("id"),
      name: sql<string>`${semanticTopics.name}`.as("name"),
      documentId: semanticSearchNoTopics.documentId,
      sentenceAid: semanticSearchNoTopics.sentenceAid,
      text: sql<string>`${semanticSearchNoTopics.text}`.as("text"),
      itemRank: sql<number>`${semanticSearchNoTopics.itemRank}`.as("item_rank"),
      scoreRank: sql<number>`${semanticSearchNoTopics.scoreRank}`.as(
        "score_rank",
      ),
      priority: sql<number>`1`.as("priority"),
    })
    .from(semanticSearchNoTopics)
    .innerJoin(
      semanticTopics,
      eq(semanticTopics.sentenceAid, semanticSearchNoTopics.sentenceAid),
    );

  let fromTable;
  if (embedding == null) {
    fromTable = fullTextSearch.as(randomAlphaUnderscore());
  } else if (!!query) {
    fromTable = fullTextSearch
      .unionAll(semanticSearch)
      .as(randomAlphaUnderscore());
  } else {
    fromTable = semanticSearch.as(randomAlphaUnderscore());
  }

  const uniqueRows = db
    .select({
      documentId: fromTable.documentId,
      sentenceAid: fromTable.sentenceAid,
      sentence: fromTable.text,
      itemRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.itemRank}))`.as(
        randomAlphaUnderscore(),
      ),
      scoreRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.scoreRank}))`.as(
        randomAlphaUnderscore(),
      ),
      id: fromTable.id,
      name: fromTable.name,
    })
    .from(fromTable)
    .groupBy((t) => [t.documentId, t.sentence, t.sentenceAid, t.id, t.name])
    .as("unique_rows");

  const sub = db
    .select({
      id: uniqueRows.id,
      name: uniqueRows.name,
      highlights: jsonAgg(
        jsonBuildObject({
          documentId: uniqueRows.documentId,
          sentence: !!query
            ? sql<string>`
              CASE
                 WHEN LENGTH(${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.sentence,
                 )}) > 0  THEN ${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.sentence,
                 )}
                ELSE ${uniqueRows.sentence}
             END`
            : sql<string>`${uniqueRows.sentence}`,
          sentenceAid: uniqueRows.sentenceAid,
          rank: uniqueRows.itemRank,
        }),
        orderAsc(sql`${uniqueRows.itemRank}`),
      ).as(randomAlphaUnderscore()),
      rank: sql<number>`SUM(${uniqueRows.scoreRank})`.as("rank"),
    })
    .from(uniqueRows)
    .where((t) =>
      isStrict && !!query
        ? sql`LENGTH(${Annotations.getFullTextSnippet(query, uniqueRows.sentence)}) > 0`
        : undefined,
    )
    .groupBy((t) => [t.id, t.name])
    .orderBy((t) => [desc(t.rank), asc(t.name), asc(t.id)]);

  let results;
  let total;
  if (page <= 1) {
    [results, total] = await Promise.all([
      withPagination(sub, { page }),
      db.select({ count: count() }).from(sub.as(randomAlphaUnderscore())),
    ]);
  } else {
    results = await withPagination(sub, { page });
  }

  const { finalResults, hasNextPage } = generateNextPage(results);

  return {
    nextCursor: hasNextPage ? page + 1 : undefined,
    results: finalResults,
    total: total ? total[0].count : 0,
  } as SearchResults<TopicSearchResult>;
};

export const annotationSearch = async ({
  isStrict,
  query,
  embedding,
  threshold,
  page,
}: SearchParams) => {
  const o = OntologyMappings.getOntologyMappings().as(randomAlphaUnderscore());

  const interMediate = db
    .select({
      content: upper(TextAnnotationTable.content).as("content"),
      itemRank: Annotations.fullTextRank.as("item_rank"),
      scoreRank: Annotations.fullTextRank.as("score_rank"),
      priority: sql<number>`2`.as("priority"),
      documentId: TextAnnotationTable.documentId,
      mapping: TextAnnotationTable.mapping,
      id: TextAnnotationTable.id,
      embedding: TextAnnotationTable.embedding,
      ...Annotations.eventArgs,
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isNotStopword,
        sql`${TextAnnotationTable.content} &@~  (${query})`,
      ),
    )
    .as(randomAlphaUnderscore());

  const fullTextSearch = db
    .select({
      path: sql<string>`${o.path}`.as("path"),
      itemRank: interMediate.itemRank,
      scoreRank: interMediate.scoreRank,
      priority: sql<number>`2`.as("priority"),
      documentId: interMediate.documentId,
      id: interMediate.id,
      embedding: interMediate.embedding,
      content: interMediate.content,
      a0: interMediate.a0,
      a1: interMediate.a1,
      time: interMediate.time,
      location: interMediate.location,
    })
    .from(interMediate)
    .innerJoin(o, eq(interMediate.mapping, o.mapping));

  const semanticSearch = Annotations.getAnnotationsWithOntology({
    options: { normalize: true, includeEventArgs: true },
    annotationFields: ["documentId", "id", "embedding"],
    computedColumns: (o) => ({
      path: sql<string>`${o.path}`.as("path"),
      itemRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("item_rank"),
      scoreRank: Annotations.getSemanticRank(
        TextAnnotationTable.embedding,
        embedding!,
      ).as("score_rank"),
      priority: sql<number>`1`.as("priority"),
    }),
  }).where((t) => gte(cosineSimilarity(t.embedding, embedding!), threshold));

  let fromTable;
  if (embedding == null) {
    fromTable = fullTextSearch.as(randomAlphaUnderscore());
  } else if (!!query) {
    fromTable = fullTextSearch
      .unionAll(semanticSearch)
      .as(randomAlphaUnderscore());
  } else {
    fromTable = semanticSearch.as(randomAlphaUnderscore());
  }

  const uniqueRows = db
    .select({
      documentId: fromTable.documentId,
      annotationId: fromTable.id,
      text: fromTable.content,
      value: fromTable.path,
      a0: fromTable.a0,
      a1: fromTable.a1,
      time: fromTable.time,
      location: fromTable.location,
      itemRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.itemRank}))`.as(
        randomAlphaUnderscore(),
      ),
      scoreRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.scoreRank}))`.as(
        randomAlphaUnderscore(),
      ),
    })
    .from(fromTable)
    .groupBy((t) => [
      t.documentId,
      t.annotationId,
      t.text,
      t.value,
      t.a0,
      t.a1,
      t.time,
      t.location,
    ])
    .as("unique_rows");

  const sub = db
    .select({
      text: !!query
        ? sql<string>`
              CASE
                 WHEN LENGTH(${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.text,
                 )}) > 0  THEN ${Annotations.getFullTextSnippet(
                   query,
                   uniqueRows.text,
                 )}
                ELSE ${uniqueRows.text}
             END`
        : sql<string>`${uniqueRows.text}`,
      value: uniqueRows.value,
      a0: uniqueRows.a0,
      a1: uniqueRows.a1,
      time: uniqueRows.time,
      location: uniqueRows.location,
      highlights: jsonAgg(
        jsonBuildObject({
          documentTitle: DocumentsTable.title,
          documentId: DocumentsTable.id,
          annotationId: uniqueRows.annotationId,
          rank: uniqueRows.itemRank,
        }),
        orderAsc(sql`${uniqueRows.itemRank}`),
      ).as(randomAlphaUnderscore()),
      rank: sql<number>`SUM(${uniqueRows.scoreRank})`.as("rank"),
    })
    .from(uniqueRows)
    .innerJoin(DocumentsTable, eq(DocumentsTable.id, uniqueRows.documentId))
    .where((t) =>
      isStrict && !!query
        ? sql`LENGTH(${Annotations.getFullTextSnippet(query, uniqueRows.text)}) > 0`
        : undefined,
    )
    .groupBy((t) => [uniqueRows.text, t.value, t.a0, t.a1, t.time, t.location])
    .orderBy((t) => [desc(t.rank), asc(t.text), asc(t.value)]);

  let results;
  let total;
  if (page <= 1) {
    [results, total] = await Promise.all([
      withPagination(sub, { page }),
      db.select({ count: count() }).from(sub.as(randomAlphaUnderscore())),
    ]);
  } else {
    results = await withPagination(sub, { page });
  }

  const { finalResults, hasNextPage } = generateNextPage(results);

  return {
    nextCursor: hasNextPage ? page + 1 : undefined,
    results: finalResults,
    total: total ? total[0].count : 0,
  } as SearchResults<AnnotationSearchResult>;
};
