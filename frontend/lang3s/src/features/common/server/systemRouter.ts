import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { logAndRethrow } from "@/lib/utils/try-catch";
import {
  AnnotationToOntology,
  DocumentsTable,
  MetadataTable,
  OntologyTable,
  TextAnnotationTable,
} from "@/lib/db/schema";
import { db } from "@/lib/db";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { and, eq, isNotNull, ne, sql } from "drizzle-orm";
import { MetadataSchema } from "@/features/common/schemas";
import { roleHasPermissions } from "@/features/auth/permissions";
import { TRPCError } from "@trpc/server";
import { getMetadata } from "@/features/common/server/queries";
import z from "zod";

const formatableDataTypes = new Set(["float", "date", "datetime"]);

export const systemRouter = createTRPCRouter({
  getPossibleMetadata: protectedProcedure.query(async () => {
    const existingMetadata = new Set(
      (
        await logAndRethrow(() =>
          db
            .select({ source: MetadataTable.source, key: MetadataTable.name })
            .from(MetadataTable),
        )
      ).map((s) => `${s.source}-${s.key}`),
    );
    const allMetadata = db
      .selectDistinct({
        source: sql<string>`${"document"}`.as(randomAlphaUnderscore()),
        key: sql<string>`jsonb_object_keys(${DocumentsTable.metadata})`.as(
          randomAlphaUnderscore(),
        ),
      })
      .from(DocumentsTable)
      .unionAll(
        db
          .selectDistinct({
            source: sql<string>`${"sentence"}`.as(randomAlphaUnderscore()),
            key: sql<string>`jsonb_object_keys(${TextAnnotationTable.metadata})`.as(
              randomAlphaUnderscore(),
            ),
          })
          .from(TextAnnotationTable)
          .where(eq(TextAnnotationTable.type, "sentence")),
      )
      .unionAll(
        db
          .selectDistinct({
            source: sql<string>`${"annotation"}`.as(randomAlphaUnderscore()),
            key: sql<string>`jsonb_object_keys(${TextAnnotationTable.metadata})`.as(
              randomAlphaUnderscore(),
            ),
          })
          .from(TextAnnotationTable)
          .where(ne(TextAnnotationTable.type, "sentence")),
      );
    return (await allMetadata).filter(
      (row) => !existingMetadata.has(`${row.source}-${row.key}`),
    );
  }),

  getMetadata: protectedProcedure.query(async () => {
    return await logAndRethrow(() => getMetadata());
  }),

  getAnnotationTypeValueWithMapping: protectedProcedure.query(async () => {
    const mappings = db
      .select({
        path: OntologyTable.path,
        annotation: AnnotationToOntology.annotation,
      })
      .from(AnnotationToOntology)
      .innerJoin(
        OntologyTable,
        eq(OntologyTable.id, AnnotationToOntology.ontologyId),
      )
      .as(randomAlphaUnderscore());

    const results = await logAndRethrow(() =>
      db
        .selectDistinct({
          path: mappings.path,
          mapping: TextAnnotationTable.mapping,
        })
        .from(TextAnnotationTable)
        .leftJoin(
          mappings,
          eq(mappings.annotation, TextAnnotationTable.mapping),
        )
        .where(
          and(
            ne(TextAnnotationTable.type, "sentence"),
            isNotNull(TextAnnotationTable.mapping),
          ),
        )
        .orderBy(TextAnnotationTable.mapping),
    );

    return Object.fromEntries(
      results.map((r) => [r.mapping, r.path]),
    ) as Record<string, string | null>;
  }),

  updateMetadata: protectedProcedure
    .input(
      z.object({
        id: z.uuid(),
        values: MetadataSchema,
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const { user } = ctx;
      if (!roleHasPermissions(user.role, ["model:create", "data:load"])) {
        throw new TRPCError({ code: "UNAUTHORIZED" });
      }

      return await logAndRethrow(() =>
        db
          .update(MetadataTable)
          .set({
            ...input.values,
            formatter: formatableDataTypes.has(input.values.dataType)
              ? input.values.formatter
              : null,
          })
          .where(eq(MetadataTable.id, input.id))
          .returning(),
      );
    }),

  createMetadata: protectedProcedure
    .input(MetadataSchema)
    .mutation(async ({ input, ctx }) => {
      const { user } = ctx;
      if (!roleHasPermissions(user.role, ["model:create", "data:load"])) {
        throw new TRPCError({ code: "UNAUTHORIZED" });
      }

      return await logAndRethrow(() =>
        db
          .insert(MetadataTable)
          .values({
            ...input,
            formatter: formatableDataTypes.has(input.dataType)
              ? input.formatter
              : null,
          })
          .returning(),
      );
    }),
});
