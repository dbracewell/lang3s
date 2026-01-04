import { db } from "@/lib/db";
import {
  AnnotationToOntology,
  OntologyProperties,
  OntologyPropertySchema,
  OntologyTable,
} from "@/lib/db/schema";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { and, asc, eq, getTableColumns, ne, sql } from "drizzle-orm";
import z from "zod";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { AnnotationColors } from "@/features/common/constants";
import { TRPCError } from "@trpc/server";
import { OntologyConceptSchema } from "@/features/ontology/schemas";
import { jsonAgg, jsonBuildObject, jsonStrictAgg } from "@/lib/db/helpers/json";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { requirePermissions } from "@/features/auth/server/actions";

export const ontologyRouter = createTRPCRouter({
  conceptNameExists: protectedProcedure
    .input(z.object({ name: z.string() }))
    .query(async ({ input }) => {
      return (
        (
          await logAndRethrow(() =>
            db
              .select()
              .from(OntologyTable)
              .where(eq(OntologyTable.name, input.name)),
          )
        ).length > 0
      );
    }),

  deleteConcept: protectedProcedure
    .input(z.object({ path: z.string() }))
    .mutation(async ({ input, ctx }) => {
      const { user } = ctx;
      const { path } = input;

      await requirePermissions(user, undefined, [
        "model:create",
        "data:load",
        "data:update",
      ]);

      const [result] = await logAndRethrow(() =>
        db
          .delete(OntologyTable)
          .where(sql`path <@ ${path}::ltree`)
          .returning(),
      );
      if (result == null) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }
      return result;
    }),

  updateConcept: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        values: z.object({
          color: z.enum(Object.keys(AnnotationColors)).optional(),
          description: z.string().min(1).optional(),
          properties: OntologyPropertySchema.optional(),
          mapping: z.array(z.string()).optional(),
        }),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const { user } = ctx;
      const { id, values } = input;
      const { mapping, ...ontTableProps } = values;

      await requirePermissions(user, undefined, [
        "model:create",
        "data:load",
        "data:update",
      ]);

      if (
        ontTableProps.properties ||
        ontTableProps.color ||
        ontTableProps.description
      ) {
        const [ontUpdate] = await logAndRethrow(() =>
          db
            .update(OntologyTable)
            .set({
              ...ontTableProps,
            })
            .where(eq(OntologyTable.id, id))
            .returning(),
        );

        if (ontUpdate == null) {
          throw new TRPCError({ code: "NOT_FOUND" });
        }
      }

      if (mapping)
        await logAndRethrow(() =>
          db.transaction(async (tx) => {
            await tx
              .delete(AnnotationToOntology)
              .where(eq(AnnotationToOntology.ontologyId, id));
            if (mapping.length > 0) {
              await tx.insert(AnnotationToOntology).values(
                mapping.map((m) => ({
                  ontologyId: id,
                  annotation: m,
                })),
              );
            }
          }),
        );
    }),

  getColorMapping: protectedProcedure.query(async () => {
    const rows = await logAndRethrow(() =>
      db
        .select({
          mapping: AnnotationToOntology.annotation,
          color: OntologyTable.color,
        })
        .from(OntologyTable)
        .innerJoin(
          AnnotationToOntology,
          eq(AnnotationToOntology.ontologyId, OntologyTable.id),
        ),
    );
    const colors: Record<string, string> = {};
    rows.forEach((r) => (colors[r.mapping] = r.color));
    return colors;
  }),

  addConcept: protectedProcedure
    .input(OntologyConceptSchema)
    .mutation(async ({ input, ctx }) => {
      const { user } = ctx;
      const { name, parentId, description } = input;

      await requirePermissions(user, undefined, ["model:create"]);

      const parent = parentId
        ? await logAndRethrow(() =>
            db.query.OntologyTable.findFirst({
              where: (c, { eq }) => eq(c.id, parentId),
            }),
          )
        : undefined;

      if (!parent) {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      const path = parent ? `${parent.path}.${name}` : name;

      return await logAndRethrow(() =>
        db
          .insert(OntologyTable)
          .values({
            name,
            parentId: parent?.id ?? null,
            path,
            description,
          })
          .returning(),
      );
    }),

  getOntology: protectedProcedure.query(async () => {
    const [result, mapping] = await logAndRethrow(() => {
      const iprops = db
        .select({
          ...getTableColumns(OntologyTable),
          properties: sql<OntologyProperties>`(
        SELECT jsonb_object_agg(key, value)
        FROM jsonb_each(${OntologyTable.properties})
        WHERE (value ->> 'inherit')::boolean = true
    )`.as(randomAlphaUnderscore()),
        })
        .from(OntologyTable)
        .where(sql`${OntologyTable.properties} != '{}'::jsonb`)
        .as(randomAlphaUnderscore());
      return Promise.all([
        db
          .select({
            ...getTableColumns(OntologyTable),
            iprops: jsonStrictAgg(
              jsonBuildObject({ path: iprops.path, props: iprops.properties }),
              sql`LENGTH(${iprops.path}::text)`,
            ),
          })
          .from(OntologyTable)
          .leftJoin(
            iprops,
            and(
              sql`${iprops.path} @> ${OntologyTable.path}`,
              ne(OntologyTable.id, iprops.id),
            ),
          )
          .groupBy(
            OntologyTable.path,
            OntologyTable.id,
            OntologyTable.isAttribute,
            OntologyTable.color,
            OntologyTable.name,
            OntologyTable.properties,
          ),
        db
          .select({
            id: AnnotationToOntology.ontologyId,
            mappings: jsonAgg(AnnotationToOntology.annotation),
          })
          .from(AnnotationToOntology)
          .groupBy((t) => t.id),
      ]);
    });

    return result.map((r) => ({
      ...r,
      mappings: (mapping.find((m) => m.id === r.id)?.mappings ??
        []) as string[],
      properties: mergeProps(r.properties, r.iprops),
      iprops: undefined,
    }));
  }),

  getFullPath: protectedProcedure
    .input(
      z.object({
        path: z.string(),
      }),
    )
    .query(async ({ input }) => {
      const { path } = input;
      return (
        await logAndRethrow(() =>
          db
            .select({ path: OntologyTable.path })
            .from(OntologyTable)
            .where(sql`${OntologyTable.path} <@ ${path.trim()}::ltree`)
            .orderBy((t) => asc(t.path)),
        )
      ).map((v) => v.path);
    }),
});

const mergeProps = (
  props: OntologyProperties | null,
  iprops: { path: string; props: OntologyProperties }[],
) => {
  const out = props ?? {};
  for (const prop of iprops) {
    if (prop.props == null) continue;
    const definedBy = prop.path;
    const entries = Object.entries(prop.props as object).reduce(
      (agg, [k, v]) => {
        agg[k] = { ...v, definedBy };
        return agg;
      },
      {} as OntologyProperties,
    );
    Object.assign(out, entries);
  }
  return out;
};
