import { db } from "@/lib/db";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schema";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { eq, sql } from "drizzle-orm";
import z from "zod";
import { logAndRethrow } from "@/lib/utils/try-catch";

export const ontologyRouter = createTRPCRouter({
  getColorMapping: protectedProcedure.query(async () => {
    const rows = await logAndRethrow(
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
    .input(
      z.object({
        name: z.string().min(1),
        parentName: z.string().optional(),
        description: z.string(),
      }),
    )
    .mutation(async ({ input }) => {
      return await insertConcept(input.name, input.parentName, {});
    }),
  getTopLevel: protectedProcedure.query(async () => {
    try {
      const result = await db.execute(sql`
        WITH RECURSIVE ontology_tree AS (
          SELECT id, name, description, path, parent_id
          FROM ${OntologyTable}
          WHERE parent_id is null
          UNION ALL
          SELECT c.id, c.name, c.description, c.path, c.parent_id
          FROM ontology c
          JOIN ontology_tree ct ON c.parent_id = ct.id
        )
        SELECT * FROM ontology_tree;
      `);
      return result.rows.map((r) => ({
        id: r.id as number,
        name: r.name as string,
        description: r.description as string,
        path: r.path as string,
        parentId: r.parent_id as number,
      }));
    } catch (error) {
      console.error(error);
      return [];
    }
  }),
});

async function insertConcept(
  name: string,
  parentName: string | null | undefined,
  props: Record<string, any> = {},
) {
  const parent = parentName
    ? await db.query.OntologyTable.findFirst({
        where: (c, { eq }) => eq(c.name, parentName),
      })
    : undefined;

  const path = parent ? `${parent.path}.${name}` : name;

  await db.insert(OntologyTable).values({
    name,
    parentId: parent?.id ?? null,
    path,
    properties: props,
  });
}
