import { db } from "@/db";
import { DocumentsTable, TextAnnotationTable, TextTable } from "@/db/schema";
import { logAndRethrow } from "@/lib/try-catch";
import {
  TextAnnotationDB,
  TextAnnotationProps,
} from "@/modules/common/classes";
import { PAGE_LIMIT } from "@/modules/common/constants";
import {
  getAnnotationsInSentence,
  notOverlaps,
} from "@/modules/documents/server/subqueries";
import { createTRPCRouter, protectedProcedure } from "@/trpc/init";
import { TRPCError } from "@trpc/server";
import {
  and,
  asc,
  count,
  desc,
  eq,
  getTableColumns,
  lt,
  ne,
  sql,
} from "drizzle-orm";
import z from "zod";
import { promises as fs } from "fs";
import path from "path"; // For path manipulation
import { DocumentSchema } from "@/modules/common/schemas";
import { env } from "@/env/env";

export const DocumentsRouter = createTRPCRouter({
  getMany: protectedProcedure
    .input(
      z.object({
        cursor: z.number().optional(),
      }),
    )
    .query(async ({ input }) => {
      const { cursor } = input;
      let offset = Math.max(cursor ?? 0, 0);

      const totalDocs = await logAndRethrow(
        db.select({ count: count(DocumentsTable.id) }).from(DocumentsTable),
      );

      const entities = db
        .select({
          textId: TextAnnotationTable.textId,
          entity: sql<string>`lower(${TextAnnotationTable.text})`.as(
            "entity_text",
          ),
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

      const docs = await logAndRethrow(
        db
          .select({
            id: DocumentsTable.id,
            title: DocumentsTable.title,
            metadata: DocumentsTable.metadata,
            text: sql<string>`SUBSTRING(${TextTable.text},0,512) || '...'`.as(
              "text",
            ),
            entities: sub.entities,
          })
          .from(DocumentsTable)
          .leftJoin(TextTable, eq(DocumentsTable.id, TextTable.documentId))
          .innerJoin(sub, eq(TextTable.id, sub.textId))
          .offset(offset * PAGE_LIMIT)
          .limit(PAGE_LIMIT + 1)
          .orderBy((t) => asc(t.id)),
      );

      const hasNext = docs.length > PAGE_LIMIT;
      const finalDocs = hasNext ? docs.slice(0, docs.length - 1) : docs;
      return {
        nextCursor: hasNext ? offset + 1 : undefined,
        totalDocs: totalDocs,
        posts: finalDocs,
      };
    }),

  getOne: protectedProcedure
    .input(z.object({ id: z.string().min(1) }))
    .query(async ({ input }) => {
      const filePath = path.join(env.DOCUMENTS_DIR, `${input.id}.json`);
      try {
        const jsonData = await fs.readFile(filePath, "utf8");
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

  test: protectedProcedure
    .input(
      z.object({
        type1: z.string(),
        type2: z.string(),
      }),
    )
    .query(async ({ input }) => {
      const q1 = getAnnotationsInSentence({
        annotationType: input.type1,
        textConversion: "upper",
      }).as("q1");
      const q2 = getAnnotationsInSentence({
        annotationType: input.type2,
        textConversion: "upper",
      }).as("q2");
      return await db
        .select({
          e1: q1.text,
          e1Type: q1.value,
          e2: q2.text,
          e2Type: q2.value,
          count: count(),
        })
        .from(q1)
        .innerJoin(
          q2,
          and(
            eq(q2.sentenceId, q1.sentenceId),
            ne(q1.annotationId, q2.annotationId),
            ne(q1.text, q2.text),
            input.type1 !== input.type2 ? notOverlaps(q1, q2) : undefined,
            input.type1 === input.type2 ? lt(q1.text, q2.text) : undefined,
          ),
        )
        .groupBy((t) => [t.e1, t.e2, t.e1Type, t.e2Type])
        .orderBy((t) => [desc(t.count)])
        .limit(100);
    }),
});
