import "server-only";
import { db } from "@/lib/db";
import {
  AnnotationWithOntologyView,
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
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
  or,
  SQL,
  sql,
  SQLWrapper,
} from "drizzle-orm";

import {
  cosineSimilarity,
  generateNextPage,
  jsonValue,
  orderAsc,
  withPagination,
} from "@/lib/db/funcs";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";
import { Annotations } from "@/lib/db/annotations";
import {
  AnnotationSearchResult,
  DocumentSearchResult,
  SearchResults,
  TopicSearchResult,
} from "@/features/search/types";
import { getMetadataBySourceAndName } from "@/features/common/server/queries";

export type SearchParams = {
  embedding?: number[];
  threshold: number;
  page: number;
  query?: string;
  isStrict: boolean;
};

type QueryWithMetadata = {
  query?: string;
  metadata?: { name: string; value: string }[];
};

const METADATA_REGEX = /meta:(\S+?)\s*=\s*("[^"]+"|\S+)/g;

const parseQuery = (query?: string): QueryWithMetadata => {
  if (!query) {
    return {};
  }
  const metadata: { name: string; value: string }[] = [];
  for (const m of query.matchAll(METADATA_REGEX)) {
    metadata.push({ name: m[1], value: m[2] });
  }

  let finalQuery = query;
  if (metadata) {
    finalQuery = query.replaceAll(METADATA_REGEX, "").trim();
  }

  return {
    query: finalQuery ?? undefined,
    metadata: metadata ?? undefined,
  };
};

const loosenQuery = (query?: string) => {
  if (query != null) {
    const parts = query.match(/("[^"]+"|\w+)/g) ?? [];
    return parts
      .map((p) => (p.startsWith('"') ? p : p === "OR" ? "" : p))
      .join(" OR ");
  }
  return undefined;
};

const prepareMetadataQuery = async (
  metadata?: { name: string; value: string }[],
) => {
  if (metadata) {
    const definedMetadata = await getMetadataBySourceAndName(
      "document",
      metadata.map((m) => m.name),
    );
    const ored = metadata
      .map((m) => {
        const md = definedMetadata.find(
          (df) => df.name.toLowerCase() === m.name.toLowerCase(),
        );

        if (md == null) {
          return null;
        }
        if (md.dataType === "string[]") {
          return sql`${DocumentsTable.metadata}->${m.name} ? ${m.value}` as SQLWrapper;
        }
        return sql`${jsonValue(DocumentsTable.metadata, m.name, md.dataType)} = ${m.value}` as SQLWrapper;
      })
      .filter((v) => v != null);
    return or(...ored);
  }
  return undefined;
};

const createUnionQuery = ({
  embedding,
  finalQuery,
  semanticSearch,
  fullTextSearch,
}: {
  embedding?: number[];
  finalQuery?: string;
  semanticSearch: any;
  fullTextSearch: any;
}) => {
  if (embedding && !!finalQuery) {
    return fullTextSearch.unionAll(semanticSearch).as(randomAlphaUnderscore());
  } else if (embedding != null) {
    return semanticSearch.as(randomAlphaUnderscore());
  } else if (!!finalQuery) {
    return fullTextSearch.as(randomAlphaUnderscore());
  }
  return db
    .select({
      documentId: TextTable.documentId,
      text: sql<string>`SUBSTRING(${TextTable.content},0,512)`.as("text"),
      itemRank: sql<number>`1`.as("item_rank"),
      scoreRank: sql<number>`1`.as("score_rank"),
      priority: sql<number>`2`.as("priority"),
    })
    .from(TextTable)
    .as(randomAlphaUnderscore());
};

export const docSearch = async ({
  embedding,
  threshold,
  page,
  query,
  isStrict,
}: SearchParams) => {
  let { query: finalQuery, metadata } = parseQuery(query);
  finalQuery = isStrict ? finalQuery : loosenQuery(finalQuery);

  const fullTextSearch = db
    .select({
      documentId: TextTable.documentId,
      text: sql<string>`${TextTable.content}`.as("text"),
      itemRank: Annotations.fullTextRank.as("item_rank"),
      scoreRank: Annotations.fullTextRank.as("score_rank"),
      priority: sql<number>`2`.as("priority"),
    })
    .from(TextTable)
    .where(Annotations.getFullTextMatch(finalQuery ?? "", TextTable.content));

  const similarityExpr = cosineSimilarity(
    TextAnnotationTable.embedding,
    embedding!,
  );

  const semanticSearch = db
    .select({
      documentId: TextAnnotationTable.documentId,
      text: sql<string>`array_to_string(
      array_agg(${TextAnnotationTable.content} order by ${TextAnnotationTable.sentenceId}),
      '...\n'
    )`.as("text"),
      itemRank:
        sql<number>`dense_rank() over (order by max(${similarityExpr}) desc)`.as(
          "item_rank",
        ),
      scoreRank:
        sql<number>`dense_rank() over (order by max(${similarityExpr}) desc)`.as(
          "score_rank",
        ),
      priority: sql<number>`1`.as("priority"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        Annotations.isSentence,
        gte(similarityExpr, threshold),
      ),
    )
    .groupBy(TextAnnotationTable.documentId);

  const fromTable = createUnionQuery({
    embedding,
    finalQuery,
    semanticSearch,
    fullTextSearch,
  });

  const uniqueRows = db
    .select({
      documentId: fromTable.documentId,
      text: sql<string>`
            CASE
              WHEN LENGTH(${Annotations.getFullTextSnippet(
                finalQuery ?? "",
                fromTable.text,
              )}) > 0  THEN ${Annotations.getFullTextSnippet(
                finalQuery ?? "",
                fromTable.text,
              )}
                ELSE CONCAT(SUBSTRING(${fromTable.text},0,512),'...')
            END
        `.as(randomAlphaUnderscore()),
      itemRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.itemRank}))`.as(
        randomAlphaUnderscore(),
      ),
      scoreRank: sql<number>`SUM(1.0 / (60.0 + ${fromTable.scoreRank}))`.as(
        randomAlphaUnderscore(),
      ),
    })
    .from(fromTable)
    .groupBy((t) => [t.documentId, t.text])
    .as("unique_rows");

  const documentWhere: SQL[] = [];
  if (isStrict && !!finalQuery) {
    documentWhere.push(
      sql`LENGTH(${Annotations.getFullTextSnippet(finalQuery, uniqueRows.text)}) > 0`,
    );
  }
  const mdQuery = await prepareMetadataQuery(metadata);
  if (mdQuery != null) {
    documentWhere.push(mdQuery);
  }

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: jsonAgg(
        jsonBuildObject({
          text: uniqueRows.text,
          rank: uniqueRows.itemRank,
        }),
        orderAsc(sql`${uniqueRows.itemRank}`),
      ).as(randomAlphaUnderscore()),
      rank: sql<number>`SUM(${uniqueRows.scoreRank})`.as("rank"),
    })
    .from(uniqueRows)
    .innerJoin(DocumentsTable, eq(DocumentsTable.id, uniqueRows.documentId))
    .where(and(...documentWhere))
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
  let { query: finalQuery, metadata } = parseQuery(query);
  finalQuery = isStrict ? query : loosenQuery(finalQuery);

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
        Annotations.getFullTextMatch(
          finalQuery ?? "",
          TextAnnotationTable.content,
        ),
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

  const fromTable = createUnionQuery({
    embedding,
    finalQuery,
    semanticSearch,
    fullTextSearch,
  });

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

  const documentWhere: SQL[] = [];
  if (isStrict && !!finalQuery) {
    documentWhere.push(
      sql`LENGTH(${Annotations.getFullTextSnippet(finalQuery, uniqueRows.sentence)}) > 0`,
    );
  }
  const mdQuery = await prepareMetadataQuery(metadata);
  if (mdQuery != null) {
    documentWhere.push(mdQuery);
  }

  const sub = db
    .select({
      id: uniqueRows.id,
      name: uniqueRows.name,
      highlights: jsonAgg(
        jsonBuildObject({
          documentId: uniqueRows.documentId,
          sentence: !!finalQuery
            ? sql<string>`
              CASE
                 WHEN LENGTH(${Annotations.getFullTextSnippet(
                   finalQuery ?? "",
                   uniqueRows.sentence,
                 )}) > 0  THEN ${Annotations.getFullTextSnippet(
                   finalQuery ?? "",
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
    .where(and(...documentWhere))
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
  const { query: finalQuery, metadata } = parseQuery(query); //isStrict ? query : loosenQuery(query);

  const sentenceSearch = Annotations.getFullTextSearchSentences(
    finalQuery ?? "",
  ).as(randomAlphaUnderscore());

  const fullTextSearch = db
    .select({
      path: AnnotationWithOntologyView.path,
      itemRank: sql<number>`${sentenceSearch.rank}`.as("item_rank"),
      scoreRank: sql<number>`${sentenceSearch.rank}`.as("score_rank"),
      documentId: AnnotationWithOntologyView.documentId,
      id: AnnotationWithOntologyView.id,
      embedding: AnnotationWithOntologyView.embedding,
      content: AnnotationWithOntologyView.normalized,
      a0: AnnotationWithOntologyView.a0Text,
      a1: AnnotationWithOntologyView.a1Text,
      time: AnnotationWithOntologyView.timeText,
      location: AnnotationWithOntologyView.locText,
    })
    .from(AnnotationWithOntologyView)
    .innerJoin(
      sentenceSearch,
      eq(sentenceSearch.sentenceAid, AnnotationWithOntologyView.sentenceAid),
    );

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
    }),
  }).where((t) => gte(cosineSimilarity(t.embedding, embedding!), threshold));

  const fromTable = createUnionQuery({
    embedding,
    finalQuery,
    semanticSearch,
    fullTextSearch,
  });

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

  const documentWhere: SQL[] = [];
  if (isStrict && !!finalQuery) {
    documentWhere.push(
      sql`LENGTH(${Annotations.getFullTextSnippet(finalQuery, uniqueRows.text)}) > 0`,
    );
  }
  const mdQuery = await prepareMetadataQuery(metadata);
  if (mdQuery != null) {
    documentWhere.push(mdQuery);
  }

  const sub = db
    .select({
      text: !!finalQuery
        ? sql<string>`
              CASE
                 WHEN LENGTH(${Annotations.getFullTextSnippet(
                   finalQuery,
                   uniqueRows.text,
                 )}) > 0  THEN ${Annotations.getFullTextSnippet(
                   finalQuery,
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
    .where(and(...documentWhere))
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
