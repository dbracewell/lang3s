import { db } from "@/db";
import { DocumentsTable, TextAnnotationTable, TextTable } from "@/db/schema";
import { logAndRethrow } from "@/lib/try-catch";
import {
  and,
  asc,
  cosineDistance,
  desc,
  eq,
  gte,
  max,
  ne,
  sql,
} from "drizzle-orm";
import "server-only";

export const fullTextAnnotationSearch = async (
  query: string,
  annotationType: string,
  page: number,
) => {
  const sub = db
    .select({
      documentId: TextAnnotationTable.documentId,
      rank: sql`pgroonga_score(tableoid,ctid)`.as("rank"),
      highlight:
        sql<string>`array_to_string(pgroonga_snippet_html (${TextAnnotationTable.text},
										 pgroonga_query_extract_keywords(${query})), '\n')`.as("highlight"),
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
    .orderBy((t) => [desc(t.rank), asc(t.documentId)])
    .as("sub");

  const results = await logAndRethrow(
    db
      .select({
        title: DocumentsTable.title,
        documentId: sub.documentId,
        rank: sql<number>`sum(${sub.rank})`.as("rank"),
        highlight:
          sql<string>`STRING_AGG(${sub.highlight}::text, '\n' order by ${sub.start} asc )`.as(
            "highlight",
          ),
      })
      .from(sub)
      .innerJoin(DocumentsTable, eq(sub.documentId, DocumentsTable.id))
      .groupBy((t) => [t.documentId, t.title])
      .orderBy((t) => [desc(t.rank), asc(t.documentId)]),
  );

  return results;
};

export const fullTextDocumentSearch = async (query: string, page: number) => {
  const sub = await db
    .select({
      documentId: TextTable.documentId,
      rank: sql<number>`pgroonga_score(tableoid,ctid)`.as("rank"),
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

  const results = await logAndRethrow(
    db
      .select({
        title: DocumentsTable.title,
        documentId: sub.documentId,
        rank: sub.rank,
        highlight: sub.highlight,
      })
      .from(sub)
      .innerJoin(DocumentsTable, eq(sub.documentId, DocumentsTable.id))
      .orderBy((t) => [desc(t.rank), asc(t.documentId)]),
  );

  return results;
};

export const semanticAnnotationSearch = async (
  embedding: number[],
  annotationType: string,
  page: number,
  minSimilarity: number,
) => {
  const similarity = sql<number>`1 - (${cosineDistance(
    TextAnnotationTable.embedding,
    embedding,
  )})`;

  const sub = db
    .selectDistinct({
      title: DocumentsTable.title,
      documentId: DocumentsTable.id,
      highlight:
        annotationType === "sentence"
          ? sql<string>`string_agg( round(CAST(${similarity}as numeric),2) || '&nbsp;&nbsp;&nbsp;' || ${TextAnnotationTable.text} , '\n' order by ${similarity} desc)`.as(
              "highlight",
            )
          : sql<string>`string_agg(round(CAST(${similarity}as numeric),2) || '&nbsp;&nbsp;&nbsp;' ||'<b>' || ${TextAnnotationTable.text} || '</b> (' || ${TextAnnotationTable.value}  || ')', '\n' order by ${similarity} desc)`.as(
              "highlight",
            ),
      rank: sql<number>`max(${similarity})`.as("rank"),
    })
    .from(TextAnnotationTable)
    .innerJoin(
      DocumentsTable,
      eq(TextAnnotationTable.documentId, DocumentsTable.id),
    )
    .where(
      and(
        ne(similarity, NaN),
        gte(similarity, minSimilarity),
        eq(TextAnnotationTable.type, annotationType),
      ),
    )
    .groupBy((t) => [t.documentId, t.title])
    .as("sub");

  const results = await logAndRethrow(
    db
      .select()
      .from(sub)
      .orderBy((t) => [desc(t.rank), asc(t.documentId)])
      .limit(50),
  );
  return results;
};

export const semanticDocumentSearch = async (
  embedding: number[],
  page: number,
  minSimilarity: number,
) => {
  const similarity = sql<number>`1 - (${cosineDistance(
    TextTable.embedding,
    embedding,
  )})`;

  const results = logAndRethrow(
    db
      .select({
        title: DocumentsTable.title,
        documentId: DocumentsTable.id,
        highlight: sql<string>`SUBSTRING(${TextTable.text},0,512)`.as(
          "highlight",
        ),
        rank: similarity.as("rank"),
      })
      .from(TextTable)
      .innerJoin(DocumentsTable, eq(TextTable.documentId, DocumentsTable.id))
      .where(and(ne(similarity, NaN), gte(similarity, minSimilarity)))
      .orderBy((t) => [desc(t.rank), asc(t.documentId)]),
  );

  return results;
};
