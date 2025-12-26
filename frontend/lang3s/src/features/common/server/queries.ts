import "server-only";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";
import { coalesce, jsonAgg, jsonBuildObject, jsonValue } from "@/lib/db/funcs";
import { MetadataConfiguration, MetadataItem } from "@/features/common/types";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { and, eq, getTableColumns, ne, not, sql } from "drizzle-orm";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { randomAlphaUnderscore } from "@/lib/utils/random";

export const getBaseAnnotationQuery = ({
  isSentence,
  requireOntology = false,
  includeStopWords = false,
}: {
  isSentence: boolean;
  requireOntology?: boolean;
  includeStopWords?: boolean;
}) => {
  if (isSentence) {
    return db
      .select({
        ...getTableColumns(TextAnnotationTable),
        content: sql<string>`${TextAnnotationTable.content}`.as(
          randomAlphaUnderscore(),
        ),
        path: sql`${""}`.as(randomAlphaUnderscore()),
      })
      .from(TextAnnotationTable)
      .where(
        and(
          eq(TextAnnotationTable.type, "sentence"),
          includeStopWords
            ? undefined
            : not(
                sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
              ),
        ),
      );
  }

  if (!requireOntology) {
    return db
      .select({
        ...getTableColumns(TextAnnotationTable),
        content: coalesce(
          jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
          jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
          TextAnnotationTable.content,
        ).as(randomAlphaUnderscore()),
        path: TextAnnotationTable.value,
      })
      .from(TextAnnotationTable)
      .where(
        and(
          ne(TextAnnotationTable.type, "sentence"),
          includeStopWords
            ? undefined
            : not(
                sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
              ),
        ),
      );
  }

  return db
    .select({
      ...getTableColumns(TextAnnotationTable),
      content: coalesce(
        jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
        jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
        TextAnnotationTable.content,
      ).as(randomAlphaUnderscore()),
      value: OntologyTable.name,
      path: OntologyTable.path,
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
    .where(
      and(
        ne(TextAnnotationTable.type, "sentence"),
        includeStopWords
          ? undefined
          : not(
              sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
            ),
      ),
    );
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
