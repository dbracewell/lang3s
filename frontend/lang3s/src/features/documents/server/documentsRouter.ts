import { db } from "@/lib/db";
import {
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
} from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { TRPCError } from "@trpc/server";
import { asc, count, eq, sql } from "drizzle-orm";
import z from "zod";
import { promises as fs } from "fs";
import path from "path";
import { DocumentSchema } from "@/features/common/schemas";
import { t3env } from "@/lib/t3env";
import * as zlib from "node:zlib";
import { generateNextPage, withPagination } from "@/lib/db/funcs";
import { OntologyMappings } from "@/lib/db/annotations";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { DEFAULT_ONTOLOGY_COLOR } from "@/features/common/constants";

export const DocumentsRouter = createTRPCRouter({
  getMany: protectedProcedure
    .input(
      z.object({
        cursor: z.number().optional(),
      }),
    )
    .query(async ({ input }) => {
      const { cursor } = input;
      const page = Math.max(1, cursor ?? 1);

      const [totalDocs, docs] = await logAndRethrow(async () => {
        return await Promise.all([
          page === 1
            ? db
                .select({ count: count(DocumentsTable.id) })
                .from(DocumentsTable)
            : undefined,
          withPagination(
            db
              .select({
                id: DocumentsTable.id,
                title: DocumentsTable.title,
                text: sql<string>`SUBSTRING(${TextTable.content},0,512) || '...'`.as(
                  "text",
                ),
              })
              .from(DocumentsTable)
              .innerJoin(TextTable, eq(DocumentsTable.id, TextTable.documentId))
              .orderBy((t) => asc(t.id)),
            { page },
          ),
        ]);
      });

      const { hasNextPage, finalResults } = generateNextPage(docs);
      return {
        nextCursor: hasNextPage ? page + 1 : undefined,
        totalDocs: totalDocs?.[0].count || 0,
        posts: finalResults,
      };
    }),

  getOne: protectedProcedure
    .input(z.object({ id: z.string().min(1) }))
    .query(async ({ input }) => {
      const filePath = path.join(t3env.DOCUMENTS_DIR, `${input.id}.json.gz`);
      try {
        const jsonData = zlib
          .gunzipSync(await fs.readFile(filePath))
          .toString("utf-8");
        const document = DocumentSchema.parse(JSON.parse(jsonData));

        const ontologyMapping = OntologyMappings.getOntologyMappings().as(
          randomAlphaUnderscore(),
        );

        const annotationIdMapping = await db
          .select({
            id: TextAnnotationTable.id,
            value: ontologyMapping.path,
            color: ontologyMapping.color,
          })
          .from(TextAnnotationTable)
          .innerJoin(
            ontologyMapping,
            eq(TextAnnotationTable.mapping, ontologyMapping.mapping),
          )
          .where(eq(TextAnnotationTable.documentId, document.id));

        return {
          ...document,
          text: {
            ...document.text,
            embedding: undefined,
            annotations: document.text.annotations.map((a) => ({
              ...a,
              embedding: undefined,
              value:
                annotationIdMapping.find((m) => a.id == m.id)?.value ?? a.value,
              color:
                annotationIdMapping.find((m) => a.id == m.id)?.color ??
                DEFAULT_ONTOLOGY_COLOR,
            })),
          },
        };
      } catch (e) {
        console.error(e);
        throw new TRPCError({ code: "NOT_FOUND" });
      }
    }),
});
