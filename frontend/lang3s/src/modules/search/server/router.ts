import { db } from "@/db";
import { TextAnnotationTable } from "@/db/schema";
import {
  fullTextDocumentSearch,
  semanticAnnotationSearch,
  fullTextAnnotationSearch,
  semanticDocumentSearch,
} from "@/modules/search/server/searchStrategies";
import { QueryTypes } from "@/modules/search/types";
import { SearchParamSchema } from "@/modules/search/utils/parse-params";
import { baseProcedure, createTRPCRouter } from "@/trpc/init";
import { eq } from "drizzle-orm";
import z from "zod";

export const SearchRouter = createTRPCRouter({
  search: baseProcedure.input(SearchParamSchema).query(async ({ input }) => {
    const {
      query,
      annotationId,
      annotationType,
      page,
      queryType,
      minSimilarity,
      semanticSearch,
      lang,
    } = input;

    let embedding: number[] = [];
    let finalQuery: string = "";
    let finalPage: number = Math.max(0, page);
    let isSemantic = !!semanticSearch;
    let finalAnnotationType =
      queryType === "sentence" ? "sentence" : annotationType;

    if (!!annotationId?.trim()) {
      const [annotation] = await db
        .select()
        .from(TextAnnotationTable)
        .where(eq(TextAnnotationTable.id, annotationId));
      if (!annotation) {
        return [];
      }
      isSemantic = true;
      embedding = annotation.embedding;
      finalQuery = annotation.text;
    } else if (!!query?.trim()) {
      finalQuery = query.trim();
      if (isSemantic) {
        const res = await fetch("http://localhost:8003/embed", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text: finalQuery,
            language: lang ?? "",
          }),
        });
        if (!res.ok) {
          return [];
        }
        embedding = await res.json();
      }
    } else {
      return [];
    }

    if (isSemantic) {
      if (queryType === "document") {
        return await semanticDocumentSearch(
          embedding,
          finalPage,
          minSimilarity,
        );
      } else {
        return semanticAnnotationSearch(
          embedding,
          finalAnnotationType ?? "entity",
          finalPage,
          minSimilarity,
        );
      }
    } else {
      if (queryType === "document") {
        return await fullTextDocumentSearch(finalQuery, finalPage);
      }
      return await fullTextAnnotationSearch(
        finalQuery,
        finalAnnotationType ?? "entity",
        page,
      );
    }
  }),
});
