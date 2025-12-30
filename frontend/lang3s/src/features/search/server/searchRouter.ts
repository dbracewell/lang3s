import { db } from "@/lib/db";
import { TextAnnotationTable } from "@/lib/db/schema";
import { t3env } from "@/lib/t3env";
import { logAndRethrow, tryCatch } from "@/lib/utils/try-catch";
import { SearchParamSchema } from "@/features/search/params";
import {
  annotationSearch,
  documentSearch,
} from "@/features/search/server/searchStrategies";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { eq } from "drizzle-orm";
import { SearchResults } from "@/features/search/types";

export const SearchRouter = createTRPCRouter({
  search: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const { q, aid, atype, cursor, stype, isStrict } = input;

      let embedding: number[] | undefined = undefined;
      let finalQuery: string = "";
      let finalPage: number = Math.max(1, cursor ?? 1);
      let finalAnnotationType = stype === "sentence" ? "sentence" : atype;
      let finalIsStrict: boolean = isStrict ?? true;

      if (!!aid?.trim()) {
        const [annotation] = await logAndRethrow(() =>
          db
            .select({
              embedding: TextAnnotationTable.embedding,
              text: TextAnnotationTable.content,
            })
            .from(TextAnnotationTable)
            .where(eq(TextAnnotationTable.id, aid)),
        );
        if (!annotation) {
          return {
            type: "annotation",
            total: 0,
            results: [],
            entities: [],
            nextCursor: undefined,
          } as SearchResults;
        }
        if (annotation.embedding) {
          embedding = annotation.embedding;
        }
        finalQuery = annotation.text;
      } else if (!!q?.trim()) {
        finalQuery = q.trim();
        const { data: res, isError } = await tryCatch(
          fetch(`${t3env.EMBEDDING_SERVER}/embed`, {
            method: "POST",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              text: finalQuery,
            }),
          }),
        );
        if (!isError && res.ok) {
          embedding = (await res.json()) as number[];
        }
      } else {
        return {
          type: "sentence",
          total: 0,
          results: [],
          entities: [],
          nextCursor: undefined,
        } as SearchResults;
      }

      const hasCase =
        finalQuery.toLowerCase() !== finalQuery &&
        finalQuery.toUpperCase() !== finalQuery;

      if (stype === "document") {
        return await documentSearch({
          embedding,
          threshold: !!aid?.trim() || hasCase ? 0.25 : 0.2,
          query: finalQuery,
          isStrict: finalIsStrict,
          page: finalPage,
        });
      }

      return await annotationSearch({
        embedding,
        threshold: !!aid?.trim() || hasCase ? 0.6 : 0.5,
        query: finalQuery,
        annotationType: finalAnnotationType as string,
        isStrict: finalIsStrict,
        page: finalPage,
      });
    }),
});
