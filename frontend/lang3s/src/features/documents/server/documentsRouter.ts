import { db } from "@/lib/db";
import {
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
  TopicDocuments,
  TopicsTable,
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
import { generateNextPage, withPagination } from "@/lib/db/funcs";
import { Annotations, OntologyMappings } from "@/lib/db/annotations";
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
        const entities = db
          .select({
            ...Annotations.getColumns({
              options: {
                normalize: true,
              },
              fields: ["documentId"],
            }),
            count: count().as("count"),
          })
          .from(TextAnnotationTable)
          .where(eq(TextAnnotationTable.type, "entity"))
          .groupBy((t) => [t.content, t.documentId])
          .orderBy((t) => [desc(t.count), asc(t.content)])
          .as("entities");

        const sub = db
          .select({
            documentId: entities.documentId,
            entities: sql<string[]>`ARRAY_AGG(${entities.content} || 
                     ' (<b>' || ${entities.count} || '</b>)' )`.as(
              "entity_array",
            ),
          })
          .from(entities)
          .groupBy(entities.documentId)
          .as("sub");

        const topics = db
          .select({
            textId: TopicDocuments.textId,
            topic: sql<
              string[]
            >`ARRAY_AGG(${TopicsTable.name} order by ${TopicDocuments.score} desc)`.as(
              randomAlphaUnderscore(),
            ),
          })
          .from(TopicsTable)
          .innerJoin(TopicDocuments, eq(TopicDocuments.topicId, TopicsTable.id))
          .groupBy((t) => [t.textId])
          .as(randomAlphaUnderscore());

        return Promise.all([
          db.select({ count: count(DocumentsTable.id) }).from(DocumentsTable),
          withPagination(
            db
              .select({
                id: DocumentsTable.id,
                title: DocumentsTable.title,
                metadata: DocumentsTable.metadata,
                topics: topics.topic,
                text: sql<string>`SUBSTRING(${TextTable.content},0,512) || '...'`.as(
                  "text",
                ),
                entities: sub.entities,
              })
              .from(DocumentsTable)
              .innerJoin(TextTable, eq(DocumentsTable.id, TextTable.documentId))
              .leftJoin(topics, eq(TextTable.id, topics.textId))
              .innerJoin(sub, eq(DocumentsTable.id, sub.documentId))
              .orderBy((t) => asc(t.id)),
            { page: cursor },
          ),
        ]);
      });

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
        console.log(e);
        throw new TRPCError({ code: "NOT_FOUND" });
      }
    }),
});
