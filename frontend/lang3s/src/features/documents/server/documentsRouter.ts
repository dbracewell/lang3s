import { db } from "@/lib/db";
import {
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
} from "@/lib/db/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { TRPCError } from "@trpc/server";
import { asc, count, desc, eq, sql } from "drizzle-orm";
import z from "zod";
import { promises as fs } from "fs";
import path from "path";
import { DocumentSchema } from "@/features/common/schemas";
import { env } from "@/lib/env/env";
import * as zlib from "node:zlib";
import {
  coalesce,
  generateNextPage,
  jsonValue,
  lower,
  withPagination,
} from "@/lib/db/funcs";

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

      const entities = db
        .select({
          textId: TextAnnotationTable.textId,
          entity: lower(
            coalesce(
              jsonValue(TextAnnotationTable.metadata, "coref_text"),
              TextAnnotationTable.content,
            ),
          ).as("entity"),
          count: count(TextAnnotationTable.id).as("count"),
        })
        .from(TextAnnotationTable)
        .where(eq(TextAnnotationTable.type, "entity"))
        .groupBy((t) => [t.textId, t.entity])
        .orderBy((t) => [desc(t.count), asc(t.entity)])
        .as("entities");

      const sub = db
        .select({
          textId: entities.textId,
          entities: sql<string[]>`ARRAY_AGG(${entities.entity} || 
                     ' (<b>' || ${entities.count} || '</b>)' )`.as(
            "entity_array",
          ),
        })
        .from(entities)
        .groupBy(entities.textId)
        .as("sub");

      const [totalDocs, docs] = await logAndRethrow(() =>
        Promise.all([
          db.select({ count: count(DocumentsTable.id) }).from(DocumentsTable),
          withPagination(
            db
              .select({
                id: DocumentsTable.id,
                title: DocumentsTable.title,
                metadata: DocumentsTable.metadata,
                text: sql<string>`SUBSTRING(${TextTable.content},0,512) || '...'`.as(
                  "text",
                ),
                entities: sub.entities,
              })
              .from(DocumentsTable)
              .leftJoin(TextTable, eq(DocumentsTable.id, TextTable.documentId))
              .innerJoin(sub, eq(TextTable.id, sub.textId))
              .orderBy((t) => asc(t.id)),
            { page: cursor },
          ),
        ]),
      );

      const { hasNextPage, finalResults } = generateNextPage(docs);
      return {
        nextCursor: hasNextPage ? page + 1 : undefined,
        totalDocs: totalDocs,
        posts: finalResults,
      };
    }),

  getOne: protectedProcedure
    .input(z.object({ id: z.string().min(1) }))
    .query(async ({ input }) => {
      const filePath = path.join(env.DOCUMENTS_DIR, `${input.id}.json.gz`);
      try {
        const jsonData = zlib
          .gunzipSync(await fs.readFile(filePath))
          .toString("utf-8");
        const document = DocumentSchema.parse(JSON.parse(jsonData));
        return {
          ...document,
          text: {
            ...document.text,
            embedding: undefined,
            annotations: document.text.annotations.map((a) => ({
              ...a,
              embedding: undefined,
            })),
          },
        };
      } catch {
        throw new TRPCError({ code: "NOT_FOUND" });
      }
    }),
});
