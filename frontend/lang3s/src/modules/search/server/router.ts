import { db } from "@/db";
import { TextAnnotationTable } from "@/db/schema";
import { env } from "@/env/env";
import { logAndRethrow } from "@/lib/try-catch";
import { SearchParamSchema } from "@/modules/search/params";
import {
  fullTextAnnotationSearch,
  fullTextDocumentSearch,
  semanticAnnotationSearch,
  semanticDocumentSearch,
} from "@/modules/search/server/searchStrategies";
import { createTRPCRouter, protectedProcedure } from "@/trpc/init";
import { eq } from "drizzle-orm";

export const SearchRouter = createTRPCRouter({
  search: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const { q, aid, atype, page, stype, minSimilarity, semantic } = input;

      let embedding: string = "";
      let finalQuery: string = "";
      let finalPage: number = Math.max(1, page ?? 1);
      let isSemantic = !!semantic;
      let finalAnnotationType = stype === "sentence" ? "sentence" : atype;

      if (!!aid?.trim()) {
        const [annotation] = await logAndRethrow(
          db
            .select({
              embedding: TextAnnotationTable.embedding,
              text: TextAnnotationTable.text,
            })
            .from(TextAnnotationTable)
            .where(eq(TextAnnotationTable.id, aid)),
        );
        if (!annotation) {
          return [];
        }
        isSemantic = true;
        if (annotation.embedding) {
          embedding = annotation.embedding;
        }
        finalQuery = annotation.text;
      } else if (!!q?.trim()) {
        finalQuery = q.trim();
        if (isSemantic) {
          const res = await fetch(`${env.EMBEDDING_SERVER}/embed`, {
            method: "POST",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              text: finalQuery,
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
        if (stype === "document") {
          return await semanticDocumentSearch(
            embedding,
            finalPage,
            minSimilarity ?? 0.6,
          );
        } else {
          return semanticAnnotationSearch(
            embedding,
            finalAnnotationType ?? "entity",
            finalPage,
            minSimilarity ?? 0.6,
          );
        }
      } else {
        if (stype === "document") {
          return await fullTextDocumentSearch(finalQuery, finalPage);
        }
        return await fullTextAnnotationSearch(
          finalQuery,
          finalAnnotationType ?? "entity",
          finalPage,
        );
      }
    }),
});
