import "server-only";
import { db } from "@/lib/db";
import {
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
} from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { SearchResults } from "@/features/search/types";
import {
  and,
  asc,
  countDistinct,
  desc,
  eq,
  gte,
  isNull,
  or,
  sql,
} from "drizzle-orm";

import {
  cosineSimilarity,
  generateNextPage,
  jsonAgg,
  jsonBuildObject,
  orderDesc,
  withPagination,
} from "@/lib/db/funcs";

export const createPaginatedSearchResults = async ({
  sub,
  page,
  searchType,
}: {
  sub: any; // Because of Drizzle typing problems
  page: number;
  searchType: string;
}) => {
  const [total, results, entities] = await logAndRethrow(() =>
    Promise.all([
      db.select({ count: countDistinct(sub.documentId) }).from(sub),
      withPagination(
        db
          .select()
          .from(sub)
          .orderBy((t) => [desc(t.rank), asc(t.documentId)]),
        { page },
      ),
      db
        .select({
          entity: sql<string>`LOWER(COALESCE(${TextAnnotationTable.metadata}->>'coref_text', ${TextAnnotationTable.content}))`,
          count: countDistinct(TextAnnotationTable.documentId),
        })
        .from(TextAnnotationTable)
        .innerJoin(sub, eq(TextAnnotationTable.documentId, sub.documentId))
        .where(eq(TextAnnotationTable.type, "entity"))
        .groupBy((t) => [t.entity])
        .orderBy((t) => [desc(t.count), asc(t.entity)])
        .having((t) => gte(t.count, 2)),
    ]),
  );

  const { hasNextPage, finalResults } = generateNextPage(results);
  return {
    type: searchType,
    total: total[0].count,
    results: finalResults,
    entities: entities,
    nextCursor: hasNextPage ? Math.max(page, 1) + 1 : undefined,
  } as SearchResults;
};

export const annotationSearch = async ({
  query,
  embedding,
  threshold,
  annotationType,
  isStrict,
  page,
}: {
  query: string;
  threshold: number;
  embedding?: number[];
  annotationType: string;
  isStrict: boolean;
  page: number;
}) => {
  const strictSearch = db
    .select({
      documentId: TextAnnotationTable.documentId,
      text: sql<string>`COALESCE(${TextAnnotationTable.metadata}->>'coref_text',
      ${TextAnnotationTable.content})`.as("strict_text"),
      a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
      a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
      time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
        "TIME",
      ),
      location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
        "LOCATION",
      ),
      itemId: TextAnnotationTable.id,
      rawScore: sql<number>`1`.as("rawScore"),
      rank: sql<number>`ROW_NUMBER() OVER (ORDER BY pgroonga_score(tableoid,ctid) DESC)`.as(
        "strict_rank",
      ),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        sql`${TextAnnotationTable.content} &@~  (${query})`,
        eq(TextAnnotationTable.type, annotationType),
        or(
          isNull(sql`${TextAnnotationTable.metadata}->>'is_stopword'`),
          eq(sql`${TextAnnotationTable.metadata}->>'is_stopword'`, "false"),
        ),
      ),
    );

  const semanticSearch = db
    .select({
      documentId: TextAnnotationTable.documentId,
      text: sql<string>`COALESCE(${TextAnnotationTable.metadata}->>'coref_text',
      ${TextAnnotationTable.content})`.as("semantic_text"),
      a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as(
        "semantic_A0",
      ),
      a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as(
        "semantic_A1",
      ),
      time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
        "semantic_TIME",
      ),
      location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
        "semantic_LOCATION",
      ),
      itemId: TextAnnotationTable.id,
      rawScore:
        sql<number>`1 - (embedding <=> ${JSON.stringify(embedding)})`.as(
          "rawScore",
        ),
      rank: sql<number>`ROW_NUMBER() OVER (ORDER BY embedding <=> ${JSON.stringify(embedding)})`.as(
        "semantic_rank",
      ),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        gte(
          cosineSimilarity(TextAnnotationTable.embedding, embedding ?? []),
          threshold,
        ),
        eq(TextAnnotationTable.type, annotationType),
        or(
          isNull(sql`${TextAnnotationTable.metadata}->>'is_stopword'`),
          eq(sql`${TextAnnotationTable.metadata}->>'is_stopword'`, "false"),
        ),
      ),
    )
    .offset(0);

  let rankedSearch;
  if (embedding == null) {
    const aliased = strictSearch.as("aliased");
    rankedSearch = db
      .select({
        documentId: aliased.documentId,
        rank: sql<number>`1.0 / (60.0 + ${aliased.rank}) + 1.0 / (60.0 + ${aliased.rank})`.as(
          "rank",
        ),
        text: aliased.text,
        a1: aliased.a1,
        a0: aliased.a0,
        time: aliased.time,
        location: aliased.location,
      })
      .from(aliased)
      .as("rankedSearch");
  } else {
    const aliased = strictSearch.as("aliased");
    const union = isStrict
      ? db
          .select()
          .from(aliased)
          .where(
            sql`array_to_string(pgroonga_snippet_html (${aliased.text},
    								 pgroonga_query_extract_keywords(${query})), '\n') != ''`,
          )
          .as("union_q2")
      : db
          .select()
          .from(semanticSearch.unionAll(strictSearch).as("union_q"))
          .as("union");

    rankedSearch = db
      .select({
        documentId: union.documentId,
        text: sql<string>`
            CASE
            WHEN array_to_string(pgroonga_snippet_html (${union.text},
    								 pgroonga_query_extract_keywords(${query})), '\n') = '' THEN SUBSTRING(${union.text},0,512)
            ELSE array_to_string(pgroonga_snippet_html (${union.text},
    								 pgroonga_query_extract_keywords(${query})), '\n')
            END
        `.as("highlight"),
        a1: union.a1,
        a0: union.a0,
        time: union.time,
        location: union.location,
        rank: sql<number>`SUM(1.0 / (60.0 + ${union.rank}))`.as("rank"),
      })
      .from(union)
      .where(
        isStrict
          ? sql`array_to_string(pgroonga_snippet_html (${union.text},
    								 pgroonga_query_extract_keywords(${query})), '\n') != ''`
          : undefined,
      )
      .groupBy(
        union.documentId,
        union.text,
        union.a1,
        union.a0,
        union.time,
        union.location,
        union.itemId,
      )
      .as("rankedSearch");
  }

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: jsonAgg(
        jsonBuildObject({
          rank: rankedSearch.rank,
          text: rankedSearch.text,
          a1: rankedSearch.a1,
          a0: rankedSearch.a0,
          time: rankedSearch.time,
          location: rankedSearch.location,
        }),
        orderDesc(sql`${rankedSearch.rank}`),
      ).as("highlight"),
      rank: sql<number>`sum(${rankedSearch.rank})`.as("rank"),
    })
    .from(DocumentsTable)
    .innerJoin(rankedSearch, eq(DocumentsTable.id, rankedSearch.documentId))
    .groupBy((t) => [t.documentTitle, t.documentId])
    .as("sub");

  return await createPaginatedSearchResults({
    sub,
    page,
    searchType: annotationType === "sentence" ? "sentence" : "annotation",
  });
};

export const documentSearch = async ({
  query,
  embedding,
  threshold,
  isStrict,
  page,
}: {
  query: string;
  embedding?: number[];
  threshold: number;
  isStrict: boolean;
  page: number;
}) => {
  const strictSearch = db
    .select({
      documentId: TextTable.documentId,
      text: TextTable.content,
      rank: sql<number>`ROW_NUMBER() OVER (ORDER BY pgroonga_score(tableoid,ctid) DESC)`.as(
        "strict_rank",
      ),
    })
    .from(TextTable)
    .where((t) => sql`${TextTable.content} &@~  (${query})`);

  const semanticSearch = db
    .select({
      documentId: TextTable.documentId,
      text: TextTable.content,
      rank: sql<number>`ROW_NUMBER() OVER (ORDER BY embedding <=> ${JSON.stringify(embedding)})`.as(
        "seamntic_rank",
      ),
    })
    .from(TextTable)
    .where(
      gte(cosineSimilarity(TextTable.embedding, embedding ?? []), threshold),
    )
    .offset(0);

  let rankedSearch;

  if (embedding == null) {
    const aliased = strictSearch.as("aliased");
    rankedSearch = db
      .select({
        documentId: aliased.documentId,
        text: sql<string>`array_to_string(pgroonga_snippet_html (${aliased.text},
										 pgroonga_query_extract_keywords(${query})), '\n')`.as("highlight"),
        rank: sql<number>`1.0 / (60.0 + ${aliased.rank})`.as("rank"),
      })
      .from(aliased)
      .as("rankedSearch");
  } else {
    const aliased = strictSearch.as("aliased");
    const union = isStrict
      ? db
          .select()
          .from(aliased)
          .where(
            sql`array_to_string(pgroonga_snippet_html (${aliased.text},
    								 pgroonga_query_extract_keywords(${query})), '\n') != ''`,
          )
          .as("union_q2")
      : db
          .select()
          .from(semanticSearch.unionAll(strictSearch).as("union_q"))
          .as("union");

    rankedSearch = db
      .select({
        documentId: union.documentId,
        text: sql<string>`
            CASE
            WHEN array_to_string(pgroonga_snippet_html (${union.text},
    								 pgroonga_query_extract_keywords(${query})), '\n') = '' THEN SUBSTRING(${union.text},0,512)
            ELSE array_to_string(pgroonga_snippet_html (${union.text},
    								 pgroonga_query_extract_keywords(${query})), '\n')
            END
        `.as("highlight"),
        rank: sql<number>`SUM(1.0 / (60.0 + ${union.rank}))`.as("rrf_score"),
      })
      .from(union)
      .groupBy((t) => [t.documentId, union.text])
      .as("rankedSearch");
  }

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: jsonAgg(
        jsonBuildObject({
          rank: rankedSearch.rank,
          text: rankedSearch.text,
        }),
        orderDesc(sql`${rankedSearch.rank}`),
      ).as("highlight"),
      rank: sql<number>`sum(${rankedSearch.rank})`.as("rank"),
    })
    .from(DocumentsTable)
    .innerJoin(rankedSearch, eq(DocumentsTable.id, rankedSearch.documentId))
    .groupBy((t) => [t.documentTitle, t.documentId])
    .as("sub");

  return await createPaginatedSearchResults({
    sub,
    page,
    searchType: "document",
  });
};
