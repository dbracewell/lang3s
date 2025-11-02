import { TextAnnotationTable } from "@/db/schema";
import {
  boolean,
  customType,
  index,
  integer,
  jsonb,
  pgTable,
  serial,
  text,
  unique,
} from "drizzle-orm/pg-core";

////////////////////////////////////////////////////////////////////////////////
// Ontology Table
////////////////////////////////////////////////////////////////////////////////

const ltree = customType<{ data: string }>({
  dataType() {
    return "ltree";
  },
});

export const OntologyTable = pgTable(
  "ontology",
  {
    id: serial("id").primaryKey(),
    name: text("name").notNull().unique(),
    parentId: integer("parent_id"),
    description: text("description"),
    isAttribute: boolean("is_attribute").default(false).notNull(),
    path: ltree("path").notNull(), // ltree type (custom)
    properties: jsonb("properties").$type<Record<string, any>>().default({}),
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
