import {
  boolean,
  index,
  integer,
  jsonb,
  pgTable,
  serial,
  text,
  unique,
} from "drizzle-orm/pg-core";
import z from "zod";
import { ltree } from "@/lib/db/custom_types";

////////////////////////////////////////////////////////////////////////////////
// Ontology Table
////////////////////////////////////////////////////////////////////////////////

export const OntologyPropertyValueDataTypes = [
  "string",
  "boolean",
  "number",
  "metadata",
] as const;

export const OntologyPropertyValueSchema = z.object({
  value: z.string().min(1, "Value is required"),
  dataType: z.enum(OntologyPropertyValueDataTypes),
  inherit: z.boolean(),
  display: z.boolean(),
  definedBy: z.string().optional(),
});

export type OntologyPropertyValue = z.infer<typeof OntologyPropertyValueSchema>;
export const OntologyPropertySchema = z.record(
  z.string(),
  OntologyPropertyValueSchema,
);
export type OntologyProperties = z.infer<typeof OntologyPropertySchema>;

export const OntologyTable = pgTable(
  "ontology",
  {
    id: serial("id").primaryKey(),
    name: text("name").notNull().unique(),
    parentId: integer("parent_id"),
    description: text("description"),
    color: text("color").default("SLATE").notNull(),
    isAttribute: boolean("is_attribute").default(false).notNull(),
    path: ltree("path").notNull(), // ltree type (custom)
    properties: jsonb("properties").$type<OntologyProperties>().default({}),
  },
  (table) => [
    index("idx_ontology_parent_id").on(table.parentId),
    index("idx_ontology_name").on(table.name),
    index("idx_ontology_path_gist").using("GIST", table.path),
  ],
);

////////////////////////////////////////////////////////////////////////////////
// Annotation Value to Ontology Table
////////////////////////////////////////////////////////////////////////////////

export const AnnotationToOntology = pgTable(
  "annotation_to_ontology",
  {
    id: serial("id").primaryKey(),
    ontologyId: integer("ontology_id")
      .notNull()
      .references(() => OntologyTable.id, { onDelete: "cascade" }),
    annotation: text("annotation_type_value").notNull(),
  },
  (table) => [
    unique("ato_ont_type_idx").on(table.ontologyId, table.annotation),
    index("ato_ont_id").on(table.ontologyId),
    index("ato_ont_type").on(table.annotation),
  ],
);
