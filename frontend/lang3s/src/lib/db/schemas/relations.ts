import { JobsTable, user } from "@/lib/db/schema";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import {
  DocumentsTable,
  TextAnnotationTable,
  TextTable,
} from "@/lib/db/schemas/text";
import { relations } from "drizzle-orm";

export const UserRelations = relations(user, ({ many }) => ({
  jobs: many(JobsTable),
}));

export const DocumentRelations = relations(DocumentsTable, ({ one }) => ({
  text: one(TextTable, {
    fields: [DocumentsTable.id],
    references: [TextTable.documentId],
  }),
}));

export const TextRelations = relations(TextTable, ({ one }) => ({
  url: one(DocumentsTable, {
    fields: [TextTable.documentId],
    references: [DocumentsTable.id],
  }),
}));

export const TextAnnotationRelations = relations(
  TextAnnotationTable,
  ({ one }) => ({
    document: one(DocumentsTable, {
      fields: [TextAnnotationTable.documentId],
      references: [DocumentsTable.id],
    }),
    text: one(TextTable, {
      fields: [TextAnnotationTable.textId],
      references: [TextTable.id],
    }),
    ontology: one(AnnotationToOntology, {
      fields: [TextAnnotationTable.mapping],
      references: [AnnotationToOntology.annotation],
    }),
  }),
);

export const OntologyRelations = relations(OntologyTable, ({ one, many }) => ({
  parent: one(OntologyTable, {
    fields: [OntologyTable.parentId],
    references: [OntologyTable.id],
    relationName: "ontology",
  }),
  children: many(OntologyTable, {
    relationName: "ontology",
  }),
  annotationTypes: many(AnnotationToOntology),
}));

export const AnnotationToOntologyRelations = relations(
  AnnotationToOntology,
  ({ one, many }) => ({
    ontologyItem: one(OntologyTable, {
      fields: [AnnotationToOntology.ontologyId],
      references: [OntologyTable.id],
    }),
    annotations: many(TextAnnotationTable),
  }),
);
