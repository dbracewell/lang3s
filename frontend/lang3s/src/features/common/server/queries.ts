import "server-only";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";
import { coalesce } from "@/lib/db/funcs";
import { MetadataConfiguration, MetadataItem } from "@/features/common/types";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import {
  and,
  eq,
  getTableColumns,
  ne,
  not,
  SQL,
  sql,
  SQLWrapper,
} from "drizzle-orm";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { jsonAgg, jsonBuildObject, jsonValue } from "@/lib/db/helpers/json";

export const getBaseAnnotationQuery = ({
  isSentence,
  requireOntology = false,
  includeStopWords = false,
  contentTransform = (v) => v,
  where,
}: {
  isSentence: boolean;
  requireOntology?: boolean;
  includeStopWords?: boolean;
  contentTransform?: (value: SQL<string>) => SQL<string>;
  where?: SQLWrapper[];
}) => {
  const whereClauses: SQLWrapper[] = where ?? [];
  if (!includeStopWords) {
    whereClauses.push(
      not(
        sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
      ),
    );
  }
  if (isSentence) {
    whereClauses.push(eq(TextAnnotationTable.type, "sentence"));
    return db
      .select({
        ...getTableColumns(TextAnnotationTable),
        content: contentTransform(
          sql<string>`${TextAnnotationTable.content}`,
        ).as(randomAlphaUnderscore()),
        path: sql<string>`${""}`.as(randomAlphaUnderscore()),
        a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
        a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
        time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
          "TIME",
        ),
        location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
          "LOCATION",
        ),
      })
      .from(TextAnnotationTable)
      .where(and(...whereClauses));
  }

  whereClauses.push(ne(TextAnnotationTable.type, "sentence"));

  if (!requireOntology) {
    return db
      .select({
        ...getTableColumns(TextAnnotationTable),
        content: contentTransform(
          coalesce(
            jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
            jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
            TextAnnotationTable.content,
          ),
        ).as(randomAlphaUnderscore()),
        path: TextAnnotationTable.value,
        a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
        a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
        time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
          "TIME",
        ),
        location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
          "LOCATION",
        ),
      })
      .from(TextAnnotationTable)
      .where(and(...whereClauses));
  }

  return db
    .select({
      ...getTableColumns(TextAnnotationTable),
      content: contentTransform(
        coalesce(
          jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
          jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
          TextAnnotationTable.content,
        ),
      ).as(randomAlphaUnderscore()),
      value: OntologyTable.name,
      path: OntologyTable.path,
      a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
      a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
      time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as(
        "TIME",
      ),
      location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
        "LOCATION",
      ),
    })
    .from(TextAnnotationTable)
    .innerJoin(
      AnnotationToOntology,
      eq(TextAnnotationTable.mapping, AnnotationToOntology.annotation),
    )
    .innerJoin(
      OntologyTable,
      eq(AnnotationToOntology.ontologyId, OntologyTable.id),
    )
    .where(and(...whereClauses));
};

export const getMetadata = async () => {
  const data = await logAndRethrow(() =>
    db
      .select({
        source: MetadataTable.source,
        items: jsonAgg(
          jsonBuildObject({
            id: MetadataTable.id,
            name: MetadataTable.name,
            dataType: MetadataTable.dataType,
            formatter: MetadataTable.formatter,
          }),
        ),
      })
      .from(MetadataTable)
      .groupBy(MetadataTable.source),
  );

  const metadataConfig: MetadataConfiguration = {
    document: {},
    annotation: {},
    sentence: {},
  };

  data.forEach((item) => {
    metadataConfig[item.source] = item.items.reduce(
      (agg, m) => {
        agg[m.name] = {
          id: m.id,
          dataType: m.dataType,
          formatter: m.formatter,
        };
        return agg;
      },
      {} as Record<string, MetadataItem>,
    );
  });

  return metadataConfig;
};
