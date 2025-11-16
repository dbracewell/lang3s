import { db } from "@/db";
import { DocumentsTable, TextAnnotationTable, TextTable } from "@/db/schema";
import { logAndRethrow } from "@/lib/try-catch";
import { PAGE_LIMIT } from "@/features/common/constants";
import { SearchResults } from "@/features/search/types";
import { and, asc, countDistinct, desc, eq, gte, ne, sql } from "drizzle-orm";
import "server-only";

export const fullTextAnnotationSearch = async (
  query: string,
  annotationType: string,
  page: number,
) => {
  const sub = db
    .select({
      documentId: TextAnnotationTable.documentId,
      similarity: sql`pgroonga_score(tableoid,ctid)`.as("rank"),
      highlight: sql<string>`array_to_string(
					pgroonga_snippet_html (
										${TextAnnotationTable.text},
										 pgroonga_query_extract_keywords(${query})
										 ), ' ... ')`.as("highlight"),
      start: TextAnnotationTable.start,
    })
    .from(TextAnnotationTable)
    .where(
      and(
        eq(TextAnnotationTable.type, annotationType),
        sql`${TextAnnotationTable.text} &@~  (${query}, 
																ARRAY[1],
 																ARRAY['scorer_tf_idf($index)'],
 																'ml_text_search_index')::pgroonga_full_text_search_condition_with_scorers`,
      ),
    )
    .as("snippets");

  const offset = Math.min(0, (page - 1) * PAGE_LIMIT);
  const [total, results] = await logAndRethrow(
    Promise.all([
      db
        .select({ count: countDistinct(DocumentsTable.id) })
        .from(DocumentsTable)
        .innerJoin(sub, eq(DocumentsTable.id, sub.documentId)),
      db
        .select({
          documentTitle: DocumentsTable.title,
          documentId: sub.documentId,
          rank: sql<number>`sum(${sub.similarity})`.as("rank"),
          highlights: sql<{ similarity: number; text: string }[]>`json_arrayagg(
						json_build_object('similarity', ${sub.similarity},
						                  'text', ${sub.highlight})
															order by ${sub.similarity} desc
				)`,
        })
        .from(sub)
        .innerJoin(DocumentsTable, eq(sub.documentId, DocumentsTable.id))
        .groupBy((t) => [t.documentId, t.documentTitle])
        .orderBy((t) => [desc(t.rank), asc(t.documentId)])
        .limit(PAGE_LIMIT + 1)
        .offset(offset),
    ]),
  );

  const hasNextPage = results.length > PAGE_LIMIT;
  const finalResults = hasNextPage
    ? results.slice(0, results.length - 1)
    : results;

  return {
    type: "text",
    total: total[0].count,
    results: finalResults,
    nextCursor: hasNextPage ? Math.min(page, 1) + 1 : undefined,
  } as SearchResults;
};

export const fullTextDocumentSearch = async (query: string, page: number) => {
  const sub = await db
    .select({
      documentId: TextTable.documentId,
      similarity: sql<number>`pgroonga_score(tableoid,ctid)`.as("rank"),
      highlight:
        sql<string>`array_to_string(pgroonga_snippet_html (${TextTable.text},
										 pgroonga_query_extract_keywords(${query})), '\n')`.as("highlight"),
    })
    .from(TextTable)
    .where(
      (t) =>
        sql`${TextTable.text} &@~  (${query}, 
																ARRAY[1],
 																ARRAY['scorer_tf_idf($index)'],
 																'ml_text_search_index')::pgroonga_full_text_search_condition_with_scorers`,
    )
    .as("sub");

  const offset = Math.min(0, (page - 1) * PAGE_LIMIT);
  const [total, results] = await logAndRethrow(
    Promise.all([
      db
        .select({ count: countDistinct(DocumentsTable.id) })
        .from(DocumentsTable)
        .innerJoin(sub, eq(DocumentsTable.id, sub.documentId)),
      db
        .select({
          documentTitle: DocumentsTable.title,
          documentId: sub.documentId,
          rank: sub.similarity,
          highlights: sql<{ similarity: number; text: string }[]>`json_arrayagg(
						json_build_object('similarity', ${sub.similarity},
						                  'text', ${sub.highlight})
															order by ${sub.similarity} desc
				)`,
        })
        .from(sub)
        .innerJoin(DocumentsTable, eq(sub.documentId, DocumentsTable.id))
        .orderBy((t) => [desc(t.rank), asc(t.documentId)])
        .groupBy((t) => [t.documentId, t.documentTitle, t.rank])
        .limit(PAGE_LIMIT + 1)
        .offset(offset),
    ]),
  );

  const hasNextPage = results.length > PAGE_LIMIT;
  const finalResults = hasNextPage
    ? results.slice(0, results.length - 1)
    : results;

  return {
    type: "text",
    total: total[0].count,
    results: finalResults,
    nextCursor: hasNextPage ? Math.min(page, 1) + 1 : undefined,
  } as SearchResults;
};

export const semanticAnnotationSearch = async (
  embedding: string,
  annotationType: string,
  page: number,
  minSimilarity: number,
) => {
  const sim = db
    .select({
      documentId: TextAnnotationTable.documentId,
      text: TextAnnotationTable.text,
      annotationType: TextAnnotationTable.type,
      embedding: TextAnnotationTable.embedding,
      similarity:
        sql<number>`(1 - (embedding <~> ${embedding})::float / 768)`.as(
          "similarity",
        ),
    })
    .from(TextAnnotationTable)
    .as("sim_search");

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: sql<{ similarity: number; text: string }[]>`
			json_arrayagg( 
					json_build_object('similarity', ${sim.similarity}, 
														'text', ${sim.text}) 
														order by ${sim.similarity} desc)`.as("highlight"),
      rank: sql<number>`max(${sim.similarity})`.as("rank"),
    })
    .from(DocumentsTable)
    .innerJoin(sim, eq(DocumentsTable.id, sim.documentId))
    .where(
      and(
        ne(sim.similarity, NaN),
        gte(sim.similarity, minSimilarity),
        eq(sim.annotationType, annotationType),
      ),
    )
    .groupBy((t) => [t.documentTitle, t.documentId])
    .as("sub");

  const offset = Math.min(0, (page - 1) * PAGE_LIMIT);
  const [total, results] = await logAndRethrow(
    Promise.all([
      db.select({ count: countDistinct(sub.documentId) }).from(sub),
      db
        .select()
        .from(sub)
        .orderBy((t) => [desc(t.rank), asc(t.documentId)])
        .limit(PAGE_LIMIT + 1)
        .offset(offset),
    ]),
  );

  const hasNextPage = results.length > PAGE_LIMIT;
  const finalResults = hasNextPage
    ? results.slice(0, results.length - 1)
    : results;

  return {
    type: "vector",
    total: total[0].count,
    results: finalResults,
    nextCursor: hasNextPage ? Math.min(page, 1) + 1 : undefined,
  } as SearchResults;
};

export const semanticDocumentSearch = async (
  embedding: string,
  page: number,
  minSimilarity: number,
) => {
  const sim = db
    .select({
      documentId: TextTable.documentId,
      text: sql<string>`SUBSTRING(${TextTable.text},0,512) || '...'`.as(
        "text2",
      ),
      embedding: TextTable.embedding,
      similarity:
        sql<number>`(1 - (embedding <~> ${embedding})::float / 768)`.as(
          "similarity",
        ),
    })
    .from(TextTable)
    .as("sim_search");

  const sub = db
    .select({
      documentTitle: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlights: sql<{ similarity: number; text: string }[]>`
			json_arrayagg( 
					json_build_object('similarity', ${sim.similarity}, 
														'text', ${sim.text})
														order by ${sim.similarity} desc)`.as("highlight"),
      rank: sql<number>`max(${sim.similarity})`.as("rank"),
    })
    .from(DocumentsTable)
    .innerJoin(sim, eq(DocumentsTable.id, sim.documentId))
    .where(and(ne(sim.similarity, NaN), gte(sim.similarity, minSimilarity)))
    .groupBy((t) => [t.documentTitle, t.documentId])
    .as("sub");

  const offset = Math.min(0, (page - 1) * PAGE_LIMIT);
  const [total, results] = await logAndRethrow(
    Promise.all([
      db.select({ count: countDistinct(sub.documentId) }).from(sub),
      db
        .select()
        .from(sub)
        .orderBy((t) => [desc(t.rank), asc(t.documentId)])
        .limit(PAGE_LIMIT + 1)
        .offset(offset),
    ]),
  );

  const hasNextPage = results.length > PAGE_LIMIT;
  const finalResults = hasNextPage
    ? results.slice(0, results.length - 1)
    : results;

  return {
    type: "vector",
    total: total[0].count,
    results: finalResults,
    nextCursor: hasNextPage ? Math.min(page, 1) + 1 : undefined,
  } as SearchResults;
};
